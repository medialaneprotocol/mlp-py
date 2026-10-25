"""The token-bucket pacer with its one-second window (INV-7)."""


class PacerConfig:
    def __init__(self, pace_bps=8000, max_object_bytes=8192, reserved_floor_bps=2000,
                 reserved_fraction=0.10, window_sec=1.0, burst_ratio=1.25, max_grant=16384):
        self.pace_bps = pace_bps
        self.max_object_bytes = max_object_bytes
        self.reserved_floor_bps = reserved_floor_bps
        self.reserved_fraction = reserved_fraction
        self.window_sec = window_sec
        self.burst_ratio = burst_ratio
        self.max_grant = max_grant


class TokenBucket:
    def __init__(self, capacity, refill_per_sec, now):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = capacity
        self.last_refill = now

    def refill(self, now):
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last_refill = now

    def try_consume(self, amount):
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class MediaPacer:
    def __init__(self, cfg, now):
        self.cfg = cfg
        self.bucket = TokenBucket(cfg.pace_bps / 8.0 * cfg.window_sec * cfg.burst_ratio,
                                  cfg.pace_bps / 8.0, now)
        self.window = []

    def reserved_rate(self):
        return max(self.cfg.reserved_floor_bps,
                   int(self.cfg.pace_bps * self.cfg.reserved_fraction))

    def window_budget(self):
        rate = self.cfg.pace_bps / 8.0
        budget = int(rate * self.cfg.window_sec * self.cfg.burst_ratio)
        return max(budget, self.cfg.max_grant)

    def window_used(self, now):
        cutoff = now - self.cfg.window_sec
        return sum(n for at, n in self.window if at > cutoff)

    def try_acquire(self, cls, nbytes, now):
        self.bucket.refill(now)
        if self.window_used(now) + nbytes > self.window_budget():
            return False
        self.bucket.try_consume(nbytes)
        self.window.append((now, nbytes))
        return True
