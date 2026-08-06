# Auto-generated robust-kbench FORWARD reference for the kernel-reward-audit
# pipeline. The reference is the task's pure-torch forward_fn; get_inputs()
# returns the full positional arg list (input tensor(s) + Model parameters +
# scalars) so reference and CUDA candidate receive byte-identical inputs.
import importlib.util
import os
import torch
import torch.nn as _nn

# Environment polyfill: this server runs torch 2.1.2, which predates
# torch.nn.RMSNorm (added in 2.4). Some robust-kbench task Models call
# nn.RMSNorm purely to mint a weight tensor of the right shape in __init__
# (the pure-torch forward_fn never uses it). Provide a minimal shim so the
# REFERENCE is constructible. The vetted CUDA kernel and forward_fn are
# untouched; this only affects reference parameter construction.
if not hasattr(_nn, "RMSNorm"):
    class _RMSNormShim(_nn.Module):
        def __init__(self, normalized_shape, eps=1e-6, elementwise_affine=True, **kw):
            super().__init__()
            if isinstance(normalized_shape, int):
                normalized_shape = (normalized_shape,)
            self.normalized_shape = tuple(normalized_shape)
            self.eps = eps
            self.weight = _nn.Parameter(torch.ones(*self.normalized_shape))

        def forward(self, x):  # unused by forward_fn
            return x

    _nn.RMSNorm = _RMSNormShim

_TASK_DIR = '/root/robust_kbench_data/tasks/layernorm'
_INIT = {'init_method': 'random', 'num_features': 64, 'dim1': 256, 'dim2': 256}
_INPUT = {'batch_size': 1, 'num_features': 64, 'dim1': 256, 'dim2': 256}

_spec = importlib.util.spec_from_file_location(
    "rkb_ff_layernorm", os.path.join(_TASK_DIR, "func_forward.py"))
_ff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ff)

forward_fn = _ff.forward_fn


def _capture_args():
    """Build the task Model + raw inputs, then recover the EXACT positional
    arguments Model.forward passes to forward_fn via a probe (handles tasks with
    multiple inputs, model params, None args, and trailing scalars uniformly).
    Determinism is provided by the caller (the oracle seeds torch before each
    sample_inputs call), so ref and candidate see identical parameters."""
    model = _ff.Model(**_INIT)
    raw = _ff.get_inputs(**_INPUT)
    if not isinstance(raw, (list, tuple)):
        raw = [raw]
    captured = {}

    def _probe(*args, **kwargs):
        captured["args"] = args
        return args[0]

    model.forward(*raw, fn=_probe)
    return list(captured["args"])


def _to_cuda(v):
    if isinstance(v, torch.Tensor):
        if v.is_floating_point():
            return v.detach().to("cuda", torch.float32).contiguous()
        return v.detach().to("cuda").contiguous()
    return v


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, *args):
        return forward_fn(*args)


def get_inputs():
    return [_to_cuda(v) for v in _capture_args()]


def get_init_inputs():
    return []
