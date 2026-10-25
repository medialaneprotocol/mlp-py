"""The receiver's accept path and the 64-update ack window."""

from mlp.assembly import ObjectAssembler
from mlp.pdu import Fragment, UpdateMeta

ACK_WINDOW_BITS = 64
_WINDOW_MASK = (1 << ACK_WINDOW_BITS) - 1


class MediaAckWindow:
    """The 64-update window an ack carries.

    Bit 0 names the highest applied update; bit i names the update i below
    it. Update id 0 is not an update id: the sender's ids start at 1.
    """

    def __init__(self):
        self._highest = 0
        self._bits = 0

    @property
    def highest_applied_update_id(self):
        return self._highest

    @property
    def bitmap(self):
        return self._bits

    def reset(self):
        self._highest = 0
        self._bits = 0

    def has(self, update_id):
        if update_id < 1 or update_id > self._highest:
            return False
        distance = self._highest - update_id
        if distance >= ACK_WINDOW_BITS:
            return False
        return (self._bits & (1 << distance)) != 0

    def mark(self, update_id):
        if update_id > self._highest:
            shift = update_id - self._highest
            if shift >= ACK_WINDOW_BITS:
                self._bits = 1
            else:
                self._bits = (self._bits << shift | 1) & _WINDOW_MASK
            self._highest = update_id
            return
        distance = self._highest - update_id
        if distance < ACK_WINDOW_BITS:
            self._bits |= 1 << distance

    def seed_from_resume(self, highest_applied):
        self.reset()
        self._highest = highest_applied
        if self._highest > 0:
            self._bits = 1


class ReceiverStats:
    def __init__(self):
        self.fragments_accepted = 0
        self.fragments_refused = 0
        self.objects_assembled = 0
        self.objects_replayed = 0
        self.updates_applied = 0


class MediaReceiverMachine:
    """Parse, dedup, assemble, and hold the ack window over applied ids."""

    def __init__(self):
        self.assembler = ObjectAssembler()
        self.ack = MediaAckWindow()
        self.stats = ReceiverStats()

    def accept_fragment(self, data):
        frag, n = Fragment.parse(data)
        if n != len(data):
            self.stats.fragments_refused += 1
            raise ValueError("bad length: trailing bytes")
        self.stats.fragments_accepted += 1
        obj, whole = self.assembler.accept(frag)
        if whole:
            self.stats.objects_assembled += 1
        return obj

    def note_applied(self, update_id):
        self.stats.updates_applied += 1
        self.ack.mark(update_id)
