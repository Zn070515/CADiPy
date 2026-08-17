# P1 Design: Persistent Sketch Entity Runtime and Parametric Sketch Core

## Status

Approved for implementation on the `feat/parametric-sketch-core` branch.

This phase extends the accepted Persistent Session and Live Target Runtime baseline. It does not replace that baseline and does not introduce a second execution model.

## Objective

CADiPy must be able to address a specific sketch, sketch entity, relation, and dimension as stable serializable engineering values, then resolve those values again after rebuild and after a save/close/reopen cycle. Public operations must describe sketch intent in engineering units and must not expose SOLIDWORKS COM objects or depend on uncontrolled UI selection state.

The phase establishes the identity and parameterization contract needed by later feature families. It is not a broad geometry catalogue.

## Scope

The current implementation scope is:

- sketch creation and inspection for a Part document;
- line, rectangle, circle, and center/start/end arc creation;
- serializable sketch, entity, relation, and dimension handles;
- persistent references encoded as base64 strings at the public boundary;
- horizontal, vertical, coincident, parallel, perpendicular, tangent, and concentric relations where the installed SOLIDWORKS capability supports them;
- distance, horizontal distance, vertical distance, radius, and diameter dimensions using millimetres;
- dimension value modification using millimetres;
- entity and dimension inspection after explicit resolution;
- a strict real-SOLIDWORKS parameterized sketch round-trip contract;
- one authoritative OpSpec registry consumed by Python API, RPC, and MCP adapters.

The existing `part.create_rectangular_extrude` contract remains intact as a regression fixture. Its rectangle-specific `GeometryHandle` is retained for compatibility while the new `SketchEntityHandle` becomes the composable sketch contract.

## Non-goals

This phase does not implement:

- fillet, chamfer, cut, revolve, sweep, loft, pattern, assembly, mate, drawing, motion, or configuration automation;
- a C# worker implementation;
- raw COM passthrough or public live COM references;
- an arbitrary selection or macro execution endpoint;
- automatic recovery by entity ordinal, name suffix, or nearest geometric match;
- a claim that a persistent reference is valid after deletion or every topology-changing edit.

## Execution boundary

The public and protocol layers depend on `SolidWorksExecutor` semantic methods. The Python COM executor owns all COM objects and temporary selections. A future C# worker can implement the same semantic port without changing public operation names, units, result values, or error codes.

The only selection allowed inside the COM backend is operation-local selection of already-resolved COM entities for SOLIDWORKS APIs that require selected objects. The backend must clear its temporary selection set and must never make current UI focus the identity source.

## Public domain values

All values are frozen, serializable dataclasses or enums. They contain no COM object and no SOLIDWORKS internal unit.

### SketchHandle

`SketchHandle` contains:

- session-local `id`;
- owning `document_id`;
- display `name`;
- requested plane name;
- optional base64 `persistent_ref` for the sketch feature.

The session-local ID is valid only while its owning session/executor is alive. The persistent reference is portable evidence for a later resolve in the same saved document; it is not a promise that a deleted or invalidated object can be recovered.

### SketchEntityHandle

`SketchEntityHandle` contains:

- session-local `id`;
- `document_id` and `sketch_id`;
- `entity_type` from `point`, `line`, `circle`, or `arc`;
- base64 `persistent_ref`;
- optional engineering-unit inspection fields such as endpoints, center, and radius.

The identity-bearing fields are the owning sketch and persistent reference. `id` is a convenient session handle and cannot be used to reconstruct an entity after the session registry is gone.

### RelationHandle and DimensionHandle

Relations contain a session-local ID, owning sketch ID, relation type, and ordered entity IDs. Dimensions contain a session-local ID, owning sketch ID, dimension type, display name, value in millimetres, and an optional persistent reference when SOLIDWORKS exposes one. In the verified SOLIDWORKS 2026 late-bound runtime, sketch dimensions are resolved by their SOLIDWORKS parameter name and that name is required to belong to the requested sketch. This is an explicit dimension identity rule, not an arbitrary name fallback. Relation and dimension entity references are validated before execution.

Public dimension values are always `*_mm` for length/radius/diameter contracts. Angles are not part of the first dimension contract. No public CADiPy sketch API accepts SOLIDWORKS metres or radians.

## Persistent-reference policy

The SOLIDWORKS 2026 API exposes `GetPersistReference3` and `GetObjectByPersistReference3`. The Python COM adapter stores the returned byte array as base64 and reconstructs a COM SafeArray only inside the backend. The resolve call passes the explicit error-code out parameter and treats all non-success states or null objects as `entity_reference_invalid`.

Each entity handle also carries the owning sketch persistent reference when SOLIDWORKS provides it. On resolution the backend verifies that the entity reference is one of the resolved sketch's current segment references; a reference from another sketch in the same Part is rejected. `document_id` and `sketch_id` remain session handles and are not treated as sufficient cross-session identity.

The backend must never fall back to:

- sketch segment order;
- feature-tree position;
- entity name guessing;
- current selection;
- a geometrically similar candidate.

After a rebuild, the backend may refresh its private COM cache from persistent references. After close/reopen, callers must provide the reopened document target plus the serialized persistent reference; an old session-local document or entity ID is not silently rebound.

