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
