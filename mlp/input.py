"""The sender-side input path: sequencing, deadlines, the pressed set."""


class InputEvent:
    def __init__(self, code, pressed, seq, deadline_ms=0):
        self.code = code
        self.pressed = pressed
        self.seq = seq
        self.deadline_ms = deadline_ms


class HostInputState:
    """A release always leaves the queue: a stuck key is the one input
    error a user cannot undo."""

    def __init__(self):
        self.next_seq = 0
        self.pressed = set()
        self.deadlines = {}
        self.order = []

    def submit(self, code, pressed, deadline_ms=0):
        seq = self.next_seq
        self.next_seq += 1
        if pressed:
            self.pressed.add(code)
        else:
            self.pressed.discard(code)
        if deadline_ms:
            self.deadlines[seq] = deadline_ms
        self.order.append(seq)
        return InputEvent(code, pressed, seq, deadline_ms)

    def is_pressed(self, code):
        return code in self.pressed

    def pressed_count(self):
        return len(self.pressed)

    def expired(self, now_ms):
        return [seq for seq in self.order
                if seq in self.deadlines and now_ms > self.deadlines[seq]]
