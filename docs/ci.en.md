# Real SOLIDWORKS CI

Strict SOLIDWORKS integration is defined by `.github/workflows/solidworks-tests.yml`. The workflow can be called by the main CI and can also be run manually through GitHub Actions.

The main CI invokes the real-machine gate for:

- pushes to `main`;
- weekday schedules;
- pull requests from the same repository.

Fork pull requests are excluded from the private self-hosted runner so untrusted code cannot execute on a development machine with SOLIDWORKS installed.

## Runner requirements

The CADiPy runner must be registered to `Zn070515/CADiPy` with these labels:

```text
self-hosted
windows
x64
solidworks
```

The supported host is Windows 11 x64 with Python 3.12 and SOLIDWORKS 2026 SP3.2 (Revision 34.3.2). `uv` manages Python from `.python-version`; the real-machine workflow does not use `actions/setup-python`.

Use a dedicated runner directory and an interactive desktop session, for example `C:\actions-runner-cadipy`. Do not overwrite or reuse `C:\actions-runner` when it is registered to another repository. Generate the registration token only in GitHub Settings and use it locally; never commit it.

## Lifetime and cleanup

The workflow rejects a pre-existing `SLDWORKS.exe` because CADiPy must not attach to or terminate a user-owned instance. Preflight creates an owned hidden instance with `launch(visible=False)`, verifies the revision and visibility, and closes it. The integration fixture closes only CADiPy-created documents and instances.

The final step only checks for a remaining `SLDWORKS.exe`; it never performs process-wide termination. A leftover process fails the job and remains available for diagnosis. The workflow does not delete the pywin32 `gen_py` cache because that behavior is not yet supported by runtime evidence.
