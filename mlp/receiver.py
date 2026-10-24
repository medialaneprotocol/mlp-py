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
