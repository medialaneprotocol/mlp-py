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
