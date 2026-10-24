# mlp-py

Python reference implementation of the Media Lane Protocol (MLP) wire format.

Mirrors `medialaneprotocol/mlp-core` (Rust) byte-for-byte. Currently implements
the PDU codec: fragment header (22 bytes), TLV header extension, and update
metadata. Full sender/receiver and scheduler are planned.

## Test

```sh
python -m pytest  # or: python -c "import mlp.pdu"
```

Golden-vector test ensures byte-for-byte parity with the Rust reference.
