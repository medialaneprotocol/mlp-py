"""The park table and its TTLs (MLP spec §9.2)."""

RESUME_TTL_SECONDS = 900
PARK_TTL_FLOOR_SECONDS = 120
PARK_TTL_CEIL_SECONDS = 900
PARK_TTL_DEFAULT = 300


class ResumeRejectReason:
    ACCEPTED = "accepted"
    NO_SLOT = "no_slot"    # the table holds no such session
    EXPIRED = "expired"    # the TTL passed; the state is gone


class ParkedSession:
    def __init__(self, session_id, last_applied_id, chain_epoch, pending_cells,
                 ttl_seconds=PARK_TTL_DEFAULT):
        self.session_id = session_id
        self.last_applied_id = last_applied_id
        self.chain_epoch = chain_epoch
        self.pending_cells = pending_cells
        self.ttl_seconds = ttl_seconds
        self.parked_at_ms = 0


class ParkTable:
    """Holds parked sessions under their TTLs."""

    def __init__(self, now_ms=lambda: 0):
        self.sessions = {}
        self._now_ms = now_ms

    def park(self, session):
        ttl = session.ttl_seconds or PARK_TTL_DEFAULT
        session.ttl_seconds = min(max(ttl, PARK_TTL_FLOOR_SECONDS), PARK_TTL_CEIL_SECONDS)
        session.parked_at_ms = self._now_ms()
        self.sessions[session.session_id] = session

    def claim(self, session_id):
        session = self.sessions.pop(session_id, None)
        if session is None:
            return None, ResumeRejectReason.NO_SLOT
        if self._now_ms() - session.parked_at_ms > session.ttl_seconds * 1000:
            return None, ResumeRejectReason.EXPIRED
        return session, ResumeRejectReason.ACCEPTED
