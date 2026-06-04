"""
pipeline/tracker.py — Re-ID tracker with cosine-similarity matching
Purplle Store Intelligence Challenge 2026

Handles:
- Visitor session lifecycle (entry, exit, re-entry)
- Appearance embedding comparison for re-identification
- session_seq tracking per visitor (increments on each re-entry)
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class VisitorSession:
    visitor_id: str
    track_ids: list[int] = field(default_factory=list)
    embedding: np.ndarray | None = None
    exit_time: float | None = None
    is_staff: bool = False
    session_seq: int = 1
    started_at: float = 0.0
    last_camera_id: str = "CAM_1"
    last_confidence: float = 0.9


class ReIDTracker:
    """
    Tracks visitor sessions across the entire video.
    Re-ID is done via cosine similarity on appearance embeddings.

    Design decisions:
    - REENTRY_WINDOW_SECONDS = 300 (5 min): Industry standard for retail;
      beyond 5 min the person is treated as a new visit for analytics.
    - COSINE_SIMILARITY_THRESHOLD = 0.75: Empirically found 0.85 (Claude's
      initial suggestion) was too strict — same person returning after 3+ min
      in different lighting scored ~0.71. Lowered to 0.75 after calibration.
    """

    REENTRY_WINDOW_SECONDS = 300  # 5 min re-entry window
    COSINE_SIMILARITY_THRESHOLD = 0.75  # tuned: 0.85 was too strict

    def __init__(self):
        self.active_sessions: dict[int, VisitorSession] = {}  # track_id -> session
        self.exited_sessions: list[VisitorSession] = []
        self.track_to_visitor: dict[int, str] = {}
        self.session_seq_counter: dict[str, int] = {}
        self.visitor_counter = 0

    def on_entry(
        self,
        track_id: int,
        embedding: np.ndarray | None,
        frame_time_s: float,
        is_staff: bool = False,
        camera_id: str = "CAM_1",
        confidence: float = 0.9,
    ) -> tuple[str, bool]:
        """
        Register a new track crossing the entry line.
        Returns (visitor_id, is_reentry).
        Re-entries get the same visitor_id with incremented session_seq.
        """
        match = self._find_reentry_match(embedding, frame_time_s)
        if match:
            # Re-entry: same visitor_id, new session_seq
            match.track_ids.append(track_id)
            match.exit_time = None
            match.last_camera_id = camera_id
            match.last_confidence = confidence
            self.active_sessions[track_id] = match
            self.track_to_visitor[track_id] = match.visitor_id
            if match in self.exited_sessions:
                self.exited_sessions.remove(match)
            self.session_seq_counter[match.visitor_id] = (
                self.session_seq_counter.get(match.visitor_id, 1) + 1
            )
            match.session_seq = self.session_seq_counter[match.visitor_id]
            return match.visitor_id, True

        # New visitor
        self.visitor_counter += 1
        visitor_id = f"VIS_{self.visitor_counter:06x}"
        session = VisitorSession(
            visitor_id=visitor_id,
            track_ids=[track_id],
            embedding=embedding,
            is_staff=is_staff,
            session_seq=1,
            started_at=frame_time_s,
            last_camera_id=camera_id,
            last_confidence=confidence,
        )
        self.active_sessions[track_id] = session
        self.track_to_visitor[track_id] = visitor_id
        self.session_seq_counter[visitor_id] = 1
        return visitor_id, False

    def on_exit(self, track_id: int, timestamp_s: float):
        """Register a track crossing the exit line."""
        if track_id in self.active_sessions:
            session = self.active_sessions.pop(track_id)
            session.exit_time = timestamp_s
            self.exited_sessions.append(session)

    def get_visitor_id(self, track_id: int) -> str | None:
        """Return visitor_id for a given tracker track_id."""
        return self.track_to_visitor.get(track_id)

    def get_session_seq(self, visitor_id: str) -> int:
        """Return current session_seq for a visitor."""
        return self.session_seq_counter.get(visitor_id, 1)

    def _find_reentry_match(
        self, embedding: np.ndarray | None, timestamp_s: float
    ) -> VisitorSession | None:
        if embedding is None or len(embedding) == 0:
            return None

        best_score, best_session = 0.0, None
        for session in self.exited_sessions:
            if session.embedding is None:
                continue
            if (
                session.exit_time
                and (timestamp_s - session.exit_time) > self.REENTRY_WINDOW_SECONDS
            ):
                continue
            norm = np.linalg.norm(embedding) * np.linalg.norm(session.embedding) + 1e-8
            score = float(np.dot(embedding, session.embedding) / norm)
            if score > self.COSINE_SIMILARITY_THRESHOLD and score > best_score:
                best_score, best_session = score, session

        return best_session
