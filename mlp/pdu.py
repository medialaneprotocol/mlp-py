"""MLP v1 fragment framing — byte level, frozen by the specification.

This module is the Python twin of ``mlp-core``'s ``media::pdu``: the same
magic, the same classes ``0..=4``, the same flag byte, the same TLV
registry, the same carrier budgets. What differs here and there is a bug.
"""

import struct

FRAGMENT_MAGIC = b"MLP\x00"
MEDIA_PROTOCOL_VERSION = 1
FRAGMENT_FIXED_HEADER = 22
MAX_FRAGMENT_COUNT = 4096
MAX_HEADER_EXT = 256
MAX_STREAM_FRAGMENT = 65_536
MAX_GRPC_COALESCE = 65_536
TARGET_FRAGMENT_PAYLOAD = 1_150

# Fragment classes: the wire freezes these; 5..=255 are reserved.
CLASS_CONTROL = 0
CLASS_CURSOR = 1
CLASS_MEDIA = 2
CLASS_FEEDBACK = 3
CLASS_PATH = 4

_CLASS_NAMES = {0: "control", 1: "cursor", 2: "media", 3: "feedback", 4: "path"}


def class_name(cls):
    return _CLASS_NAMES.get(cls, "unknown")


def class_from_u8(value):
    if value > 4:
        raise ValueError(f"bad class {value}")
    return value


# Priority: 0..=7, lower is higher; 0-1 reserved for control, pointer and
# feedback — media may not use them.
PRIO_CONTROL = 0
PRIO_INPUT = 1
PRIO_REPORT = 2
PRIO_CURSOR = 5
PRIO_MEDIA = 6
PRIO_REFRESH = 7

# The flags byte: bit 7 is reserved and must be zero.
FLAG_FIN = 1 << 0            # last fragment of the object
FLAG_ANCHOR = 1 << 1         # absolute writes applying onto any held state
FLAG_RETRANSMIT = 1 << 2     # a resend by the sender's own policy
FLAG_DUP = 1 << 3            # a deliberate duplicate for echo-critical objects
FLAG_ECHO_REQUESTED = 1 << 4 # receiver must reply with an echo
FLAG_PROBE = 1 << 5          # a probe object
FLAG_URGENT = 1 << 6         # control: drain before queued media


def flags_from_bits(bits):
    if bits & 0x80:
        raise ValueError("bad flags: bit 7 is reserved")
    return bits


# The header-extension TLV type registry. Kinds 0x10..=0xEF are skipped
# silently; 0xF0..=0xFF are experimental (skipped and counted).
TLV = {
    "UPDATE_ID": 0x01,
    "UPDATE_BASE": 0x02,
    "PART": 0x03,
    "UPDATE_BYTES": 0x04,
    "CHAIN_EPOCH": 0x05,
    "REFLECTS_INPUT_SEQ": 0x06,
    "SEND_EPOCH_MS": 0x07,
    "DEADLINE_EPOCH_MS": 0x08,
    "ECHO_OF_OBJECT_ID": 0x09,
    "BUDGET_BYTES": 0x0A,
    "PACE_BPS": 0x0B,
    "PATH_HINT": 0x0C,
    "INPUT_SEQ": 0x0D,
    "CELL_COUNT": 0x0E,
    "COST_MS": 0x0F,
    "STREAM_ID": 0x10,
    "FEC_GROUP_ID": 0x11,
    "FEC_K": 0x12,
    "PATH_ID": 0x13,
    "GREASE": 0x7F,
}


