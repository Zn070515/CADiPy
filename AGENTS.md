# CADiPy Agent Instructions

## 1. Project Identity

**CADiPy** is a production-oriented, long-lived CAD automation library and agent runtime.

Its primary target is SOLIDWORKS on Windows. It exposes stable Python-facing APIs and agent-facing operation contracts while isolating SOLIDWORKS-native execution behind well-defined backend boundaries.

This repository is derived from a mature automation-engineering template. The template is not disposable scaffolding. Its engineering disciplines—schema-driven interfaces, domain errors, strict target binding, regression testing, documentation synchronization, CI quality gates, security review, release discipline, and real-application verification—are intentional foundations that must be preserved and adapted to CAD automation.

Treat CADiPy as software intended to become:

* a maintained open-source Python package;
* a dependable automation runtime for real SOLIDWORKS documents;
* a library usable by both humans and AI agents;
* a multi-language system where Python owns the public/control plane and C# may own SOLIDWORKS-native execution;
* a system whose correctness must be demonstrated against real CAD state, not inferred from successful API calls;
* an architecture capable of evolving beyond a collection of scripts.

Do not reduce the project to a collection of convenience wrappers.

Do not optimize for the smallest amount of code at the expense of architectural integrity, safety, diagnostics, testability, compatibility, or future maintenance.

A task may have a narrow scope. **The quality standard is never narrow.**

---

## 2. Current Primary Environment

Primary development environment:

* Windows 11 x64
* SOLIDWORKS 2026 SP3.2
* SOLIDWORKS revision observed through COM: `34.3.2`
* Python development baseline: Python 3.12
* Environment/package management: `uv`
* .NET SDK 9 is installed locally
* MSVC / Visual Studio 2022 Build Tools are available
* PowerShell 7 is the preferred shell

SOLIDWORKS COM is already known to be reachable through:

```python
import win32com.client

sw = win32com.client.Dispatch("SldWorks.Application")
```

Do not hard-code the local SOLIDWORKS installation directory when the COM registration, type library, registry, or official API provides a stable discovery mechanism.

Do not assume that the presence of .NET 9 means every C# project should target `.NET 9`.

For SOLIDWORKS C# integration:

* determine target frameworks from actual SOLIDWORKS compatibility requirements;
* inspect official SOLIDWORKS API documentation and local interop assemblies;
* use modern .NET for an out-of-process worker only when interoperability is verified;
* follow the officially supported target/runtime model for any in-process SOLIDWORKS Add-in;
* do not force an Add-in onto a modern runtime merely because the SDK is installed.

---

# 3. Architecture Direction

CADiPy has four conceptual layers.

```text
Human / AI Agent
        │
        ▼
┌─────────────────────────────┐
│ Python Public / Control API │
│                             │
│ schema / IR / client        │
│ target safety               │
│ audit / verification        │
└──────────────┬──────────────┘
               │
       deterministic protocol
               │
               ▼
┌─────────────────────────────┐
│ SOLIDWORKS Execution Plane  │
│                             │
│ Python COM backend and/or   │
│ C# Worker / Core library    │
└──────────────┬──────────────┘
               │
         SOLIDWORKS COM
               │
               ▼
          SOLIDWORKS
```

The intended responsibility split is:

### Python

Python owns:

* public user API;
* Python package distribution;
* operation schema;
* CAD-oriented intermediate representations;
* validation;
* agent orchestration;
* protocol client;
* target identification;
* audit trail;
* high-level verification;
* CLI;
* MCP or other agent integrations;
* compatibility reporting;
* environment diagnostics.

### C#

C# is a native SOLIDWORKS execution backend, not a replacement for CADiPy's Python identity.

Expected C# responsibilities may include:

```text
Cadipy.SolidWorks.Core
    deterministic SOLIDWORKS API wrappers

Cadipy.SolidWorks.Worker
    out-of-process execution host
    RPC / named-pipe / equivalent transport
    COM lifecycle and threading ownership

Cadipy.SolidWorks.Addin
    only when in-process SOLIDWORKS behavior is genuinely required
    events / Task Pane / menus / in-process-only APIs
```

