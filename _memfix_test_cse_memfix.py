"""Tests for cse_mem_fix_v1 (2026-07-29 concurrent-lane host-OOM hardening).

Covers the three deployed measures:
  * size-gated stress-template cache (oversized trees regenerate per round),
  * bit-exactness of the regeneration path (cached vs fresh template give
    identical stress inputs for every policy),
  * gc sweep before high-memory policies touches no RNG state.

Set MK_WORKER_PATH to test a staged worker file before deployment.
"""
import importlib.util
import os
from pathlib import Path

import torch

from src.stress.policy_bank import STRESS_POLICIES

_WORKER_PATH = Path(os.environ.get(
    "MK_WORKER_PATH",
    Path(__file__).resolve().parent.parent / "scripts" / "_mutant_worker.py"))
_spec = importlib.util.spec_from_file_location("_mw_memfix_test", _WORKER_PATH)
_mw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mw)


def test_tree_tensor_nbytes():
    f = _mw._tree_tensor_nbytes
    assert f(torch.zeros(10, dtype=torch.float32)) == 40
    assert f(torch.zeros(4, dtype=torch.float64)) == 32
    assert f([torch.zeros(2), (torch.zeros(3), [torch.zeros(5)])]) == 40
    assert f([]) == 0
    assert f([torch.zeros(2), "x", 7]) == 8  # non-tensor leaves count 0


def test_highmem_gate_small_tree_exempt():
    assert not _mw._needs_highmem_gate([torch.randn(8, 8)])


def test_highmem_gate_threshold(monkeypatch):
    template = [torch.randn(64, 64)]  # 16 KiB
    assert not _mw._needs_highmem_gate(template)
    monkeypatch.setattr(_mw, "HIGH_MEM_GATE_MIN_TEMPLATE_BYTES", 1024)
    assert _mw._needs_highmem_gate(template)


def test_incident_kernels_fall_above_gate():
    """P22/P23 (6.4GB) and P46/P49/P52/P53 (8.6GB) must take the gate;
    checked via nbytes arithmetic, no giant allocation."""
    assert _mw.HIGH_MEM_GATE_MIN_TEMPLATE_BYTES == 1 << 30
    for shape in ((4096, 393216), (16, 32, 128, 128, 256), (128, 4096, 4095)):
        nbytes = 4
        for d in shape:
            nbytes *= d
        assert nbytes > _mw.HIGH_MEM_GATE_MIN_TEMPLATE_BYTES


def test_high_mem_policies_exist_in_bank():
    assert _mw.HIGH_MEM_STRESS_POLICIES <= set(STRESS_POLICIES)


def test_regenerated_template_stress_inputs_bitexact():
    """The uncached path (fresh template per round) must produce the same
    stress inputs as the cached path (template from an earlier seed)."""
    gen = torch.Generator()
    gen.manual_seed(11)
    cached = [torch.rand(37, 53, generator=gen), torch.rand(5, generator=gen)]
    gen.manual_seed(22)  # a later round regenerates under a different seed
    fresh = [torch.rand(37, 53, generator=gen), torch.rand(5, generator=gen)]
    for name, policy in STRESS_POLICIES.items():
        out_cached = policy(cached, 50042)
        out_fresh = policy(fresh, 50042)
        for x, y in zip(out_cached, out_fresh):
            assert torch.equal(x, y), name


def test_highmem_lock_is_exclusive_and_releasable(tmp_path, monkeypatch):
    """cse_mem_fix_v1.1: the generation gate must be exclusive while held
    and reacquirable after release (flock semantics)."""
    import fcntl
    monkeypatch.setattr(_mw, "HIGH_MEM_LOCK_PATH",
                        str(tmp_path / "highmem.lock"))
    fd = _mw._acquire_highmem_lock()
    assert fd is not None
    probe = os.open(_mw.HIGH_MEM_LOCK_PATH, os.O_RDWR)
    try:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held_elsewhere = False
        except OSError:
            held_elsewhere = True
        assert held_elsewhere
        _mw._release_highmem_lock(fd)
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)  # now acquirable
        fcntl.flock(probe, fcntl.LOCK_UN)
    finally:
        os.close(probe)


def test_highmem_lock_release_none_is_noop():
    _mw._release_highmem_lock(None)  # must never raise


def test_highmem_lock_exclusive_and_releases():
    """cse_mem_fix_v1.1 cross-worker gate: exclusive while held, reacquirable
    after release, and never raises."""
    import fcntl
    fd = _mw._acquire_highmem_lock()
    assert fd is not None
    other = os.open(_mw.HIGH_MEM_LOCK_PATH, os.O_CREAT | os.O_RDWR)
    try:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raise AssertionError("lock was not exclusive")
        except (BlockingIOError, OSError):
            pass
        _mw._release_highmem_lock(fd)
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)  # now acquirable
        fcntl.flock(other, fcntl.LOCK_UN)
    finally:
        os.close(other)
    _mw._release_highmem_lock(None)  # None must be a no-op


def test_gc_sweep_preserves_rng_stream():
    """gc.collect + cuda.empty_cache (the pre-round sweep) must not consume
    or perturb any RNG stream the round later uses."""
    import gc
    torch.manual_seed(777)
    a = torch.rand(64)
    torch.manual_seed(777)
    gc.collect()
    try:
        torch.cuda.empty_cache()
    except Exception:
        pass
    b = torch.rand(64)
    assert torch.equal(a, b)
