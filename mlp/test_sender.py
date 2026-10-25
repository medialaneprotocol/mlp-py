from mlp.cells import CellAccounting, CellGrid
from mlp.pdu import (
    CARRIER_DATA_CHANNEL, CARRIER_WS, FLAG_ANCHOR, FLAG_ECHO_REQUESTED, FLAG_FIN,
    Fragment, HeaderExt, UpdateMeta,
)
from mlp.sender import MediaSenderMachine, Scheduler, UpdateRequest


def make_part(oid, idx, count, fin=False, payload=b""):
    return Fragment(
        __import__("mlp.pdu", fromlist=["FragmentHeader"]).FragmentHeader(
            object_id=oid, fragment_index=idx, fragment_count=count,
            flags=(FLAG_FIN if fin else 0), payload_len=len(payload)),
        HeaderExt(), bytes(payload))


def test_sender_fits_and_stamps():
    s = MediaSenderMachine(CellGrid(320, 240, 64))
    payload = bytes(range(256)) * 19  # ~4864 bytes
    outcome = s.enqueue(
        UpdateRequest(payload, cells=[0], anchor=True, echo_critical=True), CARRIER_WS, 42)
    assert outcome.fragments == 1
    frag = s.poll_fragment()
    assert frag is not None
    assert frag.header.flags & FLAG_ANCHOR
    assert frag.header.flags & FLAG_ECHO_REQUESTED
    assert frag.header.flags & FLAG_FIN


def test_sender_splits_and_fins_on_datagram():
    s = MediaSenderMachine(CellGrid(320, 240, 64))
    outcome = s.enqueue(UpdateRequest(bytes(4096)), CARRIER_DATA_CHANNEL, 0)
    assert outcome.fragments >= 2
    for i in range(outcome.fragments):
        frag = s.poll_fragment()
        assert frag is not None
        raw = frag.encode()
        parsed, n = Fragment.parse(raw)
        assert n == len(raw)
        meta = UpdateMeta.from_ext(parsed.ext)
        assert meta.update_id == outcome.update_id
        if i == outcome.fragments - 1:
            assert parsed.header.flags & FLAG_FIN
        else:
            assert not parsed.header.flags & FLAG_FIN
    assert s.poll_fragment() is None


def test_sender_accounting_follows_the_corpus():
    s = MediaSenderMachine(CellGrid(320, 240, 64))
    outcome = s.enqueue(UpdateRequest(b"x", cells=[3, 4]), CARRIER_WS, 0)
    assert s.account.pending_count() == 2
    s.note_applied(outcome.update_id, [3, 4])
    assert s.account.converged()


def test_cell_accounting():
    a = CellAccounting(CellGrid(320, 240, 64))
    a.mark_pending([0, 1, 2])
    assert a.pending_count() == 3
    a.mark_applied([0, 1])
    assert a.pending_count() == 1 and not a.converged()
    a.mark_applied([2])
    assert a.converged()


def test_scheduler_parts_follow_the_carrier():
    s = Scheduler(CellGrid(320, 240, 64))
    assert s.max_parts_for(True, 0.0) == 1
    assert s.max_parts_for(False, 0.0) == 8
    assert s.max_parts_for(False, 0.1) == 2


def test_assembly_waits_for_fin():
    from mlp.assembly import ObjectAssembler
    a = ObjectAssembler()
    obj, done = a.accept(make_part(1, 0, 2, payload=b"\x01\x02"))
    assert not done
    obj, done = a.accept(make_part(1, 1, 2, payload=b"\x03\x04"))
    assert not done  # every fragment held, still no FIN
    a = ObjectAssembler()
    a.accept(make_part(1, 0, 2, payload=b"\x01\x02"))
    obj, done = a.accept(make_part(1, 1, 2, fin=True, payload=b"\x03\x04"))
    assert done and obj.payload() == b"\x01\x02\x03\x04"


def test_assembly_refuses_replay():
    from mlp.assembly import ObjectAssembler
    a = ObjectAssembler()
    a.accept(make_part(7, 0, 1, fin=True, payload=b"\x09"))
    _, done = a.accept(make_part(7, 0, 1, fin=True, payload=b"\x09"))
    assert not done


def test_assembly_budgets_open_objects():
    from mlp.assembly import ObjectAssembler, MAX_OPEN_OBJECTS
    a = ObjectAssembler()
    for oid in range(1, MAX_OPEN_OBJECTS + 1):
        a.accept(make_part(oid, 0, 2, payload=b"\x01"))
    try:
        a.accept(make_part(99, 0, 2, payload=b"\x01"))
        assert False, "the fifth open object must exceed the budget"
    except ValueError:
        pass


def test_ack_window_marks_and_slides():
    from mlp.receiver import MediaAckWindow
    w = MediaAckWindow()
    for uid in (1, 2, 3):
        w.mark(uid)
    assert w.highest_applied_update_id == 3
    assert w.has(1) and w.has(2) and w.has(3)
    assert not w.has(0)  # id 0 names no update
    w.mark(1 + 64 + 10)  # a jump of 64+: the window holds it alone
    assert w.highest_applied_update_id == 75
    assert w.has(75) and not w.has(3)
    w.seed_from_resume(41)
    assert w.highest_applied_update_id == 41 and w.bitmap == 1


def test_lifecycle_states():
    from mlp.lifecycle import LaneLifecycle, MediaLaneStateKind, lane_state_name
    l = LaneLifecycle()
    assert l.state == MediaLaneStateKind.STARTING
    l.set_applied(now_ms=1000, pending=8)
    assert l.state == MediaLaneStateKind.CONVERGING
    l.set_applied(now_ms=1100, pending=0)
    assert l.state == MediaLaneStateKind.LIVE
    l.set_applied(now_ms=1100 + 4000, pending=0)  # freshness holds
    l.pending_cells = 1
    l.last_applied_ms = 1000
    l.set_applied(now_ms=5000, pending=1)
    assert lane_state_name(l.state) in ("converging", "stale")


def test_park_table_ttl():
    import mlp.resume as r
    now = [0]
    table = r.ParkTable(now_ms=lambda: now[0])
    table.park(r.ParkedSession(1, last_applied_id=9, chain_epoch=2,
                               pending_cells=[], ttl_seconds=10))
    # A TTL below the floor is clamped up to 120 s, so an immediate claim
    # inside the floor succeeds.
    now[0] = 60_000
    session, reason = table.claim(1)
    assert reason == r.ResumeRejectReason.ACCEPTED and session.last_applied_id == 9
    table.park(r.ParkedSession(3, 9, 2, []))  # default TTL: 300 s
    now[0] += 301_000
    _, reason = table.claim(3)
    assert reason == r.ResumeRejectReason.EXPIRED
    _, reason = table.claim(999)
    assert reason == r.ResumeRejectReason.NO_SLOT


def test_host_input_state():
    from mlp.input import HostInputState
    m = HostInputState()
    m.submit("KeyA", True, deadline_ms=1000)
    assert m.is_pressed("KeyA") and m.pressed_count() == 1
    m.submit("KeyA", False, deadline_ms=1000)
    assert not m.is_pressed("KeyA")
    assert m.expired(2000)  # the release's deadline passed too
