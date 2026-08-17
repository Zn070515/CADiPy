# CADiPy

CADiPy is a production-oriented SOLIDWORKS agent-automation project. Python owns the public API, OpSpec/schema, target safety, protocol adapters, diagnostics, audit, and verification. SOLIDWORKS execution details remain behind the replaceable `SolidWorksExecutor` boundary.

The current work scope includes a Python COM executor, a fixed long-term boundary for a future C# Worker, explicit public units, one operation registry shared by CLI/RPC/MCP, and a real SOLIDWORKS Part geometry contract.

```powershell
uv sync --extra dev
uv run pytest tests -q
uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q
uv run pytest tests/integration/solidworks -m solidworks -q
```

The strict real-SOLIDWORKS gate is:

```powershell
$env:CADIPY_REQUIRE_REAL_SOLIDWORKS = '1'
uv run pytest tests/integration/solidworks -m real_solidworks --real-solidworks -q
Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS -ErrorAction SilentlyContinue
```

See the [documentation](docs/index.en.md), [API](docs/api/index.en.md), [protocol](docs/protocol.en.md), and [compatibility matrix](docs/compatibility.en.md).

For multi-operation workflows on one SOLIDWORKS document, use a persistent session. `connect()` strictly attaches to an existing instance; `launch()` explicitly creates and owns a new one.

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
```
