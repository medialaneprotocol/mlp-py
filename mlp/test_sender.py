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


def test_scheduler():
    from mlp.sender import CellGrid, Scheduler
    g = CellGrid(320, 240, 64)
    s = Scheduler(g)
    cells = [0, 1, 5, 9]
    out = s.plan(cells)
    assert out == cells
    assert s.max_chunks_for(False, 0.1) == 8
    assert s.max_chunks_for(True, 0.1) == 1


def test_bwe():
    from mlp.sender import BweConfig, BandwidthEstimator
    cfg = BweConfig(pace_floor_bps=100000, requested_fps=30.0, viewer_live=True)
    e = BandwidthEstimator(cfg)
    est = e.estimate()
    assert est.pace_bps == 100000
    e.set_rtt(100)
    assert e.rtt_ms == 100


def test_fec():
    from mlp.sender import xor_parity, recover_one
    data = [bytes([1, 2, 3]), bytes([4, 5, 6]), bytes([7, 8, 9])]
    parity = xor_parity(data)
    received = [data[0], None, data[2]]
    rec = recover_one(1, received, parity)
    assert rec is not None
    assert rec[:3] == data[1]


def test_qos():
    from mlp.receiver import QosTier
    assert QosTier.mlp_priority(QosTier.REALTIME) < QosTier.mlp_priority(QosTier.INTERACTIVE)
    assert QosTier.weight(QosTier.REALTIME) > QosTier.weight(QosTier.INTERACTIVE)
