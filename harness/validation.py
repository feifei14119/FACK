"""Client-declared metrics and checks, independent of client and GPU names.

Metrics are positive values; direction determines how to turn them into scores.
The legacy EvalResult score remains supported when no contract is declared.
"""
import copy
import statistics

from harness.measurement import valid_score
from harness.comparison import assess_pairs


def validate_contract(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
            "metrics", "primary_metric", "required_checks", "recommendation_scope",
            "associated_workloads"}:
        raise ValueError("invalid client validation contract")
    metrics = value["metrics"]
    if (not isinstance(metrics, dict) or not metrics or not isinstance(value["primary_metric"], str)
            or value["primary_metric"] not in metrics):
        raise ValueError("validation requires metrics and a declared primary_metric")
    for name, item in metrics.items():
        if (not isinstance(name, str) or not name or not isinstance(item, dict) or
                set(item) != {"unit", "direction"} or not isinstance(item["unit"], str) or
                not item["unit"] or item["direction"] not in ("higher", "lower")):
            raise ValueError("invalid metric declaration")
    checks = value["required_checks"]
    if (not isinstance(checks, list) or any(not isinstance(x, str) or not x for x in checks)
            or len(set(checks)) != len(checks)):
        raise ValueError("required_checks must be unique names")
    if value["recommendation_scope"] != "workload":
        raise ValueError("a single run can only recommend its frozen workload")
    if value["associated_workloads"] not in ("not_applicable", "required_for_artifact_adoption"):
        raise ValueError("invalid associated workload requirement")
    return copy.deepcopy(value)


def evidence(result, contract):
    """Return validated raw metrics and scores; never infer omitted checks."""
    if result.get("compiled") is not True or result.get("correct") is not True:
        raise ValueError("client did not compile and pass correctness")
    detail = result.get("detail") or {}
    if not isinstance(detail, dict):
        raise ValueError("client result detail must be an object")
    data = detail.get("validation", {})
    if not isinstance(data, dict):
        raise ValueError("client validation evidence must be an object")
    values, checks = data.get("metrics"), data.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError("client validation checks must be an object")
    if not isinstance(values, dict) or set(values) != set(contract["metrics"]):
        raise ValueError("client validation metrics missing, extra or changed")
    if any(not valid_score(v) for v in values.values()):
        raise ValueError("client validation metric must be positive and finite")
    missing = [name for name in contract["required_checks"] if checks.get(name) is not True]
    if missing:
        raise ValueError("required client checks did not pass: " + ", ".join(missing))
    scores = {name: value if contract["metrics"][name]["direction"] == "higher" else 1 / value
              for name, value in values.items()}
    if any(not valid_score(v) for v in scores.values()):
        raise ValueError("invalid normalized client score")
    return dict(values), scores


def combined_verdict(methods):
    verdicts = [item["verdict"] for item in methods.values()]
    if verdicts and all(v == "confirmed_gain" for v in verdicts):
        return "confirmed_gain"
    if "regression" in verdicts:
        return "regression"
    return "inconclusive"


def assess_methods(pairs, contract, policy, stage):
    """Assess each frozen metric with the same predeclared paired protocol."""
    methods = {}
    for name, description in contract["metrics"].items():
        scores = [{side: p["metric_scores"][side][name] for side in ("reference", "candidate")}
                  for p in pairs]
        methods[name] = dict(assess_pairs(scores, policy, stage), **description)
        for side in ("reference", "candidate"):
            values = [p["metric_values"][side][name] for p in pairs]
            methods[name][side + "_median"] = statistics.median(values)
            methods[name][side + "_range"] = [min(values), max(values)]
    return methods
