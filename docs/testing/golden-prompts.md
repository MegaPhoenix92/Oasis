# M1 Golden Prompt Suite

The canonical M1 prompt corpus lives at
`tests/fixtures/golden_prompts_m1.json`. It is the stable input set for Gate 1->2
acceptance and future real-provider viability runs.

The suite is deliberately mock-only in CI. Each entry has a stable `prompt_id` so 0002
section 5 telemetry from future runs can attach latency, import success, placement
success, completion, and subjective quality evidence without changing the corpus.

Categories covered:

- `simple`: single common objects with easy geometry.
- `stylized`: prompts where style should survive in the 0002 `Spec` and Meshy prompt.
- `complex`: multi-part props and structures that test decomposition.
- `terrain_large`: larger scene objects that stress dimensions and placement.
- `edge`: transparent, thin, tiny, or ambiguous prompts that should still produce a
  schema-valid `Spec`.

The fixture is not a real Claude or Meshy run. The mock harness in
`tests/test_golden_prompts.py` validates that each prompt can pass through `/spec` as a
schema-valid 0002 section 2 `Spec` with the expected object type and plausible dimensions.
The deferred real-provider run should fill the per-prompt `acceptance_metrics` values.