Do not make `pythonnet` + direct in-process DLL loading the architectural default.

A direct Python-to-DLL bridge may be useful for experiments or tightly constrained functionality, but the long-term system boundary should favor process isolation when it improves:

* COM apartment ownership;
* crash isolation;
* CLR/Python lifecycle separation;
* restartability;
* diagnostics;
* compatibility management;
* recoverability.

Do not introduce C# merely to rewrite working Python code. Move responsibilities into C# when SOLIDWORKS-native behavior, threading, interoperability, performance, process isolation, or maintainability justifies it.

---

# 4. The Agent Must Not Guess SOLIDWORKS APIs

SOLIDWORKS API signatures, enums, units, COM behavior, object lifetime, return values, error conventions, version support, and feature semantics must not be invented from memory.

Before implementing or modifying a SOLIDWORKS-facing operation:

1. inspect the existing repository implementation and tests;
2. inspect the relevant SOLIDWORKS 2026 official API documentation;
3. inspect local interop/type information where useful;
4. verify ambiguous behavior against a real SOLIDWORKS instance;
5. encode the discovered behavior in tests and/or documentation.

Prefer primary sources:

* official SOLIDWORKS API Help;
* official SOLIDWORKS programming guides;
* local SOLIDWORKS interop assemblies;
* registered COM type libraries;
* official examples.

Third-party repositories may be used for comparison and research, but never override verified official behavior without evidence.

If documentation and runtime behavior disagree, record the discrepancy and write a regression test against the actual supported environment.

Never silently guess:

* enum integer values;
* length units;
* angle units;
* coordinate frames;
* feature argument order;
* selection marks;
* object persistence;
* return-code meaning;
* thread requirements;
* document types;
* rebuild semantics.

---

# 5. Template Migration Discipline

This repository originated from a mature automation-engineering template.

Do not perform a blind global search-and-replace when adapting inherited material to CADiPy.

Inherited content must be audited semantically.

Classify inherited components as:

```text
KEEP
    generic engineering infrastructure that applies unchanged

ADAPT
    good inherited infrastructure whose domain semantics must become CAD-specific

REMOVE
    document-application-specific functionality with no CAD responsibility
```

Likely candidates:

### Preserve/adapt

* `src/` layout
* `tests/`
* `docs/`
* `examples/`
* `scripts/`
* `.github/workflows/`
* `pyproject.toml`
* `uv.lock`
* `README`
* `CONTRIBUTING`
* `SECURITY`
* `CHANGELOG`
* compatibility documentation
* deprecation policy
* migration documentation
* protocol documentation
* schema consistency philosophy
* domain exception hierarchy
* CI gates
* release discipline
* GitHub security workflows
* real-application integration tests

### Remove or redesign

* non-CAD document-application code
* presentation conversion/audit/art subsystems
* non-CAD server semantics
* non-CAD examples
* non-CAD vendored dependencies
* non-CAD documentation
* non-CAD workflow names
* third-party notices for dependencies that are no longer distributed

Before committing a repository conversion, search comprehensively for inherited terminology and product names:

```powershell
rg -n -i "legacy-product-name|legacy-document-application-name"
```

Every surviving occurrence must be intentional, and the public CADiPy tree should contain none.

Do not delete mature generic infrastructure merely because it originated in an earlier project.

---

# 6. Public API Philosophy

The public API should describe **engineering intent**, not expose raw COM mechanics.

Bad abstraction:

```python
sw.SelectionManager.GetSelectedObject6(...)
sw.Extension.SelectByID2(...)
sw.FeatureManager.FeatureExtrusion3(...)
```

Preferred direction:

```python
part.create_extrude(
    sketch="BaseSketch",
    depth=3.0,
    unit="mm",
)
```

or a schema operation such as:

```json
{
  "op": "part.create_extrude",
  "target": {
    "document_id": "part_..."
  },
  "params": {
    "sketch": "BaseSketch",
    "depth_mm": 3.0
  }
}
```

