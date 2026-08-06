"""CPU-only bit-exactness tests for the B9 port's error statistics.

``error_stats`` was rewritten twice over: torch.quantile refuses inputs above
2**24 elements (which run_error'd every reduction-class subject with a large
output), and the straightforward formulation kept ~10 live float64 copies of a
tensor that reaches 1.6e9 elements.  Both fixes must be numerically invisible:
the calibration rows already produced by the paused E3 pre-flight run must stay
comparable with everything produced afterwards.  So the checks here are
bitwise, against the previous implementation kept verbatim as the oracle:

  * every field, every dtype/shape/tolerance family -> identical bit patterns;
  * the >2**24 path reproduces torch.quantile('linear') exactly (verified by
    shrinking the limit so both paths can run on the same small tensor);
  * the limit constant matches what this torch build actually accepts, so no
    tensor that used to go through torch.quantile is diverted.
"""

import math
import struct
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.experiments.external_ports import b9_seeded_fuzzing as b9
from src.experiments.external_ports import compare_to_fp64

error_stats = b9.error_stats


# ---------------------------------------------------------------------------
# The implementation in force while the first 31 calibration units ran, kept
# verbatim as the bit-exactness oracle (it raises above 2**24 elements, so it
# is only ever consulted below the limit).
# ---------------------------------------------------------------------------

def legacy_error_stats(output, reference, tol):
    out64 = output.detach().to("cpu", torch.float64).reshape(-1)
    ref64 = reference.detach().to("cpu", torch.float64).reshape(-1)
    abs_err = (out64 - ref64).abs()
    abs_err = torch.where(
        torch.isfinite(abs_err), abs_err, torch.full_like(abs_err, math.inf)
    )
    nonzero = ref64 != 0.0
    if bool(nonzero.any()):
        rel = (out64[nonzero] - ref64[nonzero]).abs() / ref64[nonzero].abs()
    else:
        rel = torch.zeros(1, dtype=torch.float64)
    finite_abs = abs_err[torch.isfinite(abs_err)]

    def pct(q):
        if finite_abs.numel() == 0:
            return 0.0
        return float(torch.quantile(finite_abs, q).item())

    return {
        "count": int(abs_err.numel()),
        "num_exceeding": int((abs_err > tol).sum().item()),
        "max_abs": float(abs_err.max().item()) if abs_err.numel() else 0.0,
        "mean_abs": float(finite_abs.mean().item()) if finite_abs.numel() else math.inf,
        "p50_abs": pct(0.50),
        "p90_abs": pct(0.90),
        "p99_abs": pct(0.99),
        "max_rel": float(rel.max().item()) if rel.numel() else 0.0,
        "mean_rel": float(rel.mean().item()) if rel.numel() else 0.0,
    }


def bit_pattern(value):
    if isinstance(value, int):
        return value
    return struct.pack("<d", value).hex()


def assert_bit_identical(got, want, context):
    assert sorted(got) == sorted(want), context
    for field in want:
        a, b = got[field], want[field]
        if isinstance(a, float) and math.isnan(a) and math.isnan(b):
            continue
        assert bit_pattern(a) == bit_pattern(b), (
            f"{context}: field {field}: {a!r} != {b!r}")


# ---------------------------------------------------------------------------
# Error families: exercised against both dtypes of the calibrated set
# ---------------------------------------------------------------------------

