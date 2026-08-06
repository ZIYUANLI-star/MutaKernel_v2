"""B9: seeded differential fuzzing port (gpuemu, Sarkar 2026, @ 696b510b).

Upstream protocol (gpuemu daemon + gpuemu-corpus drivers/_p1lib.py):
  * op-schema-aware sampling — shapes drawn from per-dimension candidate
    lists in the op schema; dtypes from the op's declared list; values
    uniform in [-10, 10] (the Rust fuzzer's range);
  * fp64 CPU reference — the op's reference script computes in float64 and
    rounds back to the kernel output dtype (the correctly-rounded ideal);
  * per-(op,dtype) calibrated absolute tolerances — corpus meta.json values,
    calibrated as p95 of the correct controls' max-abs error x 1.5;
  * comparison semantics (validator.rs): shape mismatch, NaN, Inf, then
    count of |err| > tol; error statistics (max/mean abs, rel, percentiles).

Port mapping onto frozen MutaKernel subjects:
  * op schema      <- the subject contract: fixed shapes stay fixed; the
    contract's batch adapter (when present) provides the sampled dimension
    candidates; dtypes = contract floating dtypes intersected with the
    calibrated set;
  * value sampling -> :func:`b9_uniform10` (uniform [-10, 10], floating
    tensors only, shape/dtype/layout preserved);
  * fp64 reference -> :func:`run_fp64_cpu_reference`;
  * tolerance      -> :func:`calibrate_tolerance` (p95 x 1.5 over control
    errors), with :data:`B9_DEFAULT_TOLERANCES` as the documented fallback
    until per-subject controls are executed;
  * comparison     -> :func:`compare_to_fp64` mirrors validator.rs failure
    kinds and error statistics.

Budget-matched layout: 32 sampled cases, one candidate invocation each
(fp64 reference executions are reference-side and are not charged to the
candidate budget — identical accounting to every other row).

UNSUPPORTED upstream clauses (alignment checklist): the Rust daemon's
bit-exact case generator (we mirror the documented distribution, not the
byte stream), layout-metadata fuzzing beyond the contract's layouts, and the
daemon IPC protocol itself.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import torch

from src.experiments.strategy import StrategySpec, TestCaseSpec
from src.stress.policy_bank import _make_policy

from .budget32 import UNIFIED_CANDIDATE_BUDGET, assert_budget_matched

UPSTREAM_COMMIT = "696b510bc21f8036bcee395749b7fa2c2b4baf2a"
VALUE_RANGE = 10.0  # Rust fuzzer: uniform [-10, 10]
CALIBRATION_QUANTILE = 0.95
CALIBRATION_FACTOR = 1.5

# Corpus meta.json convention (e.g. softmax_triton): documented fallback
# until per-(subject,dtype) control calibration has run.
B9_DEFAULT_TOLERANCES = {"float32": 1e-5, "float16": 2e-2}

# torch.quantile refuses inputs larger than this (measured on torch 2.1.2:
# 2**24 accepted, 2**24 + 1 raises "quantile() input tensor is too large").
# Reduction-class subjects reach 1.6e9 output elements, so anything above the
# limit goes through :func:`_exact_percentiles`.
QUANTILE_NUMEL_LIMIT = 16_777_216

B9_PORT_STRATEGY = StrategySpec(
    name="b9-seeded-fuzzing-style-port",
    version="1",
    parameters={
        "comparison_role": "external_protocol_port",
        "derived_from_commit": UPSTREAM_COMMIT,
        "sampling_family": "op_schema_uniform10",
        "oracle": "fp64_cpu_reference_calibrated_abs_tol",
        "budget_matched": True,
        "calibration": "p95_of_controls_x_1.5",
    },
)


def _b9_uniform_values(t: torch.Tensor, g: torch.Generator) -> torch.Tensor:
    return (
        torch.rand(t.shape, dtype=torch.float32, generator=g) * 2.0 - 1.0
    ) * VALUE_RANGE


b9_uniform10 = _make_policy(_b9_uniform_values)

B9_PORT_POLICIES: Dict[str, Any] = {"b9_uniform10": b9_uniform10}


def plan_b9_port(
    subject_id: str,
    dtypes: Sequence[str] = ("float32", "float16"),
    batch_values: Optional[Sequence[int]] = None,
) -> List[TestCaseSpec]:
    """32 schema-sampled cases, round-robin over (dtype x batch candidate).

    ``dtypes`` must stay within the calibrated tolerance set; ``batch_values``
    comes from the subject contract's batch adapter (None = shapes fixed by
    the contract, exactly like a schema whose dims have a single candidate).
    """

    usable_dtypes = [d for d in dtypes if d in B9_DEFAULT_TOLERANCES]
    if not usable_dtypes:
        raise ValueError(
            f"no calibrated dtype among {list(dtypes)}; "
            f"calibrated set is {sorted(B9_DEFAULT_TOLERANCES)}"
        )
    contexts: List[Dict[str, Any]] = []
    for dtype in usable_dtypes:
        if batch_values:
            for batch in batch_values:
                contexts.append({"dtype": dtype, "batch_size": int(batch)})
        else:
            contexts.append({"dtype": dtype})

    cases = []
    for seed in range(UNIFIED_CANDIDATE_BUDGET):
        context = contexts[seed % len(contexts)]
        cases.append(
            TestCaseSpec(
                subject_id=subject_id,
                strategy=B9_PORT_STRATEGY,
                policy="b9_uniform10",
                seed=seed,
                mode="eval",
                scope="external_port",
                parameters=dict(context),
            )
        )
    return list(assert_budget_matched(cases))


# ---------------------------------------------------------------------------
# fp64 CPU reference + validator.rs comparison semantics
# ---------------------------------------------------------------------------

def run_fp64_cpu_reference(
    reference_module: torch.nn.Module,
    args: Sequence[Any],
    output_dtype: torch.dtype,
) -> torch.Tensor:
    """Compute the correctly-rounded ideal: float64 on CPU, rounded back.

    Mirrors the gpuemu reference scripts (_refkit.py): references compute in
    float64 and return the SAME dtype as the kernel output.
    """

    module = reference_module.to("cpu").double()
    converted = [
        arg.detach().to("cpu", torch.float64)
        if isinstance(arg, torch.Tensor) and arg.is_floating_point()
        else (arg.detach().to("cpu") if isinstance(arg, torch.Tensor) else arg)
        for arg in args
    ]
    with torch.no_grad():
        ideal = module(*converted)
    if not isinstance(ideal, torch.Tensor):
        raise TypeError("B9 port supports single-tensor outputs (upstream protocol)")
    return ideal.to(output_dtype)


ERROR_PERCENTILES = (0.50, 0.90, 0.99)


def _owned_float64(tensor: torch.Tensor) -> torch.Tensor:
    """A flat CPU float64 copy this module may consume in place.

    ``to`` is a no-op for a tensor that is already flat CPU float64, so the
    caller's buffer would otherwise be aliased and destroyed.
    """

    flat = tensor.detach().to("cpu", torch.float64).reshape(-1)
    if flat.data_ptr() == tensor.data_ptr():
        flat = flat.clone()
    return flat


def _exact_percentiles(
    values: torch.Tensor, quantiles: Sequence[float] = ERROR_PERCENTILES
) -> Dict[float, float]:
    """Exact percentiles of a 1-D float64 tensor torch.quantile refuses.

    Introselect (numpy's in-place ``partition``) puts the needed order
    statistics at their sorted positions inside the tensor's own buffer, so
    this allocates nothing and never samples -- the values are the exact
    order statistics, and the interpolation between them is torch's own
    ``lerp``, i.e. bit-for-bit what torch.quantile('linear') would return.
    ``values`` is permuted in place and must not be reused afterwards.
    """

    last = values.numel() - 1
    ranks = {}
    for q in quantiles:
        rank = q * last
        below = int(rank)
        ranks[q] = (below, min(below + 1, last), rank - below)
    buffer = values.numpy()  # zero-copy view; partitioned in place
    buffer.partition(sorted({index for below, above, _ in ranks.values()
                             for index in (below, above)}))
    percentiles = {}
    for q, (below, above, weight) in ranks.items():
        low = torch.tensor(float(buffer[below]), dtype=torch.float64)
        high = torch.tensor(float(buffer[above]), dtype=torch.float64)
        percentiles[q] = float(torch.lerp(low, high, weight).item())
    return percentiles


def error_stats(
    output: torch.Tensor, reference: torch.Tensor, tol: float
) -> Dict[str, float]:
    """Mirror _p1lib.error_stats (abs/rel error distribution vs the ideal).

    Every statistic is computed over exactly the same float64 values in the
    same order as the straightforward formulation (upcast, subtract, abs,
    non-finite -> inf, compact the finite entries), so the numbers are
    bit-identical; the fp64 temporaries are fused in place because a
    reduction-class subject reaches 1.6e9 output elements, where the
    straightforward formulation's ten live copies exceed the memory budget.
    """

    flat_out = output.detach().to("cpu").reshape(-1)
    ref64 = _owned_float64(reference)
    abs_err = _owned_float64(output)
    abs_err.sub_(ref64).abs_()
    finite = torch.isfinite(abs_err)
    all_finite = bool(finite.all())
    if not all_finite:
        abs_err.masked_fill_(finite.logical_not(), math.inf)

    count = int(abs_err.numel())
    num_exceeding = int((abs_err > tol).sum().item())
    max_abs = float(abs_err.max().item()) if count else 0.0

    nonzero = ref64 != 0.0
    if bool(nonzero.any()):
        if all_finite and bool(nonzero.all()):
            # |out - ref| already sits in abs_err; land the quotient in ref64
            rel = torch.div(abs_err, ref64.abs_(), out=ref64)
        else:
            gathered_ref = ref64[nonzero]
            rel = flat_out[nonzero].to(torch.float64)
            rel.sub_(gathered_ref).abs_()
            rel.div_(gathered_ref.abs_())
            del gathered_ref
    else:
        rel = torch.zeros(1, dtype=torch.float64)
    max_rel = float(rel.max().item()) if rel.numel() else 0.0
    mean_rel = float(rel.mean().item()) if rel.numel() else 0.0
    del rel, ref64, nonzero

    finite_abs = abs_err if all_finite else abs_err[finite]
    del abs_err, finite
    n_finite = finite_abs.numel()
    mean_abs = float(finite_abs.mean().item()) if n_finite else math.inf
    if n_finite == 0:
        percentiles = {q: 0.0 for q in ERROR_PERCENTILES}
    elif n_finite <= QUANTILE_NUMEL_LIMIT:
        percentiles = {q: float(torch.quantile(finite_abs, q).item())
                       for q in ERROR_PERCENTILES}
    else:
        percentiles = _exact_percentiles(finite_abs)

    return {
        "count": count,
        "num_exceeding": num_exceeding,
        "max_abs": max_abs,
        "mean_abs": mean_abs,
        "p50_abs": percentiles[0.50],
        "p90_abs": percentiles[0.90],
        "p99_abs": percentiles[0.99],
        "max_rel": max_rel,
        "mean_rel": mean_rel,
    }


def compare_to_fp64(
    output: torch.Tensor, reference: torch.Tensor, tol: float
) -> Dict[str, Any]:
    """Mirror validator.rs: shape, NaN, Inf, absolute-tolerance count."""

    if tuple(output.shape) != tuple(reference.shape):
        return {
            "passed": False,
            "failure_kind": "shape",
            "max_abs_err": math.inf,
            "max_rel_err": math.inf,
            "error_stats": None,
        }
    stats = error_stats(output, reference, tol)
    # nan/inf survive the float64 upcast exactly, so the flags are unchanged
    # while the second full-size fp64 copy of the output is avoided
    checked = output.detach()
    failure_kind = None
    if bool(torch.isnan(checked).any()):
        failure_kind = "nan"
    elif bool(torch.isinf(checked).any()):
        failure_kind = "inf"
    elif stats["num_exceeding"] > 0:
        failure_kind = "tolerance"
    return {
        "passed": failure_kind is None,
        "failure_kind": failure_kind,
        "max_abs_err": stats["max_abs"],
        "max_rel_err": stats["max_rel"],
        "error_stats": stats,
    }


def calibrate_tolerance(
    control_max_abs_errors: Sequence[float],
    quantile: float = CALIBRATION_QUANTILE,
    factor: float = CALIBRATION_FACTOR,
) -> float:
    """Upstream calibration: p95 of correct controls' max-abs error x 1.5."""

    if not control_max_abs_errors:
        raise ValueError("calibration requires at least one control error")
    errors = torch.tensor(sorted(control_max_abs_errors), dtype=torch.float64)
    if not bool(torch.isfinite(errors).all()):
        raise ValueError("control errors must be finite")
    return float(torch.quantile(errors, quantile).item()) * factor
