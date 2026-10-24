class CellGrid:
    def __init__(self, width, height, cell_size):
        self.width = width
        self.height = height
        self.cell_size = cell_size

    def cells(self):
        cx = (self.width + self.cell_size - 1) // self.cell_size
        cy = (self.height + self.cell_size - 1) // self.cell_size
        return cx * cy


class UpdateRequest:
    def __init__(self, payload, cells=None, anchor=False):
        self.payload = payload
        self.cells = cells or []
        self.anchor = anchor


class MediaSenderMachine:
    def __init__(self, grid):
        self.grid = grid
        self.next_id = 1

    def enqueue(self, req, mtu=1200):
        from mlp.pdu import Fragment, FragmentHeader, UpdateMeta
        payload_max = mtu - 22 - 64
        if payload_max < 64:
            payload_max = 64
        update_id = self.next_id
        self.next_id += 1
        meta = UpdateMeta(update_id=update_id, update_base=0, part_index=0, part_count=1,
                          update_bytes=len(req.payload), chain_epoch=1, send_epoch_ms=0)
        ext = meta.to_ext()
        frags = []
        off = 0
        total = max(1, (len(req.payload) + payload_max - 1) // payload_max)
        idx = 0
        if len(req.payload) == 0:
            total = 1
        while off < len(req.payload) or (len(req.payload) == 0 and idx == 0):
            chunk = req.payload[off:off + payload_max]
            flags = 0
            if req.anchor and idx == 0:
                flags = 1  # ANCHOR
            f = Fragment(
                FragmentHeader(version=1, cls=2, flags=flags, priority=6,
                               object_id=update_id, fragment_index=idx,
                               fragment_count=total, payload_len=len(chunk),
                               header_ext_len=ext.encoded_len()),
                ext, bytes(chunk))
            frags.append(f)
            off += len(chunk)
            idx += 1
            if len(req.payload) == 0:
                break
        return frags


class CellAccounting:
    def __init__(self, grid):
        self.grid = grid
        self.pending = set()
        self.applied = set()

    def mark_pending(self, cells):
        for c in cells:
            self.pending.add(c)
            self.applied.discard(c)

    def mark_applied(self, cells):
        for c in cells:
            self.pending.discard(c)
            self.applied.add(c)

    def pending_count(self):
        return len(self.pending)

    def converged(self):
        return len(self.pending) == 0


class Scheduler:
    def __init__(self, grid):
        self.grid = grid

    def plan(self, changed):
        return list(changed)

    def max_chunks_for(self, datagram, loss_ratio):
        if datagram:
            return 1
        return 8


class BweConfig:
    def __init__(self, pace_floor_bps=100000, requested_fps=30.0, viewer_live=True):
        self.pace_floor_bps = pace_floor_bps
        self.requested_fps = requested_fps
        self.viewer_live = viewer_live


class Estimate:
    def __init__(self, pace_bps=100000, max_object_bytes=8192, loss_ratio=0.0, rtt_ms=50.0, mode="live"):
        self.pace_bps = pace_bps
        self.max_object_bytes = max_object_bytes
        self.loss_ratio = loss_ratio
        self.rtt_ms = rtt_ms
        self.mode = mode


class BandwidthEstimator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rtt_ms = 50.0

    def estimate(self):
        return Estimate(pace_bps=self.cfg.pace_floor_bps, rtt_ms=self.rtt_ms)

    def set_rtt(self, ms):
        self.rtt_ms = ms


def xor_parity(data):
    max_len = max((len(d) for d in data), default=0)
    parity = bytearray(max_len)
    for d in data:
        for i, b in enumerate(d):
            parity[i] ^= b
    return bytes(parity)


def recover_one(missing_index, data, parity):
    missing = sum(1 for d in data if d is None)
    if missing != 1:
        return None
    out = bytearray(parity)
    for i, d in enumerate(data):
        if i == missing_index or d is None:
            continue
        for j, b in enumerate(d):
            if j < len(out):
                out[j] ^= b
    return bytes(out)


class StreamFlowControl:
    def __init__(self, credit):
        self.max_data = credit
        self.sent = 0
        self.received = 0

    def available(self):
        return self.max_data - self.sent

    def can_send(self, n):
        return n <= self.available()

    def on_send(self, n):
        self.sent += n

    def update_credit(self, n):
        if n > self.max_data:
            self.max_data = n


class ConnectionFlowControl:
    def __init__(self, credit):
        self.max_data = credit
        self.sent = 0
        self.received = 0

    def available(self):
        return self.max_data - self.sent

    def can_send(self, n):
        return n <= self.available()

    def on_send(self, n):
        self.sent += n

    def update_credit(self, n):
        if n > self.max_data:
            self.max_data = n


class FlowControl:
    def __init__(self, conn_credit, stream_credit):
        self.connection = ConnectionFlowControl(conn_credit)
        self.streams = {}
        self.default_credit = stream_credit

    def stream(self, sid):
        if sid not in self.streams:
            self.streams[sid] = StreamFlowControl(self.default_credit)
        return self.streams[sid]

    def can_send(self, sid, n):
        if not self.connection.can_send(n):
            return False
        return self.stream(sid).can_send(n)

    def on_send(self, sid, n):
        self.connection.on_send(n)
        self.stream(sid).on_send(n)

    def update_stream_credit(self, sid, n):
        self.stream(sid).update_credit(n)

    def update_connection_credit(self, n):
        self.connection.update_credit(n)
