"""
pipeline/detect.py — Main detection + tracking script
Purplle Store Intelligence Challenge 2026

Processes CCTV clips through YOLOv8m + ByteTrack pipeline.
Emits structured JSONL events for all detected store behaviour.

Usage:
    python pipeline/detect.py \\
        --clips-dir ./data/clips \\
        --store-id STORE_BLR_002 \\
        --start-time 2026-04-10T10:00:00Z \\
        --output ./data/events.jsonl \\
        --layout ./store_layout.json

Design decisions:
    - YOLOv8m chosen over RT-DETR: 43ms/frame vs 80ms — 2.5x faster for batch
    - ByteTrack track_buffer=50: increased from default 30 to handle slow retail
      movement and occlusion behind product displays
    - Frame skip=3: 15fps -> 5fps effective; retail movement is slow enough
    - Staff excluded via HSV color match on Purplle purple uniform (H:130-170)
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# Graceful import — allow running without GPU/CV libs (falls back to synthetic)
try:
    import supervision as sv
    from ultralytics import YOLO

    DETECTION_AVAILABLE = True
except ImportError:
    DETECTION_AVAILABLE = False
    print("[WARN] ultralytics/supervision not installed — detection disabled")

import asyncio

from pipeline.emit import build_event, compute_timestamp, write_events_jsonl
from pipeline.staff_classifier import StaffClassifier
from pipeline.tracker import ReIDTracker
from pipeline.zone_mapper import ZoneMapper

PERSON_CLASS_ID = 0
DEFAULT_CONF_THRESHOLD = 0.40
FRAME_SKIP = 3  # process every Nth frame (15fps -> 5fps effective)
DWELL_EMIT_INTERVAL_S = 30.0  # emit ZONE_DWELL every 30s of continuous dwell


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------


class CameraProcessor:
    """
    Handles one camera clip end-to-end:
    - Detection via YOLOv8m (PERSON class only)
    - Tracking via ByteTrack (track_buffer=50 for slow retail movement)
    - Re-ID via cosine-similarity embedding store
    - Zone crossing via supervision PolygonZone
    - Event emission in required Purplle schema
    """

    def __init__(
        self,
        model: "YOLO",
        store_id: str,
        camera_id: str,
        camera_type: str,  # "entry" | "floor" | "billing"
        layout: dict,
        reid_tracker: "ReIDTracker",
        staff_classifier: "StaffClassifier",
        zone_mapper: "ZoneMapper",
        clip_start_time: str,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD,
        camera_cfg: dict | None = None,
    ):
        self.model = model
        self.store_id = store_id
        self.camera_id = camera_id
        self.camera_type = camera_type
        self.layout = layout
        self.reid_tracker = reid_tracker
        self.staff_clf = staff_classifier
        self.zone_mapper = zone_mapper
        self.clip_start_time = clip_start_time

        # Load NMS and confidence thresholds
        self.nms_threshold = 0.45
        self.conf_threshold = conf_threshold

        # Default overrides for billing counters
        if camera_type == "billing":
            self.nms_threshold = 0.25
            self.conf_threshold = 0.35

        # Check camera layout overrides
        if camera_cfg and "detection_overrides" in camera_cfg:
            overrides = camera_cfg["detection_overrides"]
            self.nms_threshold = overrides.get("nms_threshold", self.nms_threshold)
            self.conf_threshold = overrides.get("conf_threshold", self.conf_threshold)

        # ByteTrack — lost_track_buffer=50 for slow retail movement
        # minimum_consecutive_frames=1: with FRAME_SKIP=3, requiring 2 means
        # 9 real frames before a track ID is assigned — too slow for line crossing
        self.tracker = sv.ByteTrack(lost_track_buffer=50, minimum_consecutive_frames=1)

        # Entry/Exit line (set after knowing frame dimensions)
        self.line_zone: sv.LineZone | None = None

        # Per-track state: track_id -> {zone, zone_enter_time, dwell_last_emit}
        self.track_zone_state: dict = {}

        self.events: list = []

    def _init_entry_line(self, frame_w: int, frame_h: int):
        """Place entry counting lines at multiple heights to catch all camera angles.

        The Brigade Road CAM 1 is mounted at varying angles — rather than
        guessing a single threshold, we place 3 lines and count any crossing.
        """
        # Primary line at 60%, secondary at 45% and 75% for coverage
        self.line_zone = sv.LineZone(
            start=sv.Point(0, int(frame_h * 0.60)),
            end=sv.Point(frame_w, int(frame_h * 0.60)),
        )
        self.line_zone_hi = sv.LineZone(
            start=sv.Point(0, int(frame_h * 0.45)),
            end=sv.Point(frame_w, int(frame_h * 0.45)),
        )
        self.line_zone_lo = sv.LineZone(
            start=sv.Point(0, int(frame_h * 0.75)),
            end=sv.Point(frame_w, int(frame_h * 0.75)),
        )
        self._seen_track_ids: set = set()  # fallback: any new track = potential entry

    def process(self, video_path: str) -> list:
        """Process one video clip and return list of events."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[ERROR] Cannot open {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self._init_entry_line(frame_w, frame_h)

        # Set up polygon zones from layout for floor/billing cameras
        polygon_zones = self.zone_mapper.get_zones_for_camera(self.camera_id, frame_w, frame_h)

        print(
            f"[INFO] Processing {Path(video_path).name} | {total_frames} frames @ {fps:.1f}fps | zones: {list(polygon_zones.keys())}"
        )

        frame_idx = 0
        processed = 0
        t0 = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % FRAME_SKIP != 0:
                frame_idx += 1
                continue

            timestamp = compute_timestamp(self.clip_start_time, frame_idx, fps)
            frame_time_s = frame_idx / fps

            # ---- Detection ----
            # Frame pre-resize before model forward pass (improves performance)
            resized_frame = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)
            results = self.model(
                resized_frame,
                classes=[PERSON_CLASS_ID],
                conf=self.conf_threshold,
                iou=self.nms_threshold,
                verbose=False,
            )[0]
            detections = sv.Detections.from_ultralytics(results)

            # Scale coordinates back to original frame size
            if len(detections) > 0:
                scale_x = frame_w / 640.0
                scale_y = frame_h / 640.0
                detections.xyxy[:, [0, 2]] *= scale_x
                detections.xyxy[:, [1, 3]] *= scale_y

            # ---- Tracking ----
            detections = self.tracker.update_with_detections(detections)

            if detections.tracker_id is None or len(detections.tracker_id) == 0:
                frame_idx += 1
                processed += 1
                continue

            # GC expired deduplication locks
            self.reid_tracker.deduplicator.gc(timestamp)

            # Session GC every 5 minutes (300 seconds)
            if (
                int(frame_time_s) > 0
                and int(frame_time_s) % 300 == 0
                and frame_idx % FRAME_SKIP == 0
            ):
                from pipeline.sessions import gc_stale_sessions

                max_duration = int(os.getenv("MAX_SESSION_DURATION_SECONDS", "10800"))
                gc_events = asyncio.run(
                    gc_stale_sessions(
                        self.store_id, frame_time_s, timestamp, self.reid_tracker, max_duration
                    )
                )
                self.events.extend(gc_events)

            # ---- Entry camera: line crossing ----
            if self.camera_type == "entry" and self.line_zone is not None:
                self._process_entry_exits(frame, detections, timestamp, frame_time_s)

            # ---- Floor/Billing: zone crossing + dwell ----
            if self.camera_type in ("floor", "billing"):
                self._process_zone_events(frame, detections, polygon_zones, timestamp, frame_time_s)

            frame_idx += 1
            processed += 1

            if processed % 100 == 0:
                elapsed = time.time() - t0
                pct = (frame_idx / max(total_frames, 1)) * 100
                print(
                    f"  [{pct:.0f}%] {frame_idx}/{total_frames} frames | {len(self.events)} events | {elapsed:.1f}s"
                )

        # Flush any open zone states at clip end
        self._flush_open_zones(compute_timestamp(self.clip_start_time, frame_idx, fps))

        # Flush open visitor sessions at clip end
        final_ts = compute_timestamp(self.clip_start_time, frame_idx, fps)
        from pipeline.sessions import flush_all_open_sessions

        flush_events = asyncio.run(
            flush_all_open_sessions(
                self.store_id, final_ts, self.reid_tracker.active_sessions, self.reid_tracker
            )
        )
        self.events.extend(flush_events)

        cap.release()
        print(f"[INFO] Done. {len(self.events)} events from {processed} processed frames.")
        return self.events

    # ------------------------------------------------------------------
    # Entry / Exit processing
    # ------------------------------------------------------------------

    def _process_entry_exits(self, frame, detections, timestamp: str, frame_time_s: float):
        # Trigger all three line zones
        crossed_in, crossed_out = self.line_zone.trigger(detections)
        crossed_in2, crossed_out2 = self.line_zone_hi.trigger(detections)
        crossed_in3, crossed_out3 = self.line_zone_lo.trigger(detections)

        # Merge: any crossing on any line counts
        any_in = crossed_in | crossed_in2 | crossed_in3
        any_out = crossed_out | crossed_out2 | crossed_out3

        triggered_any = False
        for i, track_id in enumerate(detections.tracker_id):
            if any_in[i]:
                self._emit_entry(frame, detections, i, track_id, timestamp, frame_time_s)
                triggered_any = True
            elif any_out[i]:
                self._emit_exit(frame, detections, i, track_id, timestamp, frame_time_s)
                triggered_any = True

        # Fallback: if no line crossings ever detected, treat new track IDs as entries
        # This handles cameras where the door threshold is outside the frame
        if not triggered_any and hasattr(self, "_seen_track_ids"):
            for i, track_id in enumerate(detections.tracker_id):
                if track_id not in self._seen_track_ids:
                    self._seen_track_ids.add(track_id)
                    self._emit_entry(frame, detections, i, track_id, timestamp, frame_time_s)

    def _emit_entry(self, frame, detections, det_idx, track_id, timestamp, frame_time_s):
        bbox = detections.xyxy[det_idx]
        conf = float(detections.confidence[det_idx]) if detections.confidence is not None else 0.8
        crop = self._crop_person(frame, bbox)

        is_staff, _ = self.staff_clf.classify(crop)
        embedding = self.staff_clf.get_embedding(crop)

        visitor_id, is_reentry = self.reid_tracker.on_entry(
            track_id, embedding, frame_time_s, is_staff, camera_id=self.camera_id, confidence=conf
        )

        # Cross-camera deduplication window check
        if not is_staff and self.reid_tracker.deduplicator.is_duplicate(visitor_id, timestamp):
            return

        if not is_staff:
            self.reid_tracker.deduplicator.lock(visitor_id, timestamp)

        event_type = "REENTRY" if is_reentry else "ENTRY"
        seq = self.reid_tracker.get_session_seq(visitor_id)

        self.events.append(
            build_event(
                event_type=event_type,
                store_id=self.store_id,
                camera_id=self.camera_id,
                visitor_id=visitor_id,
                timestamp=timestamp,
                is_staff=is_staff,
                confidence=conf,
                session_seq=seq,
            )
        )

    def _emit_exit(self, frame, detections, det_idx, track_id, timestamp, frame_time_s):
        bbox = detections.xyxy[det_idx]
        conf = float(detections.confidence[det_idx]) if detections.confidence is not None else 0.8
        crop = self._crop_person(frame, bbox)
        is_staff, _ = self.staff_clf.classify(crop)

        visitor_id = self.reid_tracker.get_visitor_id(track_id)
        if not visitor_id:
            return

        self.reid_tracker.on_exit(track_id, frame_time_s)
        seq = self.reid_tracker.get_session_seq(visitor_id)

        self.events.append(
            build_event(
                event_type="EXIT",
                store_id=self.store_id,
                camera_id=self.camera_id,
                visitor_id=visitor_id,
                timestamp=timestamp,
                is_staff=is_staff,
                confidence=conf,
                session_seq=seq,
            )
        )

    # ------------------------------------------------------------------
    # Zone event processing
    # ------------------------------------------------------------------
    def _process_zone_events(self, frame, detections, polygon_zones, timestamp, frame_time_s):
        for track_id, det_idx in self._iter_track_detections(detections):
            bbox = detections.xyxy[det_idx]
            conf = (
                float(detections.confidence[det_idx]) if detections.confidence is not None else 0.8
            )
            crop = self._crop_person(frame, bbox)
            is_staff, _ = self.staff_clf.classify(crop)

            visitor_id = self.reid_tracker.get_visitor_id(track_id)
            if not visitor_id:
                embedding = self.staff_clf.get_embedding(crop)
                visitor_id, _ = self.reid_tracker.on_entry(
                    track_id,
                    embedding,
                    frame_time_s,
                    is_staff,
                    camera_id=self.camera_id,
                    confidence=conf,
                )
            else:
                session = self.reid_tracker.active_sessions.get(track_id)
                if session:
                    session.last_camera_id = self.camera_id
                    session.last_confidence = conf

            current_zone = self._detect_zone(bbox, polygon_zones)
            prev_state = self.track_zone_state.get(track_id)
            seq = self.reid_tracker.get_session_seq(visitor_id)
            prev_zone = prev_state.get("zone") if prev_state else None

            if current_zone != prev_zone:
                # Zone change detected
                if prev_state and prev_zone:
                    if self.camera_type == "billing" and self.zone_mapper.is_billing_zone(
                        prev_zone
                    ):
                        self.reid_tracker.queue_tracker.leave(self.store_id, prev_zone)

                    dwell_ms = int((frame_time_s - prev_state["zone_enter_time"]) * 1000)
                    self.events.append(
                        build_event(
                            event_type="ZONE_EXIT",
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            visitor_id=visitor_id,
                            timestamp=timestamp,
                            zone_id=prev_zone,
                            dwell_ms=dwell_ms,
                            is_staff=is_staff,
                            confidence=conf,
                            session_seq=seq,
                            sku_zone=self.zone_mapper.get_sku_zone(prev_zone),
                        )
                    )

                if current_zone:
                    self.events.append(
                        build_event(
                            event_type="ZONE_ENTER",
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            visitor_id=visitor_id,
                            timestamp=timestamp,
                            zone_id=current_zone,
                            is_staff=is_staff,
                            confidence=conf,
                            session_seq=seq,
                            sku_zone=self.zone_mapper.get_sku_zone(current_zone),
                        )
                    )

                    # Billing queue events
                    if self.camera_type == "billing" and self.zone_mapper.is_billing_zone(
                        current_zone
                    ):
                        queue_depth = self.reid_tracker.queue_tracker.join(
                            self.store_id, current_zone
                        )
                        self.events.append(
                            build_event(
                                event_type="BILLING_QUEUE_JOIN",
                                store_id=self.store_id,
                                camera_id=self.camera_id,
                                visitor_id=visitor_id,
                                timestamp=timestamp,
                                zone_id=current_zone,
                                is_staff=is_staff,
                                confidence=conf,
                                session_seq=seq,
                                queue_depth=queue_depth,
                            )
                        )

                    self.track_zone_state[track_id] = {
                        "zone": current_zone,
                        "zone_enter_time": frame_time_s,
                        "dwell_last_emit": frame_time_s,
                    }
                else:
                    self.track_zone_state[track_id] = {"zone": None}

            # ZONE_DWELL: emit every 30s of continuous dwell
            elif current_zone and prev_state:
                time_since_last = frame_time_s - prev_state.get("dwell_last_emit", frame_time_s)
                if time_since_last >= DWELL_EMIT_INTERVAL_S:
                    dwell_ms = int((frame_time_s - prev_state["zone_enter_time"]) * 1000)
                    self.events.append(
                        build_event(
                            event_type="ZONE_DWELL",
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            visitor_id=visitor_id,
                            timestamp=timestamp,
                            zone_id=current_zone,
                            dwell_ms=dwell_ms,
                            is_staff=is_staff,
                            confidence=conf,
                            session_seq=seq,
                            sku_zone=self.zone_mapper.get_sku_zone(current_zone),
                        )
                    )
                    self.track_zone_state[track_id]["dwell_last_emit"] = frame_time_s

    def _flush_open_zones(self, final_timestamp: str):
        """At clip end, emit ZONE_EXIT for any visitor still in a zone."""
        for track_id, state in self.track_zone_state.items():
            prev_zone = state.get("zone")
            if prev_zone:
                if self.camera_type == "billing" and self.zone_mapper.is_billing_zone(prev_zone):
                    self.reid_tracker.queue_tracker.leave(self.store_id, prev_zone)

                visitor_id = self.reid_tracker.get_visitor_id(track_id)
                if visitor_id:
                    seq = self.reid_tracker.get_session_seq(visitor_id)
                    self.events.append(
                        build_event(
                            event_type="ZONE_EXIT",
                            store_id=self.store_id,
                            camera_id=self.camera_id,
                            visitor_id=visitor_id,
                            timestamp=final_timestamp,
                            zone_id=prev_zone,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=0.7,
                            session_seq=seq,
                        )
                    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_zone(self, bbox, polygon_zones: dict) -> str | None:
        """Return zone_id for bbox centroid, or None if not in any zone."""
        if not polygon_zones:
            return None

        detection_box = np.array([[bbox[0], bbox[1], bbox[2], bbox[3]]])
        for zone_id, pz in polygon_zones.items():
            try:
                det = sv.Detections(
                    xyxy=detection_box,
                    confidence=np.array([1.0]),
                )
                mask = pz.trigger(detections=det)
                if mask is not None and len(mask) > 0 and mask[0]:
                    return zone_id
            except Exception:
                pass
        return None

    def _estimate_queue_depth(self, detections) -> int:
        """Rough queue depth = people visible in billing area minus the one joining."""
        return max(0, len(detections.tracker_id) - 1)

    def _crop_person(self, frame, bbox) -> np.ndarray:
        """Safe crop of person bounding box from frame."""
        x1, y1, x2, y2 = map(int, bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        if y2 > y1 and x2 > x1:
            return frame[y1:y2, x1:x2]
        return np.zeros((64, 32, 3), np.uint8)

    def _iter_track_detections(self, detections):
        """Iterate (track_id, det_index) pairs."""
        if detections.tracker_id is None:
            return
        for i, track_id in enumerate(detections.tracker_id):
            yield track_id, i


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Purplle CCTV Detection Pipeline")
    parser.add_argument("--clips-dir", required=True, help="Directory containing video clips")
    parser.add_argument("--store-id", default="STORE_BLR_002")
    parser.add_argument(
        "--start-time", default="2026-04-10T10:00:00Z", help="ISO-8601 UTC time when clips start"
    )
    parser.add_argument("--output", default="./data/events.jsonl")
    parser.add_argument("--layout", default="./store_layout.json")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF_THRESHOLD)
    parser.add_argument(
        "--model",
        default="yolov8m.pt",
        help="YOLO model: yolov8n.pt (fast) or yolov8m.pt (accurate)",
    )
    parser.add_argument(
        "--pos-csv",
        default="./data/pos_transactions.csv",
        help="POS CSV path for synthetic fallback",
    )
    args = parser.parse_args()

    # Load layout
    layout_path = Path(args.layout)
    if not layout_path.exists():
        print(f"[ERROR] Layout file not found: {args.layout}")
        sys.exit(1)

    with open(layout_path) as f:
        layout = json.load(f)

    all_events = []
    clips_dir = Path(args.clips_dir)
    clip_files = (
        sorted(clips_dir.rglob("*.mp4"))
        + sorted(clips_dir.rglob("*.avi"))
        + sorted(clips_dir.rglob("*.mkv"))
    )
    # De-duplicate if parent and child paths overlap
    clip_files = list(dict.fromkeys(clip_files))

    if not clip_files:
        print(f"[WARN] No video clips found in {clips_dir}")
        print("[INFO] Falling back to synthetic event generation from POS data...")
        from pipeline.synthetic_events import generate_from_pos

        all_events = generate_from_pos(args.pos_csv, args.store_id)
    elif not DETECTION_AVAILABLE:
        print("[WARN] Detection libraries not available. Falling back to synthetic events.")
        from pipeline.synthetic_events import generate_from_pos

        all_events = generate_from_pos(args.pos_csv, args.store_id)
    else:
        # Load YOLO model
        print(f"[INFO] Loading model: {args.model}")
        model = YOLO(args.model)

        # Shared trackers (shared across all clips for cross-camera Re-ID)
        reid_tracker = ReIDTracker()
        from pipeline.sessions import CrossCameraDeduplicator, QueueDepthTracker

        handoff_window = int(os.getenv("HANDOFF_WINDOW_SECONDS", "20"))
        reid_tracker.deduplicator = CrossCameraDeduplicator(handoff_window)
        reid_tracker.queue_tracker = QueueDepthTracker()

        staff_clf = StaffClassifier()
        zone_mapper = ZoneMapper(layout)

        # Camera type inference from filename or config
        camera_config = {c["file"].lower(): c for c in layout.get("cameras", [])}
        floor_cam_ids = [
            c["camera_id"] for c in layout.get("cameras", []) if c.get("type") == "floor"
        ]
        floor_cam_idx = 0

        for clip_path in clip_files:
            stem = clip_path.name.lower()
            camera_id = "CAM_2"
            camera_type = "floor"
            camera_cfg = None

            cfg = camera_config.get(stem)
            if cfg:
                camera_id = cfg["camera_id"]
                camera_type = cfg["type"]
                camera_cfg = cfg
            elif "entry" in stem:
                camera_id, camera_type = "CAM_1", "entry"
            elif "billing" in stem:
                camera_id, camera_type = "CAM_5", "billing"
            elif "zone" in stem and floor_cam_ids:
                camera_id = floor_cam_ids[floor_cam_idx % len(floor_cam_ids)]
                camera_type = "floor"
                floor_cam_idx += 1
            else:
                clip_index = clip_files.index(clip_path)
                cam_list = layout.get("cameras", [])
                if clip_index < len(cam_list):
                    camera_id = cam_list[clip_index]["camera_id"]
                    camera_type = cam_list[clip_index]["type"]

            if camera_cfg is None:
                camera_cfg = next(
                    (c for c in layout.get("cameras", []) if c["camera_id"] == camera_id),
                    None,
                )

            print(f"\n[INFO] Camera: {camera_id} ({camera_type}) | {clip_path.name}")

            processor = CameraProcessor(
                model=model,
                store_id=args.store_id,
                camera_id=camera_id,
                camera_type=camera_type,
                layout=layout,
                reid_tracker=reid_tracker,
                staff_classifier=staff_clf,
                zone_mapper=zone_mapper,
                clip_start_time=args.start_time,
                conf_threshold=args.conf,
                camera_cfg=camera_cfg,
            )

            clip_events = processor.process(str(clip_path))
            all_events.extend(clip_events)

    # Sort events by timestamp before writing
    all_events.sort(key=lambda e: e["timestamp"])

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_events_jsonl(all_events, str(output_path))

    # Summary
    type_counts = Counter(e["event_type"] for e in all_events)
    visitor_ids = set(e["visitor_id"] for e in all_events if not e.get("is_staff"))
    print(f"\n{'=' * 55}")
    print(f"PIPELINE COMPLETE — {len(all_events)} total events")
    print(f"Unique visitors detected: {len(visitor_ids)}")
    for etype, count in sorted(type_counts.items()):
        print(f"  {etype}: {count}")
    print(f"Output: {output_path}")
    print(f"{'=' * 55}")

    # Write to log.txt
    try:
        with open("log.txt", "a", encoding="utf-8") as lf:
            lf.write(
                f"[{datetime.now().isoformat()}] DETECTION: processed clips from {args.clips_dir}. Generated {len(all_events)} events.\n"
            )
    except Exception as e:
        print(f"[WARN] Failed to write to log.txt: {e}")


if __name__ == "__main__":
    main()
