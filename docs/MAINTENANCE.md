# Tool-source cleanup, 2026-11-13

This release retains the latest local maintained implementation while separating
tool source from historical experiment output and deployment scratch work. It is
a descendant of the existing Git history, not a history rewrite.

## Retained

- All 66 existing src/ Python files: validation, mutation, repair, auditing, policy
  generation, external ports and compatibility readers.
- All existing regression tests and operator fixtures.
- Maintained CLIs and their imported helpers or file-path-selected workers.
  A leading underscore is not a deletion criterion.
- Legacy oracle runner/worker required by run_e0_flip_rerun.py for comparisons.
- The latest local timeout-streak change and repair/aggregation helpers.
- KernelBench task sources/licenses, required external references and pinned
  optional submodule identities, now with explicit .gitmodules URLs.

## Retired or separated

One-off diagnostics, fixed-cohort campaign drivers, deployment copies and duplicate
source snapshots were checked against imports, literal subprocess/module paths
and tests before retirement. The maintained entry-point closure does not refer to
those scripts. Manual operator checks with distinct fixture coverage remain.

Research results, extracted datasets, logs and paper-writing records were removed
from the tool Git tree but were not deleted from the original local workspace.
Retired code was archived separately and SHA-256 checked before removing each
source file. The per-file dependency/retirement and backup manifests remain in the
author's local maintenance archive. Prior tracked versions remain in Git history.

Credential-bearing one-off drivers are excluded from the current source tree.
This does not remove old Git objects or rotate credentials. Affected credentials
should be revoked/rotated separately.

## Validation

The pre-cleanup CPU baseline passed 595 tests, with one Windows symlink-permission
skip. In a clean exported tree without ignored local research artifacts, the
release passed 599 tests with the same single skip. All 14 checked maintained CLI
help entries succeeded. The callable example accepted the correct implementation
and rejected its deliberately omitted tail. These checks used Python 3.10 (64 bit)
and PyTorch 2.5.1 CPU.

The tracked tree changed from 13,089 paths to 634. The separate local archive holds
1,388 retired Python/shell/batch files with verified before/after hashes. Research
artifacts removed only from Git tracking were checked to remain present locally.

This does not claim GPU compilation, external service access, native baseline
parity or TileLang/RISC-V/AME hardware qualification. Those require their target
platforms, dependencies, inputs and reviewed contracts.
