"""CPU example: compare an independent reference with correct and faulty callables."""
from pathlib import Path
import json
import sys

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.validation import ExecutionConfig, ValidationStatus, validate_pair


def reference(a, b):
    # Explicit sum of outer products, independent of the candidate's matmul call.
    return sum(a[:, k:k + 1] * b[k:k + 1, :] for k in range(a.shape[1]))


def candidate(a, b):
    return a @ b


def faulty_candidate(a, b):
    # Deliberately omit the final reduction element.
    return a[:, :-1] @ b[:-1, :]


def main():
    # Exact small integers avoid making this wiring example a tolerance experiment.
    a = torch.arange(1, 16, dtype=torch.float32).reshape(3, 5)
    b = torch.arange(1, 21, dtype=torch.float32).reshape(5, 4)
    config = ExecutionConfig(include_cuda_rng=False, synchronize_cuda_timing=False)
    outputs = {}
    for name, function, expected in (
        ("correct_callable", candidate, ValidationStatus.PASS),
        ("omitted_tail", faulty_candidate, ValidationStatus.FAIL),
    ):
        result = validate_pair(reference, function, args=(a, b), execution_config=config)
        if result.status is not expected:
            raise RuntimeError(f"{name}: expected {expected.value}, got {result.status.value}: {result.reason}")
        outputs[name] = result.to_dict()
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
