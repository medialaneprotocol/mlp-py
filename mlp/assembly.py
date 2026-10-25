"""Object assembly: FIN-gated completion under the specification's budgets."""

MAX_OPEN_OBJECTS = 4
MAX_ASSEMBLY_BYTES = 1 << 20
DEDUP_WINDOW = 4096


class OpenObject:
    def __init__(self, oid, declared, cls, flags, priority, ext):
        self.object_id = oid
        self.cls = cls
        self.flags = flags
        self.priority = priority
        self.declared = declared
        self.ext = ext
        self.parts = [None] * declared
        self.received = 0
        self.bytes = 0
        self.saw_fin = False

    def whole(self):
        return self.saw_fin and self.received >= self.declared

    def payload(self):
        return b"".join(p for p in self.parts if p is not None)


class ObjectAssembler:
    """Reassembles fragments into objects.

    An object is whole when its FIN fragment arrived and every declared
    fragment is present. A replayed object is refused whole; a fragment
    that contradicts an open object is an error, as is a budget overrun.
    """

    def __init__(self):
        self.open = {}
        self.seen = set()
        self._window = []
        self.bytes = 0

    def accept(self, frag):
        oid = frag.header.object_id
        if oid in self.seen:
            return None, False
        obj = self.open.get(oid)
        if obj is None:
            if len(self.open) >= MAX_OPEN_OBJECTS:
                raise ValueError("assembly budget exceeded: too many open objects")
            obj = OpenObject(oid, frag.header.fragment_count, frag.header.cls,
                             frag.header.flags, frag.header.priority, frag.ext)
            self.open[oid] = obj
        if frag.header.fragment_count != obj.declared:
            raise ValueError("meta mismatch: fragment count changed")
        idx = frag.header.fragment_index
        if obj.parts[idx] is not None:
            return None, False  # duplicate fragment, already held
        if self.bytes + len(frag.payload) > MAX_ASSEMBLY_BYTES:
            raise ValueError("assembly budget exceeded: too many bytes")
        obj.parts[idx] = frag.payload
        obj.received += 1
        obj.bytes += len(frag.payload)
        self.bytes += len(frag.payload)
        if idx == 0:
            obj.ext = frag.ext
        if frag.header.flags & 0x01:  # FLAG_FIN
            obj.saw_fin = True
        if obj.whole():
            del self.open[oid]
            self.bytes -= obj.bytes
            self._remember(oid)
            return obj, True
        return None, False

    def _remember(self, oid):
        self.seen.add(oid)
        self._window.append(oid)
        while len(self._window) > DEDUP_WINDOW:
            self.seen.discard(self._window.pop(0))

    def is_open(self, oid):
        return oid in self.open

    def open_count(self):
        return len(self.open)
