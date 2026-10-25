"""0-RTT session tickets: a plaintext carrier of the resume point (the
production ticket is signed by the deployment, not by the protocol)."""

import struct
import time

TICKET_TTL_SECONDS = 3600


class SessionTicket:
    def __init__(self, payload, issued_at_ms, nonce):
        self.payload = payload
        self.issued_at_ms = issued_at_ms
        self.nonce = nonce

    def is_valid(self, now_ms):
        return now_ms >= self.issued_at_ms and (now_ms - self.issued_at_ms) <= TICKET_TTL_SECONDS * 1000


def issue_ticket(last_applied_update_id, chain_epoch, now_ms=None):
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    return SessionTicket(struct.pack("<QI", last_applied_update_id, chain_epoch), now_ms, now_ms)


def validate_ticket(ticket, now_ms):
    if not ticket.is_valid(now_ms) or len(ticket.payload) < 12:
        return None
    return struct.unpack("<QI", ticket.payload[:12])