class HeaderExt:
    def __init__(self):
        self.entries = []

    def push_u64(self, kind, v):
        self.entries.append((kind, struct.pack("<Q", v)))

    def push_u32(self, kind, v):
        self.entries.append((kind, struct.pack("<I", v)))

    def push_u16(self, kind, v):
        self.entries.append((kind, struct.pack("<H", v)))

    def push_u8(self, kind, v):
        self.entries.append((kind, bytes([v])))

    def push_u16_pair(self, kind, a, b):
        self.entries.append((kind, struct.pack("<HH", a, b)))

    def get(self, kind):
        for k, v in self.entries:
            if k == kind:
                return v
        return None

    def get_u64(self, kind):
        v = self.get(kind)
        return struct.unpack("<Q", v)[0] if len(v or b"") == 8 else None

    def get_u32(self, kind):
        v = self.get(kind)
        return struct.unpack("<I", v)[0] if len(v or b"") == 4 else None

    def get_u16(self, kind):
        v = self.get(kind)
        return struct.unpack("<H", v)[0] if len(v or b"") == 2 else None

    def get_u8(self, kind):
        v = self.get(kind)
        return v[0] if len(v or b"") == 1 else None

    def get_u16_pair(self, kind):
        v = self.get(kind)
        if len(v or b"") != 4:
            return None
        return struct.unpack("<HH", v)

    def encoded_len(self):
        return sum(2 + len(v) for _, v in self.entries)

    def encode(self):
        out = bytearray()
        for kind, v in self.entries:
            if len(v) > 255:
                raise ValueError("tlv value too long")
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
                 update_bytes=0, chain_epoch=0, reflects_input_seq=0, stream_id=0,
                 path_id=0, send_epoch_ms=0):
        self.update_id = update_id
        self.update_base = update_base
        self.part_index = part_index
        self.part_count = part_count
        self.update_bytes = update_bytes
        self.chain_epoch = chain_epoch
        self.reflects_input_seq = reflects_input_seq
        self.stream_id = stream_id
        self.path_id = path_id
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
        h.push_u8(TLV["PATH_ID"], self.path_id)
        h.push_u64(TLV["SEND_EPOCH_MS"], self.send_epoch_ms)
        return h

    @classmethod
    def from_ext(cls, ext):
        def g64(name):
            v = ext.get_u64(TLV[name])
            return v if v is not None else 0

        def g32(name):
            v = ext.get_u32(TLV[name])
            return v if v is not None else 0

        pair = ext.get_u16_pair(TLV["PART"])
        pi, pc = (pair if pair else (0, 1))
        pid = ext.get_u8(TLV["PATH_ID"])
        return cls(
            update_id=g64("UPDATE_ID"),
            update_base=g64("UPDATE_BASE"),
            part_index=pi,
            part_count=pc,
            update_bytes=g32("UPDATE_BYTES"),
            chain_epoch=g32("CHAIN_EPOCH"),
            reflects_input_seq=g64("REFLECTS_INPUT_SEQ"),
            stream_id=g32("STREAM_ID"),
            path_id=pid if pid is not None else 0,
            send_epoch_ms=g64("SEND_EPOCH_MS"),
        )


class FragmentHeader:
    def __init__(self, version=1, cls=CLASS_MEDIA, flags=0, priority=PRIO_MEDIA,
                 object_id=0, fragment_index=0, fragment_count=1, payload_len=0,
                 header_ext_len=0):
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
        if len(ext_bytes) > MAX_HEADER_EXT:
            raise ValueError("bad ext: too long")
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
        fclass = class_from_u8(buf[5])
        flags = flags_from_bits(buf[6])
        prio = buf[7]
        if prio > 7:
            raise ValueError("bad priority")
        object_id = struct.unpack("<I", buf[8:12])[0]
        frag_index = struct.unpack("<H", buf[12:14])[0]
        frag_count = struct.unpack("<H", buf[14:16])[0]
        payload_len = struct.unpack("<I", buf[16:20])[0]
        ext_len = struct.unpack("<H", buf[20:22])[0]
        if frag_count == 0 or frag_count > MAX_FRAGMENT_COUNT or frag_index >= frag_count:
            raise ValueError("bad fragment")
        if fclass == CLASS_MEDIA and prio <= PRIO_INPUT:
            raise ValueError("bad priority: media may not use the reserved band")
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


# The carriers, with the budgets the specification freezes.
CARRIER_WS = 0
CARRIER_GRPC = 1
CARRIER_DATA_CHANNEL = 2
CARRIER_REPAIR_CHANNEL = 3
CARRIER_CONTROL_CHANNEL = 4

_DATAGRAM_CARRIERS = {CARRIER_DATA_CHANNEL, CARRIER_REPAIR_CHANNEL, CARRIER_CONTROL_CHANNEL}


def carrier_fragment_payload_max(c):
    if c in (CARRIER_WS, CARRIER_GRPC):
        return MAX_STREAM_FRAGMENT
    return TARGET_FRAGMENT_PAYLOAD


def carrier_message_cap(c):
    if c == CARRIER_GRPC:
        return MAX_GRPC_COALESCE
    return carrier_fragment_payload_max(c)


def carrier_is_datagram(c):
    return c in _DATAGRAM_CARRIERS
