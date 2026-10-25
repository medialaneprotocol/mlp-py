"""Connection migration: the challenge-response that proves the new path
sees the same session."""


class MigrationState:
    IDLE = 0
    PROBING = 1
    MIGRATED = 2
    FAILED = 3


class PathMigration:
    def __init__(self, active_path):
        self.state = MigrationState.IDLE
        self.active_path = active_path
        self.candidate_path = 0
        self.challenge = 0
        self.failures = 0

    def start_probe(self, candidate, challenge):
        self.state = MigrationState.PROBING
        self.candidate_path = candidate
        self.challenge = challenge

    def complete(self, response):
        if self.state != MigrationState.PROBING:
            return False
        if response == self.challenge:
            self.active_path = self.candidate_path
            self.state = MigrationState.MIGRATED
            return True
        self.state = MigrationState.FAILED
        self.failures += 1
        return False

    def is_probing(self):
        return self.state == MigrationState.PROBING
