"""Gap-based loss detection: three acks past a packet declare it lost."""


class LossDetector:
    def __init__(self, threshold=3):
        self.largest_acked = None
        self.sent = set()
        self.acked = set()
        self.lost = set()
        self.threshold = threshold

    def on_send(self, pn):
        self.sent.add(pn)

    def on_ack(self, acked):
        for pn in acked:
            self.acked.add(pn)
            if self.largest_acked is None or pn > self.largest_acked:
                self.largest_acked = pn
        self._detect()

    def _detect(self):
        if self.largest_acked is None:
            return
        for pn in list(self.sent):
            if pn >= self.largest_acked or pn in self.acked or pn in self.lost:
                continue
            if self.largest_acked - pn >= self.threshold:
                self.lost.add(pn)

    def is_lost(self, pn):
        return pn in self.lost

    def lost_count(self):
        return len(self.lost)
