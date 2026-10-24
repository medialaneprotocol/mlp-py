import struct

FRAGMENT_MAGIC = b"MLP\x00"
MEDIA_PROTOCOL_VERSION = 1
FRAGMENT_FIXED_HEADER = 22
MAX_HEADER_EXT = 256

CLASS_CONTROL = 0
CLASS_CURSOR = 1
CLASS_MEDIA = 2
CLASS_FEEDBACK = 3
CLASS_PATH = 4
CLASS_DATAGRAM = 5

PRIO_CONTROL = 0
PRIO_INPUT = 1
PRIO_REPORT = 2
PRIO_CURSOR = 5
PRIO_MEDIA = 6
PRIO_REFRESH = 7

TLV = {
    "UPDATE_ID": 0x01,
    "UPDATE_BASE": 0x02,
    "PART": 0x03,
    "UPDATE_BYTES": 0x04,
    "CHAIN_EPOCH": 0x05,
    "REFLECTS_INPUT_SEQ": 0x06,
    "SEND_EPOCH_MS": 0x07,
    "CELL_COUNT": 0x08,
    "BUDGET_BYTES": 0x09,
    "STREAM_ID": 0x10,
    "GREASE": 0x7F,
}


class HeaderExt:
    def __init__(self):
        self.entries = []  # list of (kind, bytes)

    def push_u64(self, kind, v):
        self.entries.append((kind, struct.pack("<Q", v)))

    def push_u32(self, kind, v):
        self.entries.append((kind, struct.pack("<I", v)))

    def push_u16_pair(self, kind, a, b):
        self.entries.append((kind, struct.pack("<HH", a, b)))

    def get(self, kind):
        for k, v in self.entries:
            if k == kind:
                return v
        return None

    def get_u64(self, kind):
        v = self.get(kind)
        if v is None or len(v) != 8:
            return None
        return struct.unpack("<Q", v)[0]

    def get_u32(self, kind):
        v = self.get(kind)
        if v is None or len(v) != 4:
            return None
        return struct.unpack("<I", v)[0]

    def get_u16_pair(self, kind):
        v = self.get(kind)
        if v is None or len(v) != 4:
            return None
        a, b = struct.unpack("<HH", v)
        return a, b

    def encoded_len(self):
        return sum(2 + len(v) for _, v in self.entries)

    def encode(self):
        out = bytearray()
        for kind, v in self.entries:
            out.append(kind)
            out.append(len(v))
            out.extend(v)
        return bytes(out)

    @classmethod
    def parse(cls, b):
        h = cls()
        off = 0
        n = len(b)
        while off < n:
            if off + 2 > n:
                raise ValueError("bad ext")
            kind = b[off]
            l = b[off + 1]
            off += 2
            if off + l > n:
                raise ValueError("bad ext")
            h.entries.append((kind, bytes(b[off:off + l])))
            off += l
        return h


class UpdateMeta:
    def __init__(self, update_id=0, update_base=0, part_index=0, part_count=1,
                 update_bytes=0, chain_epoch=0, reflects_input_seq=0, stream_id=0, send_epoch_ms=0):
        self.update_id = update_id
        self.update_base = update_base
        self.part_index = part_index
        self.part_count = part_count
        self.update_bytes = update_bytes
        self.chain_epoch = chain_epoch
        self.reflects_input_seq = reflects_input_seq
        self.stream_id = stream_id
        self.send_epoch_ms = send_epoch_ms

    def to_ext(self):
        h = HeaderExt()
        h.push_u64(TLV["UPDATE_ID"], self.update_id)
        h.push_u64(TLV["UPDATE_BASE"], self.update_base)
        h.push_u16_pair(TLV["PART"], self.part_index, self.part_count)
        h.push_u32(TLV["UPDATE_BYTES"], self.update_bytes)
        h.push_u32(TLV["CHAIN_EPOCH"], self.chain_epoch)
        h.push_u64(TLV["REFLECTS_INPUT_SEQ"], self.reflects_input_seq)
        h.push_u32(TLV["STREAM_ID"], self.stream_id)
        h.push_u64(TLV["SEND_EPOCH_MS"], self.send_epoch_ms)
        return h

    @classmethod
    def from_ext(cls, ext):
        uid = ext.get_u64(TLV["UPDATE_ID"])
        if uid is None:
            return None
        ub = ext.get_u64(TLV["UPDATE_BASE"])
        pair = ext.get_u16_pair(TLV["PART"])
        pi, pc = (pair if pair else (0, 1))
        ubytes = ext.get_u32(TLV["UPDATE_BYTES"])
        ce = ext.get_u32(TLV["CHAIN_EPOCH"])
        ris = ext.get_u64(TLV["REFLECTS_INPUT_SEQ"])
        sid = ext.get_u32(TLV["STREAM_ID"])
        sem = ext.get_u64(TLV["SEND_EPOCH_MS"])
        return cls(
            update_id=uid,
            update_base=ub if ub is not None else 0,
            part_index=pi,
            part_count=pc,
            update_bytes=ubytes if ubytes is not None else 0,
            chain_epoch=ce if ce is not None else 0,
            reflects_input_seq=ris if ris is not None else 0,
            stream_id=sid if sid is not None else 0,
            send_epoch_ms=sem if sem is not None else 0,
        )

    def check_against(self, other):
        if self != other and (self.update_id, self.update_base, self.part_index, self.part_count,
                              self.update_bytes, self.chain_epoch, self.reflects_input_seq, self.send_epoch_ms) != \
           (other.update_id, other.update_base, other.part_index, other.part_count,
            other.update_bytes, other.chain_epoch, other.reflects_input_seq, other.send_epoch_ms):
            raise ValueError("meta mismatch")


