# Contributing to CADiPy

Follow `AGENTS.md`: preserve explicit target binding, stable domain errors, schema-driven operations, backend isolation, verification evidence, and release hygiene.

Before changing a SOLIDWORKS-facing call, inspect official API Help and local type information. Do not infer signatures, enum values, coordinate frames, or units. Write a failing test first, implement the maintainable boundary, and run focused and repository-level checks.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src/cadipy
uv run pytest tests -q
uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q
```
