"""One sender-to-receiver round trip, as a proof."""

from mlp.cells import CellGrid
from mlp.pdu import CARRIER_WS, UpdateMeta
from mlp.receiver import MediaReceiverMachine
from mlp.sender import MediaSenderMachine, UpdateRequest


def run_roundtrip(width, height, payload):
    grid = CellGrid(width, height, 64)
    sender = MediaSenderMachine(grid)
    receiver = MediaReceiverMachine()

    outcome = sender.enqueue(
        UpdateRequest(payload, cells=[0, 1, 2], anchor=True), CARRIER_WS, 0)

    result = {
        "fragments_sent": outcome.fragments,
        "fragments_received": 0,
        "objects_assembled": 0,
        "update_id": outcome.update_id,
        "ack_highest_applied": 0,
        "payload_match": False,
    }
    assembled = b""
    while True:
        frag = sender.poll_fragment()
        if frag is None:
            break
        obj = receiver.accept_fragment(frag.encode())
        result["fragments_received"] += 1
        if obj is not None:
            assembled = obj.payload()
            result["objects_assembled"] += 1
            receiver.note_applied(UpdateMeta.from_ext(obj.ext).update_id)

    result["ack_highest_applied"] = receiver.ack.highest_applied_update_id
    result["payload_match"] = assembled == payload
    return result