Raw SOLIDWORKS details belong behind backend/compiler/execution boundaries unless exposing them is necessary for advanced escape-hatch APIs.

Prefer semantic selectors over transient COM objects.

For example, avoid persisting a raw `Face2` object across rebuilds when the intended reference can be represented as:

```json
{
  "feature": "Boss-Extrude1",
  "selector": "largest_planar_face",
  "normal": "+Z"
}
```

Selectors must be deterministic, explainable, testable, and fail loudly when ambiguous.

Never silently choose an arbitrary entity because several candidates match.

---

# 7. Single Source of Truth for Operations

Preserve the template's schema-driven philosophy.

There should be one authoritative operation registry/schema from which agent-facing surfaces are derived.

An operation definition should eventually be able to describe at least:

* operation name;
* description;
* parameters;
* parameter types;
* return contract;
* read-only vs mutating;
* target requirements;
* destructive severity;
* supported document types;
* capability/version requirements;
* verification expectations;
* whether rebuild is required;
* whether operation participates in a transaction;
* errors that may be produced.

Conceptual example:

```python
OpSpec(
    name="part.create_extrude",
    readonly=False,
    destructive=True,
    document_types={"part"},
    requires_target=True,
    rebuild=True,
    ...
)
```

Python API, CLI, RPC, MCP, documentation stubs, and validation logic should derive from the same contract wherever practical.

Do not maintain manually duplicated operation lists across multiple entry points.

Schema consistency must be regression-tested.

---

# 8. Target Safety Is a Core Requirement

CAD automation can successfully modify the wrong model. That is more dangerous than a call simply failing.

Every mutating operation must operate on an explicitly resolved target.

Do not make UI focus the authoritative identity.

A future target contract should support information such as:

```json
{
  "document_id": "...",
  "path": "...",
  "title": "...",
  "document_type": "part",
  "configuration": "Default"
}
```

For important mutations, consider additional identity evidence where appropriate:

* file path;
* document type;
* configuration;
* assembly identity;
* revision/fingerprint;
* expected feature;
* expected document state.

Follow a resolve-once discipline:

```text
validate expected target
        ↓
resolve authoritative document object
        ↓
execute against that resolved object
```

Never:

```text
check document A
        ↓
look at UI again
        ↓
accidentally mutate document B
```

Read operations may support current-active-document semantics where safe and explicit.

Mutations must not silently follow focus unless the caller explicitly requests such behavior.

---

# 9. Transaction and Undo Discipline

A group of operations representing one logical CAD change should be treated as a transaction when SOLIDWORKS capabilities permit it.

The architecture should support:

```text
begin logical CAD transaction
        ↓
perform deterministic operations
        ↓
rebuild
        ↓
verify
        ↓
commit
```

and:

```text
begin logical CAD transaction
        ↓
operation fails or verification fails
        ↓
rollback / undo / restore known state
```

Do not claim atomicity unless actual runtime behavior proves it.

If complete rollback cannot be guaranteed, expose the real semantics honestly.

Before destructive workflows, consider:

* save state;
* working copy;
* undo record;
* document dirty state;
* recovery metadata.

Rollback behavior itself must have integration tests.

---

# 10. COM Lifetime and Threading

COM behavior is an architectural concern, not an implementation detail.

Rules:

* explicitly control COM initialization where required;
* document STA/MTA assumptions;
* never casually pass live COM objects between arbitrary Python threads;
* do not serialize COM objects across RPC;
* return stable domain data instead;
* avoid retaining transient geometry objects longer than necessary;
* reacquire entities after rebuild when object stability is not guaranteed;
* keep ownership of SOLIDWORKS application/document references explicit;
* release or invalidate stale references deliberately.

When the C# worker is introduced, it should own a predictable SOLIDWORKS/COM execution context and serialize operations as required by the chosen architecture.

Do not hide threading violations behind retries.

---

# 11. Units and Geometry

CADiPy must have an explicit unit policy.

