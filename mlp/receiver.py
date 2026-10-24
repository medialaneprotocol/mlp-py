class SurfaceCanvas:
    def __init__(self, w, h):
        self.width = w
        self.height = h
        self.cells = [0] * (w * h)


class MediaReceiverMachine:
    def __init__(self, w, h):
        self.canvas = SurfaceCanvas(w, h)
        self.seen = set()

    def accept_fragment(self, data):
        from mlp.pdu import Fragment
        frag, n = Fragment.parse(data)
        if n != len(data):
            raise ValueError("bad length")
        self.seen.add(frag.header.object_id)
        return True

    def note_applied(self, update_id):
        pass

    def build_ack(self):
        return bytes([0])


class InputToken:
    def __init__(self, kind, code):
        self.kind = kind
        self.code = code

    @staticmethod
    def key(code):
        return InputToken("key", code)


class InputEvent:
    def __init__(self, code, pressed, seq=0):
        self.code = code
        self.pressed = pressed
        self.seq = seq


class InputQueue:
    def __init__(self):
        self.events = []

    def submit(self, e):
        self.events.append(e)

    def __len__(self):
        return len(self.events)


class ResumeRejectReason:
    OK = "ok"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SessionTicket:
    TTL_MS = 3600 * 1000

    def __init__(self, payload, issued_at_ms, nonce):
        self.payload = payload
        self.issued_at_ms = issued_at_ms
        self.nonce = nonce

    def is_valid(self, now_ms):
        return now_ms >= self.issued_at_ms and (now_ms - self.issued_at_ms) <= self.TTL_MS


def issue_ticket(last_applied_update_id, chain_epoch, now_ms):
    import struct
    payload = struct.pack("<QI", last_applied_update_id, chain_epoch)
    return SessionTicket(payload, now_ms, now_ms)


def validate_ticket(ticket, now_ms):
    if not ticket.is_valid(now_ms):
        return None
    if len(ticket.payload) < 12:
        return None
    import struct
    uid, epoch = struct.unpack("<QI", ticket.payload[:12])
    return uid, epoch


class MigrationState:
    IDLE = 0
    PROBING = 1
    MIGRATED = 2
    FAILED = 3


class PathMigration:
    def __init__(self, active_path):
        self.state = MigrationState.IDLE
        self.active_path = active_path
        self.candidate_path = 0
        self.challenge = 0
        self.failures = 0

    def start_probe(self, candidate, challenge):
        self.state = MigrationState.PROBING
        self.candidate_path = candidate
        self.challenge = challenge

    def complete(self, response):
        if self.state != MigrationState.PROBING:
            return False
        if response == self.challenge:
            self.active_path = self.candidate_path
            self.state = MigrationState.MIGRATED
            return True
        self.state = MigrationState.FAILED
        self.failures += 1
        return False

    def is_probing(self):
        return self.state == MigrationState.PROBING


class QosTier:
    BACKGROUND = 0
    BEST_EFFORT = 1
    INTERACTIVE = 2
    REALTIME = 3

    _PRIO = {0: 7, 1: 6, 2: 5, 3: 2}
    _WEIGHT = {0: 1, 1: 2, 2: 4, 3: 8}

    @staticmethod
    def mlp_priority(tier):
        return QosTier._PRIO[tier]

    @staticmethod
    def weight(tier):
        return QosTier._WEIGHT[tier]


class LossDetector:
    def __init__(self, threshold=3):
        self.largest_acked = None
        self.sent = set()
        self.acked = set()
        self.lost = set()
        self.threshold = threshold

    def on_send(self, pn):
        self.sent.add(pn)

    def on_ack(self, acked):
        for pn in acked:
            self.acked.add(pn)
            if self.largest_acked is None or pn > self.largest_acked:
                self.largest_acked = pn
        self._detect()

    def _detect(self):
        if self.largest_acked is None:
            return
        largest = self.largest_acked
        for pn in list(self.sent):
            if pn >= largest:
                continue
            if pn in self.acked or pn in self.lost:
                continue
            if largest - pn >= self.threshold:
                self.lost.add(pn)

    def is_lost(self, pn):
        return pn in self.lost

    def lost_count(self):
        return len(self.lost)


class OpenObject:
    def __init__(self, oid, declared, cls=2, flags=0, priority=6, ext=None):
        self.object_id = oid
        self.declared = declared
        self.cls = cls
        self.flags = flags
        self.priority = priority
        self.ext = ext
        self.parts = [None] * declared
        self.received = 0
        self.bytes = 0


class ObjectAssembler:
    def __init__(self):
        self.open = {}

    def accept(self, frag):
        oid = frag.header.object_id
        if oid not in self.open:
            self.open[oid] = OpenObject(oid, frag.header.fragment_count, frag.header.cls,
                                       frag.header.flags, frag.header.priority, frag.ext)
        obj = self.open[oid]
        if frag.header.fragment_count != obj.declared:
            return None, False
        idx = frag.header.fragment_index
        if obj.parts[idx] is not None:
            return None, False  # duplicate
        obj.parts[idx] = frag.payload
        obj.received += 1
        obj.bytes += len(frag.payload)
        if idx == 0:
            obj.ext = frag.ext
        if obj.received >= obj.declared:
            del self.open[oid]
            return obj, True
        return None, False

    def is_open(self, oid):
        return oid in self.open

    def open_count(self):
        return len(self.open)


