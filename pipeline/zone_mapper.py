"""
pipeline/zone_mapper.py — Resolves polygon zones from store_layout.json
Purplle Store Intelligence Challenge 2026
"""

import contextlib

import numpy as np

try:
    import supervision as sv

    SV_AVAILABLE = True
except ImportError:
    sv = None
    SV_AVAILABLE = False


class ZoneMapper:
    """
    Reads zone polygons per camera from store_layout.json.
    Returns supervision.PolygonZone instances ready for detection triggering.

    Falls back to evenly-spaced grid if explicit polygons aren't calibrated yet.
    """

    def __init__(self, layout: dict):
        self.layout = layout
        self.zones_by_id = {z["zone_id"]: z for z in layout.get("zones", [])}
        self.cameras = {c["camera_id"]: c for c in layout.get("cameras", [])}

    def get_zones_for_camera(self, camera_id: str, frame_w: int, frame_h: int) -> dict[str, any]:
        """Return dict of zone_id -> PolygonZone for a given camera."""
        if not SV_AVAILABLE:
            return {}

        cam = self.cameras.get(camera_id, {})
        zone_ids = cam.get("zones", [])
        polygons: dict[str, any] = {}

        for zid in zone_ids:
            poly = self._polygon_for_zone(zid, frame_w, frame_h)
            if poly is not None:
                try:
                    polygons[zid] = sv.PolygonZone(
                        polygon=poly,
                    )
                except Exception:
                    # Older supervision API
                    with contextlib.suppress(Exception):
                        polygons[zid] = sv.PolygonZone(
                            polygon=poly,
                            frame_resolution_wh=(frame_w, frame_h),
                        )

        return polygons

    def get_sku_zone(self, zone_id: str) -> str | None:
        """Return the sku_zone category for a given zone_id."""
        z = self.zones_by_id.get(zone_id, {})
        return z.get("sku_zone")

    def get_zone_label(self, zone_id: str) -> str:
        """Return human-readable label for a zone."""
        z = self.zones_by_id.get(zone_id, {})
        return z.get("label", zone_id)

    def is_billing_zone(self, zone_id: str) -> bool:
        """True if zone is a billing/cash counter zone."""
        z = self.zones_by_id.get(zone_id, {})
        return z.get("is_billing", False)

    def _polygon_for_zone(self, zone_id: str, w: int, h: int) -> np.ndarray | None:
        z = self.zones_by_id.get(zone_id, {})

        # Use explicit polygon if defined in layout JSON
        if "polygon" in z:
            poly = np.array(z["polygon"], dtype=np.int32)
            # Scale relative coordinates if values are <= 1.0
            if poly.max() <= 1.0:
                poly = (poly * np.array([w, h])).astype(np.int32)
            return poly

        # Fallback: synthesize a grid-based polygon
        all_zone_ids = list(self.zones_by_id.keys())
        if zone_id not in all_zone_ids:
            return None

        idx = all_zone_ids.index(zone_id)
        cols = 4
        col = idx % cols
        row = idx // cols
        cw = w // cols
        ch = h // max((len(all_zone_ids) // cols) + 1, 1)

        x1, y1 = col * cw, row * ch
        x2, y2 = min(x1 + cw, w), min(y1 + ch, h)

        return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)
