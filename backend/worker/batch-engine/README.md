# Batch engine (TypeScript): reference only

This TypeScript engine is not deployed. The batch engine that runs is the Python port in
`backend/worker/app/batching/engine.py` (task 43). This code is kept as the reference the port is tested against:

- `tests/*.test.ts` are ported one for one to `backend/worker/tests/test_batching.py`;
- `tests/parity.ts` prints this engine's results for fixed scenarios, saved as
  `backend/worker/tests/fixtures/batch_parity.json`, which the Python must reproduce:

```sh
docker run --rm -v "$PWD/backend/worker/batch-engine:/e" -w /e node:24-slim sh -c \
  'LOG_LEVEL=silent npx -y tsx@4.19.2 tests/parity.ts' | sed -n '/^{/,$p' | grep -v '^\[20' > backend/worker/tests/fixtures/batch_parity.json
```

Change the engine in Python. If you change it here too (to keep the reference meaningful), regenerate the fixture.
See docs/BATCH_ENGINE_TECHNICAL_DESIGN.md (the note at the top).
