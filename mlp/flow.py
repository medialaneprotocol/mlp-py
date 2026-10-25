"""Per-stream and connection flow control (QUIC-shaped credit windows)."""


class StreamFlowControl:
    def __init__(self, credit):
        self.max_data = credit
        self.sent = 0

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
        return self.connection.can_send(n) and self.stream(sid).can_send(n)

    def on_send(self, sid, n):
        self.connection.on_send(n)
        self.stream(sid).on_send(n)
