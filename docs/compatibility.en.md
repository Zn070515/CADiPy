# Compatibility

The strict baseline is Windows 11 x64, Python 3.12, SOLIDWORKS 2026 SP3.2, COM revision `34.3.2`, and pywin32 312 or a compatible update.

Normal `solidworks` tests skip with an explicit reason when SOLIDWORKS or COM is unavailable. `--real-solidworks` or `CADIPY_REQUIRE_REAL_SOLIDWORKS=1` enables the strict gate; missing software, broken COM, unsupported Python/version, or fixture failure is a failure, never a skip.
