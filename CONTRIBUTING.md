# Contributing to CADiPy

CADiPy follows the repository contract in `AGENTS.md`. Changes must preserve explicit target binding, stable domain errors, schema-driven operations, backend isolation, verification evidence, and release hygiene.

Before implementation, inspect the relevant official SOLIDWORKS API Help and local type information. Do not infer signatures, enum values, coordinate frames, or units from memory. Write a failing test for new behavior, implement the smallest maintainable boundary, and run focused plus repository-level checks.

Typical checks:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src/cadipy
uv run pytest tests -q
uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q
```

Use the strict real-SOLIDWORKS gate for changes touching the COM backend or geometry contract. The test-owned documents and temporary paths are the only resources that may be closed or removed by the fixture.
