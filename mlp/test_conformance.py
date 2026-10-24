import json, os
from mlp.pdu import Fragment


def test_conformance_vectors():
    path = os.path.join(os.path.dirname(__file__), "conformance", "vectors.json")
    with open(path) as f:
        data = json.load(f)
    for v in data["vectors"]:
        b = bytes.fromhex(v["hex"])
        frag, n = Fragment.parse(b)
        assert n == len(b), v["name"]
        assert frag is not None