Never scatter implicit conversions throughout backend code.

Public APIs should favor explicit engineering units such as:

```python
depth_mm=3.0
angle_deg=45.0
```

or typed unit objects if adopted later.

Internal SOLIDWORKS API units must be normalized through a centralized conversion layer.

Tests must cover unit conversion.

Never assume a value such as `3` means:

* 3 metres;
* 3 millimetres;
* 3 inches;
* 3 radians;
* 3 degrees.

Coordinate systems must also be explicit.

If an operation depends on:

* sketch plane coordinates;
* model coordinates;
* assembly coordinates;
* component transform;
* local feature coordinates;

the contract and implementation must make that space clear.

---

# 12. Rebuild Is Not Verification

A successful COM call does not prove success.

A successful SOLIDWORKS rebuild does not prove engineering correctness.

Verification should become a distinct subsystem.

Depending on the operation, verification may include:

* document still exists and is of expected type;
* requested feature exists;
* feature is unsuppressed;
* feature parameters match requested values;
* rebuild succeeds;
* sketch is fully defined when required;
* expected dimensions exist;
* body count matches expectation;
* bounding box is plausible;
* mass/volume is plausible;
* assembly component count is correct;
* mate state is valid;
* no unexpected dangling references exist;
* interference check passes when required;
* expected motion range is possible;
* export artifact exists and can be reopened.

The library should eventually distinguish:

```text
API call succeeded
feature created
model rebuilt
verification passed
```

These are different states.

Do not collapse them into a single `"ok"` result.

---

# 13. Error Model

Never leak arbitrary backend failures as the public error contract.

Create a CADiPy domain exception hierarchy.

Expected categories may include:

```text
CadipyError
├── InvalidArgumentError
├── UnsupportedPlatformError
├── UnsupportedVersionError
├── CapabilityUnavailableError
├── TargetNotFoundError
├── TargetMismatchError
├── AmbiguousSelectionError
├── DocumentTypeError
├── FileConflictError
├── SolidWorksNotAvailableError
├── ComOperationError
├── RebuildError
├── VerificationError
├── TransactionError
├── WorkerError
└── ProtocolError
```

Preserve backend diagnostics internally:

* HRESULT;
* SOLIDWORKS return code;
* worker error;
* operation name;
* target identity;
* relevant feature name.

Public errors must remain readable and machine-identifiable through stable `error_code` values.

Do not expose absolute private paths, secrets, raw tracebacks, or unrelated process/environment data over RPC.

---

# 14. Python / C# Protocol

When the C# execution host exists, Python and C# communicate through a versioned protocol.

The protocol must not transmit live COM objects.

Use serializable domain values.

Conceptual request:

```json
{
  "protocol": 1,
  "id": "request-id",
  "operation": "part.create_extrude",
  "target": {
    "document_id": "part_..."
  },
  "params": {
    "sketch": "BaseSketch",
    "depth_mm": 3.0
  }
}
```

Conceptual response:

```json
{
  "protocol": 1,
  "id": "request-id",
  "ok": true,
  "data": {
    "feature": "Boss-Extrude1",
    "rebuild": "ok",
    "verification": "passed"
  }
}
```

Protocol changes require:

* version consideration;
* compatibility tests;
* documentation;
* migration notes if externally observable.

Python and C# implementations must have cross-language contract tests.

---

# 15. SOLIDWORKS Worker Rules

The out-of-process worker is a reliability boundary.

It should eventually provide:

* deterministic startup;
* explicit protocol/version handshake;
* SOLIDWORKS version reporting;
* PID/process ownership;
* graceful shutdown;
* crash detection;
* reconnect behavior;
* structured logs;
* request IDs;
* bounded request/response sizes;
* timeouts;
* no arbitrary code execution endpoint;
* operation whitelist derived from schema where practical.

If a worker cannot prove ownership of a process, it must not kill it.

Do not implement generic:

```text
eval
exec
run arbitrary C#
run arbitrary COM expression
```

as public agent tools.

