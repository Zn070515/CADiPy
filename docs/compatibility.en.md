# Compatibility

The strict baseline is Windows 11 x64, Python 3.12, SOLIDWORKS 2026 SP3.2, COM revision `34.3.2`, and pywin32 312 or a compatible update.

| Capability | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | --- | --- | --- | --- |
| portable test suite | Tested | Tested | Tested | Tested |
| real SOLIDWORKS contract | Not validated | Not validated | Tested | Not validated |

The current portable evidence is `25 passed, 1 deselected` on each version. The real SOLIDWORKS strict contract passed on Python 3.12 with SOLIDWORKS 2026 SP3.2 and revision `34.3.2`. Combinations not marked Tested are not claimed as validated support.

Normal `solidworks` tests skip with an explicit reason when SOLIDWORKS or COM is unavailable. `--real-solidworks` or `CADIPY_REQUIRE_REAL_SOLIDWORKS=1` enables the strict gate; missing software, broken COM, unsupported Python/version, or fixture failure is a failure, never a skip.