def make_pair(family, numel, dtype):
    generator = torch.Generator().manual_seed(numel * 977 + len(family))
    reference = (torch.rand(numel, generator=generator,
                            dtype=torch.float32) * 20.0 - 10.0).to(dtype)
    noise = torch.rand(numel, generator=generator, dtype=torch.float32)
    if family == "exact":
        return reference.clone(), reference
    if family == "noisy":
        return (reference.to(torch.float32) + noise * 1e-3).to(dtype), reference
    if family == "coarse":
        return (reference.to(torch.float32) * 3.0).to(dtype), reference
    if family == "zeros_in_reference":
        reference = reference.clone()
        reference[::7] = 0.0
        return (reference.to(torch.float32) + noise * 1e-3).to(dtype), reference
    if family == "zero_reference":
        return torch.zeros_like(reference), torch.zeros_like(reference)
    output = reference.clone()
    if family == "some_nan":
        output[::11] = float("nan")
    elif family == "some_inf":
        output[::13] = float("inf")
    elif family == "all_nan":
        output = torch.full_like(output, float("nan"))
    elif family == "all_inf":
        output = torch.full_like(output, float("inf"))
    else:
        raise ValueError(family)
    return output, reference


FAMILIES = ("exact", "noisy", "coarse", "zeros_in_reference", "zero_reference",
            "some_nan", "some_inf", "all_nan", "all_inf")


@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
@pytest.mark.parametrize("numel", [1, 2, 3, 17, 4096, 100_003])
@pytest.mark.parametrize("family", FAMILIES)
def test_error_stats_is_bit_identical_below_the_limit(dtype, numel, family):
    output, reference = make_pair(family, numel, dtype)
    for tol in (0.0, 1e-5, 2e-2, 1.0):
        context = f"{family}/{dtype}/n={numel}/tol={tol}"
        assert_bit_identical(error_stats(output, reference, tol),
                             legacy_error_stats(output, reference, tol),
                             context)


def test_error_stats_handles_empty_and_multidimensional_outputs():
    empty = torch.zeros(0)
    assert_bit_identical(error_stats(empty, empty, 1e-5),
                         legacy_error_stats(empty, empty, 1e-5), "empty")
    output = torch.rand(8, 16, 4)
    reference = output + 1e-4
    assert_bit_identical(error_stats(output, reference, 1e-5),
                         legacy_error_stats(output, reference, 1e-5), "3d")


@pytest.mark.parametrize("dtype", [torch.float32, torch.float16,
                                   torch.float64])
def test_error_stats_does_not_mutate_its_arguments(dtype):
    """float64 arguments must be copied, not consumed in place."""
    output, reference = make_pair("noisy", 4096, dtype)
    output_before, reference_before = output.clone(), reference.clone()
    stats = error_stats(output, reference, 1e-5)
    assert torch.equal(output, output_before)
    assert torch.equal(reference, reference_before)
    assert_bit_identical(stats, legacy_error_stats(output, reference, 1e-5),
                         f"no-mutation/{dtype}")


# ---------------------------------------------------------------------------
# The above-limit path
# ---------------------------------------------------------------------------

def test_quantile_limit_constant_matches_this_torch_build():
    accepted = torch.zeros(b9.QUANTILE_NUMEL_LIMIT, dtype=torch.float64)
    torch.quantile(accepted, 0.5)  # must not raise: the limit is inclusive
    del accepted
    with pytest.raises(RuntimeError, match="too large"):
        torch.quantile(
            torch.zeros(b9.QUANTILE_NUMEL_LIMIT + 1, dtype=torch.float64), 0.5)


@pytest.mark.parametrize("numel", [2, 3, 10, 11, 1001, 65_536])
@pytest.mark.parametrize("family", ["uniform", "duplicates", "subnormal",
                                    "huge", "constant"])
def test_exact_percentiles_reproduce_torch_quantile_bitwise(numel, family):
    generator = torch.Generator().manual_seed(numel + len(family))
    values = torch.rand(numel, generator=generator, dtype=torch.float64)
    if family == "duplicates":
        values = torch.randint(0, 3, (numel,), generator=generator).double()
    elif family == "subnormal":
        values = values * 1e-320
    elif family == "huge":
        values = values * 1e300
    elif family == "constant":
        values = torch.zeros(numel, dtype=torch.float64)
    want = {q: float(torch.quantile(values, q).item())
            for q in b9.ERROR_PERCENTILES}
    got = b9._exact_percentiles(values.clone())
    for q in b9.ERROR_PERCENTILES:
        assert bit_pattern(got[q]) == bit_pattern(want[q]), (
            f"{family}/n={numel}/q={q}: {got[q]!r} != {want[q]!r}")