AI agents receive constrained engineering operations, not an unrestricted code execution bridge.

---

# 16. Add-in Rules

Do not create an in-process SOLIDWORKS Add-in merely because Add-ins are possible.

Introduce one when requirements need capabilities such as:

* SOLIDWORKS event subscriptions;
* document lifecycle events;
* selection events;
* rebuild notifications;
* Task Pane UI;
* commands/menus;
* APIs that require in-process execution;
* low-latency state synchronization.

The Add-in must remain a backend component.

It must not become a second independent business-logic implementation competing with the Python API and Worker.

Common contracts belong in shared protocol/core layers.

---

# 17. Branch Discipline

`main` is protected by process even if GitHub branch protection is not configured.

All feature, fix, documentation, build, dependency, refactor, and CI work must happen on a branch.

This repository does not use Git worktrees for development. All subsequent work must be performed directly in the repository root: switch to `main`, update it, and create the new branch from `main` in the root directory. Do not create project copies under `.worktrees/`.

Naming:

```text
feat/<short-name>
fix/<short-name>
docs/<short-name>
build/<short-name>
refactor/<short-name>
```

Before creating a branch:

```powershell
git status
git checkout main
git pull --ff-only
git checkout -b <branch>
```

Do not mix unrelated work into one branch.

Do not commit directly to `main` unless the user explicitly authorizes an emergency repair.

Before merge:

* inspect `git status`;
* inspect `git diff`;
* run all applicable gates;
* confirm documentation;
* confirm no generated junk or CAD output accidentally entered Git;
* merge with explicit history or PR according to repository policy.

After the applicable gates pass, completed work must be integrated directly without
creating a pull request unless the user explicitly overrides this rule:

* commit the focused change on the feature branch;
* fast-forward merge the feature branch into `main`;
* run the merged-result gates;
* push `main` to `origin` over SSH;
* delete the completed local feature branch and leave the working tree on `main`;
* do not leave completed work waiting on a feature branch or pull request.

Commits should be focused.

Preferred prefixes:

```text
feat:
fix:
docs:
build:
refactor:
test:
chore:
```

Version bumps must remain separate from functional commits.

---

# 18. Development Commands

Use `uv` for Python.

Typical Python gates:

```powershell
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/cadipy
uv run pytest tests -q
uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q
```

If repository configuration changes these commands, follow repository configuration rather than maintaining duplicate rules here.

For .NET projects:

```powershell
dotnet restore
dotnet build
dotnet test
```

Do not report success unless the commands actually completed successfully.

Do not suppress failing tests to obtain a green run.

---

# 19. Test Architecture

Tests should be divided by what they prove.

## Pure tests

Run without SOLIDWORKS where possible:

* schema validation;
* unit conversion;
* IR validation;
* selectors;
* protocol serialization;
* error mapping;
* compatibility logic;
* target matching;
* deterministic geometry/planning logic;
* worker protocol parsing;
* security limits.

These should be suitable for normal CI.

Portable modules must maintain a line-coverage gate of at least 85% across
domain, operations, protocol, verification, diagnostics, and audit. The gate
must not count COM mocks as evidence of SOLIDWORKS compatibility.

## Mock/fake boundary tests

Mocks are useful only for testing our code around the integration boundary.

Mocks do **not** prove SOLIDWORKS compatibility.

Never claim a COM operation works because a mocked COM object accepted the method.

## Real SOLIDWORKS integration tests

Real tests should verify important operations against an installed SOLIDWORKS instance.

Examples:

```text
connect
create document
create sketch
create feature
rebuild
read feature back
save
close
reopen
verify
```

Tests must clean up documents and processes they own.

Do not kill unrelated user SOLIDWORKS processes.

## Golden CAD fixtures

Use carefully designed CAD fixtures for regression tests.

Fixtures should record:

* SOLIDWORKS version;
* expected feature tree;
* expected dimensions;
* expected body/component count;
* expected verification result.

Do not commit enormous generated CAD artifacts without a reason.

If binary fixtures become necessary, establish an explicit repository/LFS policy before accumulating them.

