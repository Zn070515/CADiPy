# SOLIDWORKS API evidence used by CADiPy

This note records the API facts used by the Python COM backend. It is an
engineering record, not a substitute for the official API Help.

## Supported environment

- SOLIDWORKS observed through `Dispatch("SldWorks.Application")`: revision
  `34.3.2`.
- Python: `3.12.10` x64.
- `pywin32` is installed in the development environment.
- The live connection was read-only: the observed application was attached
  with `Visible == False`; CADiPy does not call `ExitApp` on a shared session.

## Verified official members

The following official SOLIDWORKS 2026 API Help pages were consulted:

- [ISldWorks.NewDocument](https://help.solidworks.com/2025/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~newdocument.html)
  takes `(TemplateName, PaperSize, Width, Height)` and returns a document or
  null. `GetDocumentTemplate` is consulted first for the default template;
  this machine returned a localized path that did not exist, so the backend
  falls back to the registered document-template folder and its `gb_part.prtdot`
  candidate. It does not hard-code the SOLIDWORKS installation directory.
- [ISldWorks.OpenDoc6](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~OpenDoc6.html)
  takes `(FileName, Type, Options, Configuration, Errors, Warnings)` and
  returns a model document or null.
- [ISldWorks.CloseDoc](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~CloseDoc.html)
  closes a named document. CADiPy only closes documents represented by its
  own handles.
- [ISketchManager.CreateCornerRectangle](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchManager~CreateCornerRectangle.html)
  takes six coordinates and returns sketch segments. Official examples pass
  model coordinates in internal meters; CADiPy converts from public mm at the
  backend boundary.
- [IFeatureManager.FeatureExtrusion3](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~FeatureExtrusion3.html)
  creates an extruded feature from the selected sketch. The official example
  uses `0.003` for a 3 mm depth and the `swEndCondBlind`/related enum values
  supplied by the SOLIDWORKS constants.
- [IModelDoc2.ForceRebuild3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~ForceRebuild3.html)
  returns whether the rebuild completed successfully.
- [IModelDocExtension.SaveAs2](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs2.html)
  returns a Boolean and reports save errors/warnings through output values.
  With dynamic pywin32 dispatch, the two integer output values must be passed
  as `VT_BYREF | VT_I4` variants; passing Python integers produces a COM type
  mismatch on the supported installation. `ExportData` is passed as
  `pythoncom.Nothing`.

## Enum values used at the boundary

The official `swDocumentTypes_e` enumeration defines `swDocPART = 1`,
`swDocASSEMBLY = 2`, and `swDocDRAWING = 3`. The official
`swSaveAsVersion_e` enumeration defines `swSaveAsCurrentVersion = 0`, and
`swSaveAsOptions_e` defines `swSaveAsOptions_Silent = 1`.

These values are kept in the SolidWorks backend only. They are not part of
the public CADiPy API or protocol.

## Runtime verification still required

The following behavior is deliberately verified by the real integration
fixture rather than inferred from documentation: the default part template
available on this machine, the exact feature name returned after extrusion,
the rectangle dimensions as observed from the resulting sketch geometry, the
post-rebuild feature state, and save/close/reopen identity.