def test_exact_percentiles_partitions_in_place_without_copying():
    values = torch.rand(1024, dtype=torch.float64)
    address = values.numpy().__array_interface__["data"][0]
    b9._exact_percentiles(values)
    assert values.numpy().__array_interface__["data"][0] == address


@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
@pytest.mark.parametrize("family", FAMILIES)
def test_switching_paths_at_the_limit_does_not_change_any_number(
        monkeypatch, dtype, family):
    """A shrunk limit forces the >2**24 path onto a tensor small enough for the
    legacy torch.quantile implementation to grade it."""
    output, reference = make_pair(family, 4096, dtype)
    want = legacy_error_stats(output, reference, 1e-5)
    monkeypatch.setattr(b9, "QUANTILE_NUMEL_LIMIT", 8)
    got = error_stats(output, reference, 1e-5)
    assert_bit_identical(got, want, f"shrunk-limit/{family}/{dtype}")


def test_limit_boundary_is_inclusive(monkeypatch):
    output, reference = make_pair("noisy", 64, torch.float32)
    monkeypatch.setattr(b9, "QUANTILE_NUMEL_LIMIT", 64)
    on_limit = error_stats(output, reference, 1e-5)
    monkeypatch.setattr(b9, "QUANTILE_NUMEL_LIMIT", 63)
    above_limit = error_stats(output, reference, 1e-5)
    assert_bit_identical(on_limit,
                         legacy_error_stats(output, reference, 1e-5), "on-limit")
    assert_bit_identical(above_limit, on_limit, "above-limit")


def test_an_output_above_the_limit_no_longer_raises():
    """The exact failure that run_error'd L1_P3/L1_P7/L1_P8/L1_P9/L1_P11.

    One element past the limit is enough to reproduce it; the real subjects
    reach 1.3e8..1.6e9 elements.
    """
    numel = b9.QUANTILE_NUMEL_LIMIT + 1
    reference = torch.rand(numel, dtype=torch.float32)
    output = reference + 1e-4
    with pytest.raises(RuntimeError, match="too large"):
        legacy_error_stats(output, reference, 1e-5)
    stats = error_stats(output, reference, 1e-5)
    assert stats["count"] == numel
    assert stats["num_exceeding"] == numel  # every element is off by ~1e-4
    assert 0.0 < stats["p50_abs"] <= stats["p90_abs"] <= stats["p99_abs"]
    assert stats["p99_abs"] <= stats["max_abs"]


# ---------------------------------------------------------------------------
# Verdict semantics (validator.rs mirror) are untouched by the memory rewrite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
@pytest.mark.parametrize("family", FAMILIES)
def test_compare_to_fp64_verdict_is_unchanged(dtype, family):
    output, reference = make_pair(family, 1024, dtype)
    verdict = compare_to_fp64(output, reference, 2e-2)
    legacy = legacy_error_stats(output, reference, 2e-2)
    upcast = output.detach().to("cpu", torch.float64)
    if bool(torch.isnan(upcast).any()):
        expected_kind = "nan"
    elif bool(torch.isinf(upcast).any()):
        expected_kind = "inf"
    elif legacy["num_exceeding"] > 0:
        expected_kind = "tolerance"
    else:
        expected_kind = None
    assert verdict["failure_kind"] == expected_kind
    assert verdict["passed"] is (expected_kind is None)
    assert_bit_identical(verdict["error_stats"], legacy,
                         f"verdict-stats/{family}/{dtype}")


def test_compare_to_fp64_still_short_circuits_on_shape():
    verdict = compare_to_fp64(torch.zeros(5), torch.zeros(4), 1e-5)
    assert verdict["failure_kind"] == "shape"
    assert verdict["error_stats"] is None