---

# 20. Real Application Verification

Any change to SOLIDWORKS-facing behavior is incomplete until tested against real SOLIDWORKS when the local environment permits.

For every verified operation, confirm observable postconditions.

Example:

```text
create rectangle
    is not enough

create rectangle
    ↓
query sketch entities
    ↓
verify dimensions/coordinates
```

Example:

```text
create extrude
    is not enough

create extrude
    ↓
rebuild
    ↓
read resulting feature
    ↓
check depth/body
```

Never validate solely by looking at the SOLIDWORKS window.

UI screenshots may provide supporting evidence but should not be the authoritative correctness mechanism when API state is available.

---

# 21. Process Cleanup

Automated tests must leave the machine in a known state.

Track whether CADiPy:

* connected to an existing SOLIDWORKS process;
* launched its own process.

If CADiPy launched the process and owns it, it may shut it down according to the test policy.

If it connected to a user-owned process, do not terminate it without explicit authorization.

At integration-test cleanup:

* close test documents;
* discard or save intentionally;
* stop owned workers;
* release COM references;
* confirm owned test processes exited;
* remove temporary artifacts.

Never use indiscriminate:

```powershell
taskkill /F /IM SLDWORKS.exe
```

as routine cleanup.

Process termination requires ownership evidence.

---

# 22. Security Model

An agent capable of controlling SOLIDWORKS can modify or destroy valuable design data.

Security and safety are core architecture.

Required principles:

* bind local servers to loopback by default;
* authenticate local RPC if a persistent server is used;
* whitelist operations;
* reject arbitrary execution;
* limit payload sizes;
* validate file paths;
* normalize paths;
* protect against accidental overwrite;
* require explicit overwrite semantics;
* never expose secrets in logs;
* avoid leaking full private filesystem paths remotely;
* reject malformed or oversized protocol payloads;
* identify target documents before mutation;
* classify destructive operations;
* provide dry-run/planning capability where meaningful.

A token that grants CAD control must be treated as sensitive.

---

# 23. File Safety

Opening a model is not permission to overwrite it.

Mutating and persistence are separate concepts.

File operations must make behavior explicit:

```text
open
modify in memory
save
save as
overwrite
close without save
```

Never overwrite an existing model simply because the desired output path already exists.

Require an explicit `overwrite=True` or equivalent contract.

For generated artifacts, prefer atomic/staged writes where practical.

Tests must cover file conflicts.

---

# 24. Compatibility Policy

Compatibility claims must distinguish:

```text
Tested
Expected
Unsupported
```

Primary current test baseline:

```text
SOLIDWORKS 2026 SP3.2
Revision 34.3.2
Windows x64
Python 3.12
```

The current compatibility evidence distinguishes the following:

* Python 3.10, 3.11, 3.12, and 3.13: portable test matrix tested;
* Python 3.12 with SOLIDWORKS 2026 SP3.2 revision 34.3.2: real contract tested;
* other Python/SOLIDWORKS combinations: not validated unless separately evidenced.

Do not claim support for another SOLIDWORKS release merely because APIs appear similar.

Adding a supported SOLIDWORKS version requires evidence.

Feature-level capabilities should be detectable where version differences matter.

Avoid version checks such as:

```python
if version >= X:
```

when capability detection can provide a more robust contract.

Version-specific behavior must have compatibility documentation.

---

# 25. Documentation Is Part of the Change

Code changes and documentation cannot drift.

Maintain documentation for:

* installation;
* environment diagnostics;
* Python API;
* protocol;
* schema;
* errors;
* target semantics;
* compatibility;
* C# worker;
* Add-in architecture if introduced;
* security;
* migration;
* deprecation;
* examples;
* benchmarks where meaningful.

If generated API documentation exists, update its source and regenerate it.

Do not manually modify generated files without modifying their source.

Behavioral changes require documentation in the same development cycle.

Breaking or materially changed behavior requires migration guidance.

CHANGELOG entries must describe externally meaningful effects rather than internal implementation trivia.

