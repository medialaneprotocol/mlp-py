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


def test_cell_accounting():
    from mlp.sender import CellGrid, CellAccounting
    g = CellGrid(320, 240, 64)
    a = CellAccounting(g)
    a.mark_pending([0, 1, 2])
    assert a.pending_count() == 3
    a.mark_applied([0, 1])
    assert a.pending_count() == 1
    assert not a.converged()
    a.mark_applied([2])
    assert a.converged()
