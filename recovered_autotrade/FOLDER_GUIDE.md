# Recovered Autotrade Folder Guide

## Folder layout

- `2.0_baseline_recovery`
  - Existing 2.0 recovery baseline.
  - Includes the original 2.0 recovered `autotrade2.pyc`, extracted binary artifacts, and prior analysis notes.

- `3.0_original_like_core`
  - 3.0 core files kept as close to the extracted original as practical.
  - Kept files:
    - `autotrade`
    - `autotrade2`

- `3.0_analysis_notes`
  - 3.0 vs 2.0 comparison report and recovery notes.

## Why 3.0 was trimmed

The removed 3.0 file was not vendor-specific core logic.

- Removed: `PYZ.pyz`
  - Reason: it is the embedded Python module bundle, mostly third-party/runtime packages.
  - For this project, the meaningful 3.0 delta was in the main entry script `autotrade2`, not in a changed dependency set.
