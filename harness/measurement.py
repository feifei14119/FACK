"""Collect screening evidence without mixing valid and invalid repetitions.

This module does not confirm speedups or choose statistical thresholds. Each
sample is one call to the client's evaluator, not one internal timing loop.
"""
from __future__ import annotations

import copy
import hashlib
import math
import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


def valid_score(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _json_value(value):
    """Snapshot client data, keeping non-finite values visible in strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return repr(value)


def snapshot_result(result) -> Dict:
    """Detach the client return value before a later call can mutate it."""
    return _json_value(copy.deepcopy({
        key: getattr(result, key, None) for key in (
            "compiled", "correct", "tflops", "time_us",
            "counter_dump_path", "counters", "direction", "detail")
    }))


@dataclass
class MeasurementBatch:
    status: str = "measurement_invalid"
    correct: Optional[bool] = None
    tflops: Optional[float] = None
    samples: List[Dict] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


def measure_screen(evaluator, path: str, repeats: int,
                   expected_sha256: Optional[str] = None) -> MeasurementBatch:
    """Require every repetition to compile, pass correctness and return a score.

    Stop on the first failure, preserve all attempted samples, and never combine
    a PASS from one repetition with a timing whose correctness is unknown.
    Source checks detect mutation of the input file; they do not prove which
    code object the client loaded (that remains the client's responsibility).
    """
    batch = MeasurementBatch()
    scores = []
    try:
        expected = expected_sha256 or file_sha256(path)
        for i in range(max(1, repeats)):
            if file_sha256(path) != expected:
                batch.error = "candidate source changed before evaluation"
                return batch
            sample = {"attempt": i + 1, "source_sha256": expected,
                      "started_at": time.time(), "result": None}
            batch.samples.append(sample)
            started = time.monotonic()
            try:
                res = evaluator.evaluate(path, with_counters=False)
                sample["result"] = snapshot_result(res)
            except Exception as exc:
                sample["error"] = "{}: {}".format(type(exc).__name__, exc)
                batch.error = sample["error"]
                return batch
            finally:
                sample["elapsed_s"] = time.monotonic() - started
            if file_sha256(path) != expected:
                batch.error = "candidate source changed during evaluation"
                return batch
            if getattr(res, "compiled", None) is False:
                batch.status = "compile_failed"
                return batch
            if getattr(res, "compiled", None) is not True:
                batch.error = "missing compilation verdict"
                return batch
            correct, score = getattr(res, "correct", None), getattr(res, "tflops", None)
            if correct is False:
                batch.status, batch.correct = "incorrect", False
                return batch
            if correct is not True or not valid_score(score):
                batch.error = "missing correctness verdict or invalid performance score"
                return batch
            scores.append(score)
    except (OSError, ValueError) as exc:
        batch.error = "{}: {}".format(type(exc).__name__, exc)
        return batch
    batch.status, batch.correct = "measured", True
    batch.tflops = statistics.median(scores)
    return batch
