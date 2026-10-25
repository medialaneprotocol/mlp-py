"""The eight Prometheus counters the core's telemetry sink renders."""


class PrometheusTelemetry:
    def __init__(self):
        self.fragments_sent = 0
        self.fragments_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.updates_applied = 0
        self.convergences = 0
        self.losses = 0
        self.echoes = 0

    def record_fragment_sent(self, n):
        self.fragments_sent += 1
        self.bytes_sent += n

    def record_fragment_received(self, n):
        self.fragments_received += 1
        self.bytes_received += n

    def record_update_applied(self):
        self.updates_applied += 1

    def record_convergence(self):
        self.convergences += 1

    def record_loss(self):
        self.losses += 1

    def record_echo(self):
        self.echoes += 1

    def render(self):
        lines = []
        for name, help_text in (
            ("mlp_fragments_sent_total", "Total fragments sent."),
            ("mlp_fragments_received_total", "Total fragments received."),
            ("mlp_bytes_sent_total", "Total bytes sent."),
            ("mlp_bytes_received_total", "Total bytes received."),
            ("mlp_updates_applied_total", "Total updates applied."),
            ("mlp_convergences_total", "Total convergences."),
            ("mlp_losses_total", "Total losses detected."),
            ("mlp_echoes_total", "Total echoes measured."),
        ):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {getattr(self, name[4:])}")
        return "\n".join(lines) + "\n"