---

# 26. Internal Research Documents

Separate public documentation from internal engineering notes.

Public documentation belongs in tracked `docs/`.

Formal design specifications and implementation plans in `docs/superpowers/`
are public engineering history and must be curated before commit. Curated,
public evidence may be kept in `docs/development/`. Temporary scratch
analysis, unedited reasoning, and private plans belong in ignored local files.

Do not accidentally publish:

* private local paths;
* serial numbers;
* license keys;
* machine-specific secrets;
* debugging dumps containing sensitive information;
* temporary screenshots that reveal unrelated files.

Never commit SOLIDWORKS serial numbers or license information.

---

# 27. Dependencies

Add dependencies deliberately.

Before adding one, evaluate:

* why it is needed;
* maintained status;
* license;
* Windows support;
* Python version support;
* binary footprint;
* security history;
* whether the standard library or current dependencies already solve the problem.

Do not add a large framework for a small utility.

Do not vendor third-party code without:

* explicit reason;
* license review;
* provenance;
* THIRD_PARTY_NOTICES updates;
* update strategy.

For C# packages, apply the same discipline to NuGet dependencies.

---

# 28. CI Direction

Preserve the template's layered CI philosophy.

Every third-party GitHub Action reference must use a full 40-character commit
SHA with a readable version comment. Floating tags such as `@v4` or `@main`
are not permitted. Dependabot updates must pass CI and receive diff review.

The repository should support separate classes of verification:

```text
portable/pure tests
        │
Windows tests
        │
Python compatibility
        │
.NET build/tests
        │
package/wheel smoke
        │
security checks
        │
real SOLIDWORKS integration
```

The portable Python matrix must cover 3.10 through 3.13. The real
SOLIDWORKS gate runs on the supported Python 3.12 self-hosted environment and
must fail rather than skip when strict mode is requested.

Real SOLIDWORKS tests may require a licensed self-hosted Windows runner.

Do not fake a real-SOLIDWORKS CI result on GitHub-hosted runners.

If the real application test cannot run in a given environment, mark that limitation explicitly rather than silently replacing it with mocks.

Release quality gates must distinguish:

```text
unit correctness
package correctness
protocol correctness
real SOLIDWORKS correctness
```

---

# 29. Release Discipline

Public releases must be reproducible and CI-driven.

Do not manually upload a package to PyPI to bypass a broken release workflow.

Expected release properties:

* version single source of truth;
* SemVer;
* tag matches package version;
* CHANGELOG matches package version;
* tests pass;
* wheel installs in a clean environment;
* import smoke passes;
* security workflow passes;
* real SOLIDWORKS gates pass when defined as required;
* release provenance/attestation preserved where supported.

Do not bump versions casually during ordinary development.

Version bumps should be separate commits.

---

# 30. API Stability and Deprecation

Do not break public APIs casually.

Before changing an existing public contract, determine whether the change can be additive.

When deprecation is appropriate:

* issue an explicit warning;
* document replacement;
* document migration;
* retain the old path for the documented support window;
* add tests covering the deprecation behavior.

Internal cleanup is not sufficient justification for breaking users.

---

# 31. Agent-Facing Tool Design

Agent tools should represent atomic, composable CAD operations.

Good:

```text
part.create_sketch
sketch.add_rectangle
sketch.add_dimension
part.create_extrude
assembly.insert_component
assembly.add_mate
document.rebuild
assembly.check_interference
document.save
```

Bad:

```text
execute_python
execute_csharp
invoke_com
run_macro_text
eval_expression
```

An AI model should choose from safe engineering verbs.

It should not receive unrestricted access to the backend runtime merely because unrestricted execution is easier to implement.

High-level orchestration belongs above atomic deterministic tools.

---

# 32. Do Not Confuse Automation With Engineering Intelligence

CADiPy provides automation primitives, structured state, verification, and safe execution.

Do not claim that the library has solved mechanical engineering merely because it can create geometry.

Distinguish:

```text
requested geometry created
```

from:

