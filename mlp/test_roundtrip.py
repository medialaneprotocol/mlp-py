def test_roundtrip():
    from mlp.roundtrip import run_roundtrip
    res = run_roundtrip(320, 240, bytes([1, 2, 3, 4, 5]))
    assert res["fragments_sent"] > 0
    assert res["fragments_received"] == res["fragments_sent"]
