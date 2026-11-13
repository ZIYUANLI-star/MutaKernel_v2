# MutaKernel V2

MutaKernel provides contract-aware differential validation, controlled mutation
probes, stress-input construction, counterexample search, and reproducible
experiment records. This is the maintained tool source for development and
backend adaptation. Paper artifacts and historical run outputs are separate.

## Quick start

Use **Python 3.10 or later, 64 bit**. Run commands from the repository root.
Maintenance checks use Python 3.10 and PyTorch 2.5.1 CPU. Actual GPU candidates
also need the corresponding GPU, compiler and runtime.

~~~bash
git clone --depth 1 https://github.com/ZIYUANLI-star/MutaKernel_v2.git
cd MutaKernel_v2
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1

python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-dev.txt
python examples/validate_callable.py
python -m pytest -q
~~~

The example checks a correct matrix-product callable and detects a deliberately
omitted reduction tail. It requires no GPU, benchmark download, API key or network
service. Passing this example does not qualify a hardware backend.

For GPU execution, install the appropriate CUDA build of PyTorch instead of the
CPU build. Triton candidates require a Triton version compatible with the
supported Linux/PyTorch/GPU stack. LLM repair/triage, SSH, plotting and dataset
ingestion dependencies are in requirements-optional.txt; install them only for
the features you use. Credentials and machine paths belong in environment
variables, never in committed source.

## Main interfaces

| Area | Source / entry point |
|---|---|
| Validate callables or modules | src.validation.validate_pair, ValidationExecutor |
| Structured numerical oracle | src/validation/oracle.py |
| Input, state and RNG isolation | src/validation/inputs.py, state.py |
| Contracts and applicability | src/experiments/contract.py |
| Stress input generation | src/stress/policy_bank.py, policy_metadata.py |
| CUDA/Triton parsing and mutation | src/mutengine/ |
| Counterexample verdicts, auditing and mapping | src/cse/, src/audit/ |
| Directed test planning | src/validator/site_directed.py |
| Optional repair and diagnosis | src/mutrepair/, src/mutevolve/, src/stress/llm_* |
| Isolated candidate execution | scripts/_candidate_worker.py |
| Reproducible experiments | scripts/build_fse_subject_manifest.py, plan_fse_experiment.py, run_fse_experiment.py |
| External protocol ports | src/experiments/external_ports/, scripts/run_e3_external.py |

For new hardware, read **[the backend adaptation guide](docs/BACKEND_ADAPTATION.md)**.
The existing implementation targets PyTorch callables and CUDA/Triton workloads.
It does **not** contain a ready-made TileLang, RISC-V Tensor or AME backend.

## Experiment workflow

1. Prepare candidate/reference sources and a reviewed contract.
2. Build a content-addressed subject manifest with build_fse_subject_manifest.py.
3. Freeze a test plan with plan_fse_experiment.py.
4. Capture the environment with capture_fse_environment.py.
5. Execute run_fse_experiment.py, then summarize/analyze the records.

Use each command's --help for exact arguments. The runner binds source hashes,
contracts, worker implementation, environment, test IDs and costs. It supports
resume and the latest local --timeout-streak-limit option. Skipped cases remain
INCONCLUSIVE and record zero observed candidate calls; they are not passes.

The mutation/EMD pipeline remains available through run_mutation_test.py and
full_block12.py. Stress enhancement, repair, controlled probes, human audit,
baseline ports, statistical analysis and repair-campaign tools remain in scripts/.
The legacy oracle runner/worker are intentionally retained because the E0
soundness comparison invokes them; they are not the default oracle.

The Block* and FSE_* documents retain historical design and review context.
Current interfaces are described here, in the adaptation guide, in --help output,
and by the maintained tests; retired diagnostic paths in historical notes are
available in prior Git commits.

## Data and optional external projects

Small operator fixtures, KernelBench task sources and required external reference
functions remain available. Full research runs, extracted datasets, paper-writing
records, deployment snapshots and one-off diagnostics are not tool source. They
were preserved locally during cleanup; see [the maintenance record](docs/MAINTENANCE.md).

Optional third-party revisions are pinned as submodules. They are unnecessary for
the CPU suite/example. Initialize only a dependency your task needs:

~~~bash
git submodule update --init external/B7_robust_kbench
~~~

See [external baseline integration](docs/RELATED_BASELINE_INTEGRATION.md) for
native/ported distinctions. Other corpora need separately provided inputs and
dependencies. The historic best_kernels.json is an index, not bundled generated
kernels; use scripts/scan_best_kernels.py to index your own runs.

Path overrides include MUTAKERNEL_KERNELBENCH_ROOT, MUTAKERNEL_KERNELBENCH_RUNS
and MUTAKERNEL_RESULTS_DIR; see config.py. Configure temporary/compiler/package
caches and output directories for your host. If data must stay remote, keep
inputs, logs, witnesses and outputs on that host.

## Result interpretation

PASS means observed agreement under the configured contract and oracle. FAIL
records a discrepancy or attributed candidate failure. INCONCLUSIVE means the
comparison was unavailable or unsound. Keep phase, scope, observed call counts
and evidence: compile, resource, out-of-contract and numerical failures have
different meanings. Finite tests and mutation scores do not prove equivalence.
