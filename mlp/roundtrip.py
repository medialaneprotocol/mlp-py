def run_roundtrip(w, h, payload):
    from mlp.sender import CellGrid, MediaSenderMachine, UpdateRequest
    from mlp.receiver import FullMediaReceiver
    grid = CellGrid(w, h, 64)
    sender = MediaSenderMachine(grid)
    receiver = FullMediaReceiver(w, h)
    frags = sender.enqueue(UpdateRequest(payload=payload), 1200)
    received = 0
    for f in frags:
        b = f.encode()
        _, _, err = None, None, None
        try:
            obj, done, err = receiver.accept_fragment(b)
            if err is None:
                received += 1
        except Exception:
            pass
    return {
        "fragments_sent": len(frags),
        "fragments_received": received,
        "converged": receiver.converged(),
    }