class FragmentHeader:
    def __init__(self, version=1, cls=CLASS_MEDIA, flags=0, priority=PRIO_MEDIA,
                 object_id=0, fragment_index=0, fragment_count=1, payload_len=0, header_ext_len=0):
        self.version = version
        self.cls = cls
        self.flags = flags
        self.priority = priority
        self.object_id = object_id
        self.fragment_index = fragment_index
        self.fragment_count = fragment_count
        self.payload_len = payload_len
        self.header_ext_len = header_ext_len


class Fragment:
    def __init__(self, header, ext, payload):
        self.header = header
        self.ext = ext
        self.payload = payload

    def encode(self):
        ext_bytes = self.ext.encode()
        self.header.payload_len = len(self.payload)
        self.header.header_ext_len = len(ext_bytes)
        out = bytearray()
        out += FRAGMENT_MAGIC
        out.append(self.header.version)
        out.append(self.header.cls)
        out.append(self.header.flags)
        out.append(self.header.priority)
        out += struct.pack("<I", self.header.object_id)
        out += struct.pack("<H", self.header.fragment_index)
        out += struct.pack("<H", self.header.fragment_count)
        out += struct.pack("<I", len(self.payload))
        out += struct.pack("<H", len(ext_bytes))
        out += ext_bytes
        out += self.payload
        return bytes(out)

    @classmethod
    def parse(cls, buf):
        if len(buf) < FRAGMENT_FIXED_HEADER:
            raise ValueError("bad length")
        if buf[0:4] != FRAGMENT_MAGIC:
            raise ValueError("bad magic")
        version = buf[4]
        if version != MEDIA_PROTOCOL_VERSION:
            raise ValueError("unsupported version")
        fclass = buf[5]
        flags = buf[6]
        prio = buf[7]
        if prio > 7:
            raise ValueError("bad priority")
        object_id = struct.unpack("<I", buf[8:12])[0]
        frag_index = struct.unpack("<H", buf[12:14])[0]
        frag_count = struct.unpack("<H", buf[14:16])[0]
        payload_len = struct.unpack("<I", buf[16:20])[0]
        ext_len = struct.unpack("<H", buf[20:22])[0]
        if frag_count == 0 or frag_index >= frag_count:
            raise ValueError("bad fragment")
        if fclass == CLASS_MEDIA and prio <= PRIO_INPUT:
            raise ValueError("bad priority")
        if ext_len != 0 and ext_len < 2:
            raise ValueError("bad ext")
        if ext_len > MAX_HEADER_EXT:
            raise ValueError("bad ext")
        ext_end = FRAGMENT_FIXED_HEADER + ext_len
        payload_end = ext_end + payload_len
        if len(buf) < payload_end:
            raise ValueError("bad length")
        ext = HeaderExt.parse(buf[FRAGMENT_FIXED_HEADER:ext_end])
        payload = bytes(buf[ext_end:payload_end])
        header = FragmentHeader(
            version=version, cls=fclass, flags=flags, priority=prio,
            object_id=object_id, fragment_index=frag_index, fragment_count=frag_count,
            payload_len=payload_len, header_ext_len=ext_len,
        )
        return cls(header, ext, payload), payload_end


# Carrier
CARRIER_WS = 0
CARRIER_GRPC = 1


def carrier_fragment_payload_max(c):
    if c == CARRIER_WS:
        return 1024
    if c == CARRIER_GRPC:
        return 4096
    return 1024


# Fragment flags
FLAG_ANCHOR = 1 << 0
FLAG_ECHO_REQUESTED = 1 << 1
FLAG_DUPLICATE = 1 << 2
