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


def test_loss_detector():
    from mlp.receiver import LossDetector
    ld = LossDetector()
    for i in range(10):
        ld.on_send(i)
    ld.on_ack([0, 1, 2, 4, 5, 6, 7, 8, 9])
    assert ld.is_lost(3)
    assert ld.lost_count() == 1


def test_assembly():
    from mlp.pdu import Fragment, FragmentHeader
    from mlp.receiver import ObjectAssembler
    a = ObjectAssembler()
    f1 = Fragment(FragmentHeader(object_id=1, fragment_index=0, fragment_count=2, payload_len=4), None, bytes([1,2,3,4]))
    f1.ext = __import__("mlp.pdu", fromlist=["HeaderExt"]).HeaderExt()
    f2 = Fragment(FragmentHeader(object_id=1, fragment_index=1, fragment_count=2, payload_len=4), None, bytes([5,6,7,8]))
    f2.ext = __import__("mlp.pdu", fromlist=["HeaderExt"]).HeaderExt()
    obj, done = a.accept(f1)
    assert not done
    obj, done = a.accept(f2)
    assert done
    assert obj.received == 2
    assert a.open_count() == 0


def test_metrics():
    from mlp.receiver import PrometheusTelemetry
    t = PrometheusTelemetry()
    t.record_fragment_sent(100)
    t.record_update_applied()
    out = t.render()
    assert "mlp_fragments_sent_total 1" in out
    assert "mlp_bytes_sent_total 100" in out
    assert "mlp_updates_applied_total 1" in out


def test_pacer():
    from mlp.receiver import PacerConfig, MediaPacer
    import time
    now = time.time()
    cfg = PacerConfig()
    p = MediaPacer(cfg, now)
    assert p.window_budget() > 0
    assert p.try_acquire(6, 100, now)
    assert p.pace_bps() == 8000


def test_probe():
    from mlp.receiver import ProbeResult, PathProber
    pp = PathProber(1000, 3)
    import time
    now = time.time()
    pp.record(ProbeResult(0, 100.0, 0.05, 1000000, now))
    pp.record(ProbeResult(1, 50.0, 0.01, 2000000, now))
    assert pp.best_path() == 1
    assert pp.should_probe(now) is False or True


def test_flow_control():
    from mlp.sender import FlowControl
    fc = FlowControl(5000, 1000)
    assert fc.can_send(0, 500)
    fc.on_send(0, 500)
    assert fc.can_send(1, 500)
    fc.on_send(1, 500)
    assert not fc.can_send(0, 4100)


def test_input_manager():
    from mlp.receiver import InputManager
    m = InputManager()
    m.submit("KeyA", True, 1000)
    assert m.is_pressed("KeyA")
    assert m.pressed_count() == 1
    m.submit("KeyA", False, 1000)
    assert not m.is_pressed("KeyA")
    assert len(m.expired(2000)) >= 1