```text
design satisfies mechanical intent
```

and from:

```text
design is safe/manufacturable/optimal
```

Claims must be supported by actual evidence.

If CADiPy does not perform FEA, it must not imply structural safety.

If CADiPy only checks interference, say interference was checked.

Precise language matters.

---

# 33. Planning Discipline

For non-trivial work:

1. understand existing contracts;
2. inspect relevant code;
3. inspect tests;
4. inspect public documentation;
5. research external API behavior when needed;
6. identify compatibility/security implications;
7. write an implementation plan;
8. review the plan for architectural regressions;
9. implement;
10. verify;
11. update documentation;
12. review the final diff.

Plans must address downstream maintenance, not only immediate code generation.

Do not knowingly create architectural debt under the assumption that it will automatically be rewritten later.

At the same time, avoid speculative complexity unsupported by a real requirement.

The principle is:

> **Build only justified capabilities, but build justified capabilities properly.**

---

# 34. Bug-Fix Discipline

For a bug:

1. reproduce it;
2. identify the real root cause;
3. add a regression test that fails for the correct reason;
4. implement the fix;
5. run focused tests;
6. run broader affected gates;
7. validate against real SOLIDWORKS when applicable;
8. update docs if observable behavior changed.

Do not add retries, sleeps, broad exception catches, or arbitrary fallbacks until the failure mechanism is understood.

A workaround is acceptable only when:

* the underlying external limitation is known;
* the workaround has bounded behavior;
* it is documented;
* it has regression coverage.

---

# 35. Anti-Patterns

Do not introduce these without explicit architectural justification:

* giant monolithic `solidworks.py`;
* arbitrary COM passthrough as the main API;
* persistent raw COM objects in public return values;
* global mutable active-document state;
* silent target switching;
* silent unit conversion assumptions;
* magic enum integers scattered in code;
* bare `except Exception: pass`;
* broad retry loops around COM errors;
* `time.sleep()` as synchronization architecture;
* UI automation when an official API exists;
* screenshot-only correctness checks;
* direct main-branch development;
* manual duplicated API registries;
* manually maintained docs that can be generated from schema;
* unversioned Python↔C# protocol;
* unrestricted eval endpoints;
* killing arbitrary SOLIDWORKS processes;
* committing generated `.SLDPRT`, `.SLDASM`, STEP, STL, logs, screenshots, or temporary test files without explicit fixture intent;
* embedding machine-specific install paths in library logic;
* hard-coding the developer's serial number, user directory, or local environment.

---

# 36. Definition of Done

A change is not done because the code compiles.

A completed change should satisfy all applicable items:

* architecture remains consistent;
* target semantics are safe;
* operation is represented in the authoritative schema where applicable;
* domain errors are correct;
* unit conversions are explicit;
* pure tests exist;
* integration tests exist where needed;
* real SOLIDWORKS behavior has been verified where relevant;
* rebuild/postcondition verification exists;
* Python/C# contract remains synchronized;
* lint passes;
* formatting passes;
* type checking passes;
* Python tests pass;
* .NET tests/build pass where affected;
* documentation is synchronized;
* CHANGELOG is updated when appropriate;
* migration/deprecation docs are updated when appropriate;
* security implications were reviewed;
* no secrets or accidental binaries were added;
* final `git diff` contains only intended work.

If some validation cannot be executed, report exactly what was not verified and why.

Never state that a change is fully verified when only mocks or static inspection were performed.

---

# 37. Final Engineering Principle

CADiPy controls real engineering documents in a large stateful desktop application.

The project therefore prioritizes:

1. **correct target**
2. **correct operation**
3. **correct geometry/state**
4. **verifiable result**
5. **recoverability**
6. **stable public contract**
7. **maintainability**
8. **agent usability**

Convenience comes after these.

The goal is not merely to make SOLIDWORKS scriptable.

The goal is to provide a disciplined automation layer in which Python applications and AI agents can operate SOLIDWORKS through explicit contracts, constrained capabilities, deterministic execution, and evidence-backed verification.
