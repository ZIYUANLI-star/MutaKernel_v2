"""Bit-exactness tests for the 2026-07-28 CSE input-pipeline optimisation.

Covers the three deployed changes:
  * stress-template reuse (policies must ignore template values and must
    never mutate their input),
  * removal of the redundant outer clone_tree,
  * single-pass ``_tensor_summary`` (values bit-identical to the legacy
    implementation, including NaN/Inf edge cases).

Set MK_WORKER_PATH to test a staged worker file before deployment.
"""
import importlib.util
import os
from pathlib import Path

import pytest
import torch

from src.stress.policy_bank import STRESS_POLICIES
from src.validation import clone_tree

_WORKER_PATH = Path(os.environ.get(
    "MK_WORKER_PATH",
    Path(__file__).resolve().parent.parent / "scripts" / "_mutant_worker.py"))
_spec = importlib.util.spec_from_file_location("_mw_under_test", _WORKER_PATH)
_mw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mw)


def _legacy_tensor_summary(t):
    """Verbatim copy of the pre-optimisation implementation (reference)."""
    if isinstance(t, torch.Tensor):
        mean = (
            float(t.mean().item())
            if t.numel() > 0 and t.is_floating_point()
            else None
        )
        return {
            "shape": list(t.shape),
            "dtype": str(t.dtype),
            "min": float(t.min()) if t.numel() > 0 else None,
            "max": float(t.max()) if t.numel() > 0 else None,
            "mean": mean,
            "has_nan": bool(t.isnan().any()) if t.is_floating_point() else False,
            "has_inf": bool(t.isinf().any()) if t.is_floating_point() else False,
        }
    return {"type": type(t).__name__, "value": str(t)[:100]}


_SUMMARY_CASES = [
    torch.randn(37, 53),
    torch.randn(1000) * 1e6,
    torch.tensor([1.0, float("nan"), 3.0]),
    torch.tensor([1.0, float("inf"), -2.0]),
    torch.tensor([float("-inf"), 5.0]),
    torch.tensor([float("nan"), float("inf")]),          # NaN+Inf fallback
    torch.tensor([float("nan"), float("-inf"), 2.0]),    # NaN+(-Inf) fallback
    torch.tensor([float("nan")]),
    torch.full((4, 4), float("inf")),
    torch.arange(24, dtype=torch.int64).reshape(2, 3, 4),
    torch.zeros(0),
    torch.zeros(0, dtype=torch.int32),
    torch.tensor(3.5),
    torch.randn(8, 9, dtype=torch.float64),
    torch.randn(64, dtype=torch.float32).half(),
    torch.tensor([True, False]),
]


@pytest.mark.parametrize("idx", range(len(_SUMMARY_CASES)))
def test_tensor_summary_bitexact_vs_legacy(idx):
    t = _SUMMARY_CASES[idx]
    new = _mw._tensor_summary(t)
    old = _legacy_tensor_summary(t)
    assert set(new) == set(old)
    for key in old:
        a, b = old[key], new[key]
        if isinstance(a, float) and a != a:  # NaN == NaN for this check
            assert isinstance(b, float) and b != b, key
        else:
            assert a == b, (key, a, b)


def test_tensor_summary_non_tensor_passthrough():
    assert _mw._tensor_summary(42) == _legacy_tensor_summary(42)
    assert _mw._tensor_summary("x") == _legacy_tensor_summary("x")


def test_policies_never_mutate_template():
    """Safety of dropping the outer clone: policies are pure w.r.t. input."""
    template = [torch.randn(17, 19), torch.randn(5)]
    ref = clone_tree(template)
    for name, policy in STRESS_POLICIES.items():
        policy(template, 50041)
        for got, want in zip(template, ref):
            assert torch.equal(got, want), name


def test_policies_ignore_template_values():
    """Safety of the single-template cache: outputs depend only on the
    template's geometry/dtype and the policy seed, not on template values."""
    gen = torch.Generator()
    gen.manual_seed(9)
    t_a = [torch.randn(17, 19, generator=gen), torch.randn(5, generator=gen)]
    t_b = [torch.zeros(17, 19), torch.full((5,), 7.0)]
    for name, policy in STRESS_POLICIES.items():
        out_a = policy(t_a, 50042)
        out_b = policy(t_b, 50042)
        for x, y in zip(out_a, out_b):
            assert torch.equal(x, y), name


def test_all_float_tensor_tree_guard():
    f = _mw._all_float_tensor_tree
    assert f([torch.randn(3), torch.randn(2, 2)])
    assert f(torch.randn(3))
    assert f((torch.randn(3), [torch.randn(2)]))
    assert not f([torch.randn(3), 5])          # non-tensor leaf
    assert not f([torch.arange(3)])            # integer tensor
    assert not f([torch.randn(3), torch.tensor([True])])
    assert not f([])                           # empty tree is not reusable
    assert not f(5)


def test_worker_declares_pipeline_tag():
    assert _mw.INPUT_PIPELINE_TAG == "cse_gen_opt_v2"
