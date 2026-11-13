# Backend adaptation

Start with examples/validate_callable.py and the public src.validation API.
MutaKernel supplies comparison and test-control machinery; it does not implement
TileLang lowering or a RISC-V Tensor/AME driver.

## Callable integration

validate_pair(reference, candidate, args=..., oracle_config=..., execution_config=...)
accepts Python callables. A candidate wrapper may load a compiled kernel, transfer
input buffers, invoke the target, wait for completion and return logical outputs.
The independent reference must receive identical logical inputs. Equal random
seeds in different runtimes are not sufficient to ensure identical input bytes.

A controller/reference/comparator can run on host CPU while the candidate executes
on another device. Synchronize the target inside the wrapper. ExecutionConfig's
include_cuda_rng and synchronize_cuda_timing can be disabled for non-CUDA execution;
the adapter must implement appropriate target state, RNG and synchronization.

If copying outputs to CPU, preserve the original dtype, shape, layout/stride and
interface metadata separately. Blindly converting everything to contiguous FP32
would hide interface failures. Stateful operators need explicit cache/state
comparison and independent reference/candidate inputs.

## Isolated worker integration

The stock scripts/_candidate_worker.py expects Model, ModelNew, get_inputs() and
optional get_init_inputs(), together with PyTorch-compatible .to() and train/eval
behavior. Its JSON result includes status, phase, observed invocation counts and
evidence.

For an incompatible interface, implement a worker matching the runner protocol.
The programmatic scripts.run_fse_experiment.run_experiment(..., worker_path=...)
hook accepts a custom worker and binds its implementation hash. The standard CLI
selects the stock worker. Inspect _materialize_case, _run_worker and the CPU
integration tests before porting; this hook does not imply backend compatibility.

## Contracts and input generators

Executable case parameters currently cover dtype, batch size, layout, repetition
and backward mode. Extend the schema, applicability checks, plan serialization,
input construction, worker and tests together for Tile shapes, page tables,
quantization formats and routing metadata. Do not ignore unknown parameters.

The stress bank preserves shape/dtype and changes floating values. Valid linked
KV cache/page tables, GPTQ packing and MoE routes need operator-specific generators.
FP8 and packed arithmetic need explicit format, rounding, saturation and oracle
contracts. Test only shapes/layouts that the interface promises to support.

## Mutation guidance

Existing parsers/operators recognize CUDA/Triton constructs. A TileLang syntax/IR
adapter and target fault probes require separate validation. Recheck unmodified
hosts, separate invalid/inconclusive probes, and recalibrate fault-to-stress maps.
Do not treat old CUDA detection rates or budgets as validated target guarantees.

## Bring-up checks

1. A small correct operator agrees with an independently justified reference.
2. Known tail/mask/scale faults produce reproducible failures on legal inputs.
3. Unsupported inputs and unavailable references do not become passes.
4. Repeated calls and cleanup do not contaminate subsequent tests.
5. Evidence identifies the compiled artifact, target, compiler/runtime revisions,
   contract, actual input bytes, schedule and execution path.

Start with RMSNorm or GEMM/MLP, then extend quantized, paged-attention and MoE cases.
Simulator, ISA and real-hardware qualification are distinct from host-side harness
validation. There is no claim of a completed TileLang/RISC-V/AME port in this release.
