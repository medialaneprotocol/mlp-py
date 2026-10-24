import json, os


def test_interop_roundtrip():
    path = os.path.join(os.path.dirname(__file__), "conformance", "vectors.json")
    with open(path) as f:
        data = json.load(f)
    from mlp.pdu import Fragment
    for v in data["vectors"]:
        b = bytes.fromhex(v["hex"])
        frag, n = Fragment.parse(b)
        assert n == len(b), v["name"]
        enc = frag.encode()
        assert enc.hex() == v["hex"], v["name"]