## Operation contracts

The following operations are added to the authoritative registry. Each operation uses the existing document target binding. Sketch/entity/dimension references are parameters and are resolved exactly once inside the operation before any COM mutation.

| Operation | Target | Parameters | Result |
| --- | --- | --- | --- |
| `sketch.create` | Part document | `plane` | `SketchHandle` |
| `sketch.list` | Part document | none | tuple of `SketchHandle` |
| `sketch.inspect` | Part document | sketch reference | `SketchInspection` |
| `sketch.add_line` | Part document | sketch reference, `start_x_mm`, `start_y_mm`, `end_x_mm`, `end_y_mm` | `SketchEntityHandle` |
| `sketch.add_rectangle` | Part document | sketch reference, `width_mm`, `height_mm`, optional origin | four line entity handles |
| `sketch.add_circle` | Part document | sketch reference, center, `radius_mm` | `SketchEntityHandle` |
| `sketch.add_arc` | Part document | sketch reference, center, start/end points, direction | `SketchEntityHandle` |
| `sketch.add_relation` | Part document | sketch reference, relation type, ordered entity refs | `RelationHandle` |
| `sketch.add_dimension` | Part document | sketch reference, dimension type, entity refs, `value_mm`, dimension placement | `DimensionHandle` |
| `sketch.set_dimension` | Part document | dimension reference, `value_mm` | updated `DimensionHandle` |
| `sketch.inspect_entity` | Part document | sketch reference, entity reference | `SketchEntityInspection` |
| `sketch.inspect_dimension` | Part document | sketch reference, dimension reference | `DimensionInspection` |

The exact parameter schema is defined once in `operations/registry.py` and is tested against dispatch, RPC, and MCP adapter exposure. Adapter-specific aliases are not permitted.

## Relation and dimension semantics

The backend resolves every referenced entity, clears the document selection list, selects only those resolved objects with operation-specific marks, invokes the verified SOLIDWORKS relation/dimension API, and reads the created relation or dimension back. A COM call returning without an exception is insufficient: the returned handle must contain an observable relation or parameter name/value.

If a relation is redundant, unsupported, ambiguous, or rejected by the sketch solver, the backend returns a stable CADiPy domain error with the SOLIDWORKS diagnostic retained internally. It does not report a successful relation merely because selection succeeded.

`set_dimension` resolves the exact dimension parameter and sets its value in metres only inside the backend after converting from the public millimetre value. The public result and inspection remain in millimetres.

## Long-term golden contract

The P1 strict fixture performs this sequence against SOLIDWORKS 2026 SP3.2 revision 34.3.2:

1. launch an owned SOLIDWORKS instance;
2. create a Part and a Front Plane sketch;
3. create four independent lines for a 100 x 60 mm rectangle;
4. add horizontal, vertical, coincident, and origin-anchor relations;
5. add 100 mm horizontal and 60 mm vertical dimensions;
6. inspect entities, relations, dimensions, and solver state;
7. rebuild and verify actual model state;
8. extrude 3 mm through the existing semantic feature boundary;
9. save a temporary SLDPRT;
10. close and reopen it;
11. resolve the sketch, all four entities, and both dimensions from persisted references;
12. verify the same relations/dimensions and the 100 x 60 x 3 mm solid state;
13. set the horizontal dimension to 120 mm;
14. rebuild and verify the actual bounding box is approximately 120 x 60 x 3 mm;
15. close the owned test document and owned SOLIDWORKS process.

The fixture is a long-term real-SOLIDWORKS integration contract, not a demo. In ordinary environments it may skip when SOLIDWORKS is absent. When `CADIPY_REQUIRE_REAL_SOLIDWORKS=1`, missing SOLIDWORKS, COM failure, unsupported capability, creation failure, verification failure, or round-trip failure must fail the test.

## Testing layers

Pure tests cover serialization, unit validation, operation schema, error mapping, target/reference validation, and deterministic dispatch using a semantic fake executor. They do not pretend to prove COM behavior.

Backend tests cover SafeArray/base64 conversion, invalid-reference handling, temporary selection discipline, and semantic result mapping with narrow boundary doubles.

Real tests cover line/circle/arc creation, relation and dimension postconditions, persistent references through save/reopen, dimension mutation, and the full golden contract. The integration fixture must record the observed SOLIDWORKS version and leave no generated CAD binary in the repository.

## Verified API evidence

The implementation is based on local SOLIDWORKS 2026 COM probing plus the official API references:

- [Persistent Reference IDs](https://help.solidworks.com/2026/English/api/sldworksapiprogguide/Overview/Persistent_Reference_IDs.htm)
- [GetPersistReference3](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetPersistReference3.html)
- [GetObjectByPersistReference3](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetObjectByPersistReference3.html)
- [CreateLine](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchManager~CreateLine.html)
- [SketchManager methods](https://help.solidworks.com/2026/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isketchmanager_methods.html)
- [SketchAddConstraints](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~SketchAddConstraints.html)
- [AddDimension2](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~AddDimension2.html)

The local probe specifically established that Python COM must pass a `VT_ARRAY | VT_UI1` SafeArray and a by-reference integer error value to `GetObjectByPersistReference3`; this behavior is covered by backend tests and the strict fixture.