class FullMediaReceiver:
    def __init__(self, w, h):
        self.canvas = SurfaceCanvas(w, h) if 'SurfaceCanvas' in globals() else None
        self.assembler = ObjectAssembler()
        self.accounting = CellAccounting(CellGrid(w, h, 64)) if 'CellGrid' in globals() else None
        self.applied = 0

    def accept_fragment(self, data):
        from mlp.pdu import Fragment
        frag, n = Fragment.parse(data)
        if n != len(data):
            raise ValueError("bad length")
        obj, done = self.assembler.accept(frag)
        if done:
            self.applied += 1
        return obj, done, None

    def converged(self):
        return self.accounting.converged() if self.accounting else True


class PrometheusTelemetry:
    def __init__(self):
        self.fragments_sent = 0
        self.fragments_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.updates_applied = 0
        self.convergences = 0
        self.losses = 0
        self.echoes = 0

    def record_fragment_sent(self, n):
        self.fragments_sent += 1
        self.bytes_sent += n

    def record_fragment_received(self, n):
        self.fragments_received += 1
        self.bytes_received += n

    def record_update_applied(self):
        self.updates_applied += 1

    def record_convergence(self):
        self.convergences += 1

    def record_loss(self):
        self.losses += 1

    def record_echo(self):
        self.echoes += 1

    def render(self):
        return (
            "# HELP mlp_fragments_sent_total Total fragments sent.\n"
            "# TYPE mlp_fragments_sent_total counter\n"
            f"mlp_fragments_sent_total {self.fragments_sent}\n"
            "# HELP mlp_bytes_sent_total Total bytes sent.\n"
            "# TYPE mlp_bytes_sent_total counter\n"
            f"mlp_bytes_sent_total {self.bytes_sent}\n"
            "# HELP mlp_updates_applied_total Total updates applied.\n"
            "# TYPE mlp_updates_applied_total counter\n"
            f"mlp_updates_applied_total {self.updates_applied}\n"
            "# HELP mlp_convergences_total Total convergences.\n"
            "# TYPE mlp_convergences_total counter\n"
            f"mlp_convergences_total {self.convergences}\n"
        )


class PacerConfig:
    def __init__(self, pace_bps=8000, max_object_bytes=8192, window_sec=1.0, burst_ratio=1.25, max_grant=16384):
        self.pace_bps = pace_bps
        self.max_object_bytes = max_object_bytes
        self.window_sec = window_sec
        self.burst_ratio = burst_ratio
        self.max_grant = max_grant


class TokenBucket:
    def __init__(self, capacity, refill_per_sec, now):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = capacity
        self.last_refill = now

    def refill(self, now):
        import time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last_refill = now

    def try_consume(self, amount):
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class MediaPacer:
    def __init__(self, cfg, now):
        self.cfg = cfg
        self.bucket = TokenBucket(cfg.pace_bps / 8.0 * cfg.window_sec * cfg.burst_ratio,
                                 cfg.pace_bps / 8.0, now)
        self.window = []

    def window_budget(self):
        rate = self.cfg.pace_bps / 8.0
        allowance = rate * self.cfg.window_sec * self.cfg.burst_ratio
        budget = int(allowance)
        if budget < self.cfg.max_grant:
            budget = self.cfg.max_grant
        return budget

    def window_used(self, now):
        cutoff = now - self.cfg.window_sec
        return sum(w[1] for w in self.window if w[0] > cutoff)

    def try_acquire(self, cls, nbytes, now):
        self.bucket.refill(now)
        budget = self.window_budget()
        used = self.window_used(now)
        if used + nbytes > budget:
            return False
        watermark = 0
        if cls >= 5:
            watermark = int(self.cfg.pace_bps / 8.0 * 0.1)
        if self.bucket.tokens < nbytes + watermark:
            return False
        self.bucket.try_consume(nbytes)
        self.window.append((now, nbytes))
        return True

    def pace_bps(self):
        return self.cfg.pace_bps

    def max_grant_bytes(self):
        return self.cfg.max_grant


class ProbeResult:
    def __init__(self, path_id, rtt_ms, loss_ratio, goodput_bps, completed_at):
        self.path_id = path_id
        self.rtt_ms = rtt_ms
        self.loss_ratio = loss_ratio
        self.goodput_bps = goodput_bps
        self.completed_at = completed_at


class PathProber:
    def __init__(self, interval_ms, probes_per_path):
        self.interval_ms = interval_ms
        self.probes_per_path = probes_per_path
        self.results = []
        self.last_probe = None

    def should_probe(self, now):
        if self.last_probe is None:
            return True
        return (now - self.last_probe) * 1000 >= self.interval_ms

    def record(self, result):
        self.results.append(result)
        self.last_probe = result.completed_at

    def best_path(self):
        if not self.results:
            return None
        best = self.results[0]
        for r in self.results[1:]:
            if r.rtt_ms < best.rtt_ms or (r.rtt_ms == best.rtt_ms and r.loss_ratio < best.loss_ratio):
                best = r
        return best.path_id

    def path_results(self, path_id):
        return [r for r in self.results if r.path_id == path_id]
