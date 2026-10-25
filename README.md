# mlp-py

Python implementation of the Media Lane Protocol (MLP) wire format.

The wire is frozen by the [specification](https://github.com/medialaneprotocol/mlp):
this package's PDU codec — fragment header, TLV header extension, update
metadata, carriers — matches `medialaneprotocol/mlp-core` (Rust) byte for
byte, and the conformance test re-encodes the reference's own vectors
without a byte of drift.

## What it implements

- **The codec** (`mlp.pdu`): classes `0..=4`, the flag byte
  (FIN/ANCHOR/RETRANSMIT/DUP/ECHO_REQUESTED/PROBE/URGENT, bit 7 reserved),
  the full TLV registry with the reserved and experimental skip bands, the
  five carriers with their payload and message caps.
- **Object assembly** (`mlp.assembly`): FIN-gated completion, the
  four-object and one-megabyte budgets, the windowed object-id dedup.
- **The sender's byte-level half** (`mlp.sender`): enqueue an update,
  fragment it for a carrier, stamp every part with its metadata, FIN the
  last part, poll the encoded fragments.
- **The receiver's accept path** (`mlp.receiver`): parse, dedup, assemble,
  and the 64-update ack window (`MediaAckWindow`).
- **The lane vocabulary** (`mlp.lifecycle`, `mlp.resume`, `mlp.input`): the
  ten wire states, the close codes, the unsupported reasons; the park table
  with the TTL floor/ceiling; the pressed-set input sequencing.
- **Helpers** (`mlp.flow`, `mlp.loss`, `mlp.pacer`, `mlp.qos`, `mlp.ticket`,
  `mlp.migration`, `mlp.probe`, `mlp.metrics`): flow-control credit windows,
  gap-based loss detection, the token-bucket pacer with its reserved rate,
  QoS tiers, 0-RTT tickets, path migration and probing, the eight
  Prometheus counters.

## What it does not implement (yet)

The pacing machines, the bandwidth estimator, the repair plans and the
scheduler's priority bands are the Rust machine's. The package exposes no
placeholder for any of them.

## Test

```sh
python3 -m pytest -q
```

The conformance test parses and re-encodes every vector in
`mlp/conformance/vectors.json` — the same corpus `mlp-core`, `mlp-go` and
`mlp-c` test against — and fails on the first byte of drift.
