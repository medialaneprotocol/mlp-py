"""Path probing: measure RTT, loss and goodput per path, pick the best."""


class ProbeResult:
    def __init__(self, path_id, rtt_ms, loss_ratio, goodput_bps, completed_at):
        self.path_id = path_id
        self.rtt_ms = rtt_ms
        self.loss_ratio = loss_ratio
        self.goodput_bps = goodput_bps
        self.completed_at = completed_at


class PathProber:
    def __init__(self, interval_ms, probes_per_path):
        self.interval_ms = interval_ms
        self.probes_per_path = probes_per_path
        self.results = []
        self.last_probe = None

    def should_probe(self, now_ms):
        if self.last_probe is None:
            return True
        return now_ms - self.last_probe >= self.interval_ms

    def record(self, result):
        self.results.append(result)
        self.last_probe = result.completed_at

    def best_path(self):
        if not self.results:
            return None
        best = self.results[0]
        for r in self.results[1:]:
            if r.rtt_ms < best.rtt_ms or (r.rtt_ms == best.rtt_ms and r.loss_ratio < best.loss_ratio):
                best = r
        return best.path_id

    def path_results(self, path_id):
        return [r for r in self.results if r.path_id == path_id]
