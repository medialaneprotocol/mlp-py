"""The sender's enqueue-and-fragment path.

The pacer, the estimator and the repair plans are the Rust machine's; this
module is the byte-level half a Python peer needs to speak first.
"""

from mlp.cells import CellAccounting
from mlp.pdu import (
    CLASS_MEDIA, FLAG_ANCHOR, FLAG_ECHO_REQUESTED, FLAG_FIN, FRAGMENT_FIXED_HEADER,
    Fragment, FragmentHeader, MAX_FRAGMENT_COUNT, PRIO_MEDIA, UpdateMeta,
    carrier_fragment_payload_max,
)


class UpdateRequest:
    def __init__(self, payload, cells=None, anchor=False, echo_critical=False):
        self.payload = payload
        self.cells = cells or []
        self.anchor = anchor
        self.echo_critical = echo_critical


class EnqueueOutcome:
    def __init__(self, update_id, fragments):
        self.update_id = update_id
        self.fragments = fragments


class SenderStats:
    def __init__(self):
        self.updates_enqueued = 0
        self.fragments_sent = 0
        self.bytes_sent = 0


class MediaSenderMachine:
    def __init__(self, grid):
        self.grid = grid
        self.account = CellAccounting(grid)
        self.next_object_id = 1
        self.next_update_id = 1
        self.queue = []
        self.stats = SenderStats()

    def enqueue(self, req, carrier, now_ms=0):
        payload_max = carrier_fragment_payload_max(carrier) - 64  # metadata reserve
        if payload_max < 64:
            payload_max = 64
        if len(req.payload) > payload_max * MAX_FRAGMENT_COUNT:
            raise ValueError("bad length: no carrier can fragment this")

        update_id = self.next_update_id
        self.next_update_id += 1
        object_id = self.next_object_id
        self.next_object_id += 1
        self.account.mark_pending(req.cells)

        total = max(1, (len(req.payload) + payload_max - 1) // payload_max)
        flags = 0
        if req.anchor:
            flags |= FLAG_ANCHOR
        if req.echo_critical:
            flags |= FLAG_ECHO_REQUESTED

        for idx in range(total):
            chunk = req.payload[idx * payload_max:(idx + 1) * payload_max]
            part_flags = flags | (FLAG_FIN if idx == total - 1 else 0)
            meta = UpdateMeta(
                update_id=update_id, update_base=0, part_index=idx, part_count=1,
                update_bytes=len(req.payload), chain_epoch=1, send_epoch_ms=now_ms,
            )
            ext = meta.to_ext()
            frag = Fragment(
                FragmentHeader(
                    version=1, cls=CLASS_MEDIA, flags=part_flags, priority=PRIO_MEDIA,
                    object_id=object_id, fragment_index=idx, fragment_count=total,
                    payload_len=len(chunk), header_ext_len=ext.encoded_len(),
                ),
                ext, bytes(chunk),
            )
            self.queue.append(frag.encode())
            self.stats.fragments_sent += 1
            self.stats.bytes_sent += len(chunk)
        self.stats.updates_enqueued += 1
        return EnqueueOutcome(update_id, total)

    def poll_fragment(self):
        if not self.queue:
            return None
        raw = self.queue.pop(0)
        frag, _ = Fragment.parse(raw)
        return frag

    def note_applied(self, update_id, cells):
        self.account.mark_applied(cells)


class Scheduler:
    """The wire-level half of the scheduler: the part-count rule. The
    priority bands and the capture cycle are the Rust machine's."""

    def __init__(self, grid):
        self.grid = grid

    def max_parts_for(self, datagram, loss_ratio):
        if datagram:
            return 1
        if loss_ratio > 0.05:
            return 2
        return 8
