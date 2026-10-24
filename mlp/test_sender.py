from mlp.sender import CellGrid, UpdateRequest, MediaSenderMachine
from mlp.pdu import Fragment


def test_sender_enqueue():
    g = CellGrid(320, 240, 64)
    s = MediaSenderMachine(g)
    frags = s.enqueue(UpdateRequest(payload=bytes([1, 2, 3, 4, 5])), 1200)
    assert frags
    for f in frags:
        b = f.encode()
        f2, n = Fragment.parse(b)
        assert n == len(b)
        assert f2 is not None
