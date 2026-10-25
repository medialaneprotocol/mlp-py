"""The lane's wire vocabulary: ten states, five close codes, three
unsupported reasons (MLP spec §7, §8)."""


class MediaLaneStateKind:
    STARTING = 0
    LIVE = 1
    DEGRADED = 2
    CONVERGING = 3
    STALE = 4
    PARKED = 5
    DISABLED = 6
    DECODE_BOUND = 7
    NO_FEEDBACK = 8
    MEDIA_UNSUPPORTED = 9


_STATE_NAMES = {
    0: "starting", 1: "live", 2: "degraded", 3: "converging", 4: "stale",
    5: "parked", 6: "disabled", 7: "decode_bound", 8: "no_feedback",
    9: "media_unsupported",
}


def lane_state_from_u32(value):
    if value > 9:
        raise ValueError(f"bad lane state {value}")
    return value


def lane_state_name(state):
    return _STATE_NAMES.get(state, "unknown")


class MediaCloseCode:
    NORMAL = 0
    SERVER_SHUTDOWN = 1
    POLICY = 2
    SUPERSEDED = 3
    PARK = 4


def close_code_from_u32(value):
    if value > 4:
        raise ValueError(f"bad close code {value}")
    return value


class MediaUnsupportedReason:
    PROTOCOL = "protocol"
    DISABLED_BY_POLICY = "disabled_by_policy"
    NO_SENDER_CAPABILITY = "no_sender_capability"


class LaneMode:
    SINGLE = 0
    SPLIT = 1


class LaneLifecycle:
    """A state is a fact both ends can measure — freshness, convergence,
    loss — and neither end's claim overrides the other's staleness."""

    def __init__(self, stale_budget_ms=3000):
        self.state = MediaLaneStateKind.STARTING
        self.since_ms = 0
        self.converged = False
        self.pending_cells = 0
        self.last_applied_ms = None
        self.stale_budget_ms = stale_budget_ms
        self.no_feedback = False
        self.loss_ratio = 0.0

    def set_applied(self, now_ms, pending):
        self.last_applied_ms = now_ms
        self.pending_cells = pending
        self.converged = pending == 0
        self._reconsider(now_ms)

    def set_loss(self, ratio):
        self.loss_ratio = ratio

    def _reconsider(self, now_ms):
        if self.state in (MediaLaneStateKind.PARKED, MediaLaneStateKind.DISABLED,
                          MediaLaneStateKind.MEDIA_UNSUPPORTED):
            return
        if self.no_feedback:
            self.state = MediaLaneStateKind.NO_FEEDBACK
        elif self.converged:
            self.state = MediaLaneStateKind.LIVE
        elif self.last_applied_ms is not None and now_ms - self.last_applied_ms > self.stale_budget_ms:
            self.state = MediaLaneStateKind.STALE
        elif self.pending_cells > 0:
            self.state = MediaLaneStateKind.CONVERGING
        else:
            self.state = MediaLaneStateKind.LIVE
        self.since_ms = now_ms
