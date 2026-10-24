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
