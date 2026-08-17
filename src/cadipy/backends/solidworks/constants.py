"""Verified SOLIDWORKS API enum values used by the late-bound adapter."""

# SOLIDWORKS 2026 IDispatch probing reports this value for the official
# swUserPreferenceToggle_e.swInputDimValOnCreate member.  Keep the value in
# one place because the dynamic pywin32 adapter does not expose makepy enums.
SW_INPUT_DIM_VAL_ON_CREATE = 10
