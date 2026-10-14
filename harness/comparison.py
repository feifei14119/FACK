"""Paired comparisons, without GPU or optional statistics packages.

Bounds concern the population median of paired score ratios, not mean runtime.
Their nominal coverage assumes independent pairs from a common distribution;
ordering balance does not establish that assumption on real hardware.

paired_sign_v1 tests one fixed sample. paired_sequential_v1 analyses
predeclared looks and stops at the first decisive one; each look spends a
predeclared share of the stage alpha (Bonferroni), so coverage holds for any
dependence between looks. Its signed_rank statistic additionally assumes the
paired log ratio is symmetric about its median, which holds when candidate
and reference noise share a distribution and A/B orders are balanced.
"""
import bisect
import fractions
import functools
import itertools
import math
import statistics

from harness.measurement import valid_score

METHOD = "paired_sign_v1"
SEQUENTIAL_METHOD = "paired_sequential_v1"
STATISTICS = ("sign", "signed_rank")
MAX_SEQUENTIAL_PAIRS = 512
LOG_TOLERANCE = 1e-12
SHARE_TOLERANCE = 1e-9


def lower_rank(n, alpha):
    """1-based order statistic with one-sided noncoverage <= alpha (or 0)."""
    cumulative, rank = 0, 0
    for k in range(1, n // 2 + 1):
        cumulative += math.comb(n, k - 1)
        if cumulative / (2 ** n) <= alpha:
            rank = k
        else:
            break
    return rank


@functools.lru_cache(maxsize=None)
def _signed_rank_cumulative_counts(n):
    """2**n * P(T+ <= t) for t = 0..n(n+1)/2 under the symmetric null, exactly."""
    counts = [1]
    for k in range(1, n + 1):
        counts = [a + b for a, b in zip(counts + [0] * k, [0] * k + counts)]
    return tuple(itertools.accumulate(counts))


def signed_rank_lower_rank(n, alpha):
    """1-based Walsh-average order statistic with noncoverage <= alpha (or 0)."""
    limit = math.floor(fractions.Fraction(alpha) * 2 ** n)
    return bisect.bisect_right(_signed_rank_cumulative_counts(n), limit) if limit >= 1 else 0


def _check_number(policy, name):
    value = policy[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be finite and numeric")


def _validate_common(policy):
    value = policy["max_confirmations"]
    if type(value) is not int or not 1 <= value <= 1024:
        raise ValueError("max_confirmations must be an integer in [1, 1024]")
    for name in ("alpha", "min_gain"):
        _check_number(policy, name)
    if not 0 < policy["alpha"] < 0.5 or policy["min_gain"] < 0:
        raise ValueError("require 0 < alpha < 0.5 and min_gain >= 0")


def _validate_looks(policy, stage):
    looks = policy[stage + "_looks"]
    if not isinstance(looks, list) or not looks:
        raise ValueError(stage + "_looks must be a non-empty list")
    previous, shares = 0, 0.0
    for look in looks:
        if not isinstance(look, dict) or set(look) != {"pairs", "alpha_share"}:
            raise ValueError(stage + "_looks entries require exactly pairs and alpha_share")
        pairs = look["pairs"]
        if type(pairs) is not int or not previous < pairs <= MAX_SEQUENTIAL_PAIRS:
            raise ValueError(stage + "_looks pairs must increase within [1, {}]".format(MAX_SEQUENTIAL_PAIRS))
        if pairs % 2:
            raise ValueError(stage + "_looks pairs must be even to balance A/B and B/A order")
        _check_number(look, "alpha_share")
        if look["alpha_share"] <= 0:
            raise ValueError(stage + "_looks alpha_share must be positive")
        alpha = stage_alpha(policy, stage) * look["alpha_share"]
        if not _rank(policy["statistic"], pairs, alpha):
            raise ValueError(stage + " look of {} pairs is too small for its alpha".format(pairs))
        previous, shares = pairs, shares + look["alpha_share"]
    if abs(shares - 1) > SHARE_TOLERANCE:
        raise ValueError(stage + "_looks alpha_share must sum to 1")


def validate_policy(policy):
    """No implicit sample sizes or thresholds; callers freeze the entire policy."""
    if isinstance(policy, dict) and policy.get("method") == SEQUENTIAL_METHOD:
        fields = {"method", "statistic", "confirm_looks", "final_looks", "min_gain",
                  "alpha", "max_confirmations", "futility_stop"}
        if set(policy) != fields:
            raise ValueError("comparison policy requires exactly {}".format(sorted(fields)))
        if policy["statistic"] not in STATISTICS:
            raise ValueError("statistic must be one of {}".format(list(STATISTICS)))
        if type(policy["futility_stop"]) is not bool:
            raise ValueError("futility_stop must be a boolean")
        _validate_common(policy)
        for stage in ("confirm", "final"):
            _validate_looks(policy, stage)
        return dict(policy)
    fields = {"method", "confirm_pairs", "final_pairs", "min_gain", "alpha", "max_confirmations"}
    if not isinstance(policy, dict) or set(policy) != fields or policy["method"] != METHOD:
        raise ValueError("comparison policy requires exactly {} (method={}) or method={}".format(
            sorted(fields), METHOD, SEQUENTIAL_METHOD))
    for name in ("confirm_pairs", "final_pairs"):
        value = policy[name]
        if type(value) is not int or not 1 <= value <= 1024:
            raise ValueError(name + " must be an integer in [1, 1024]")
        if value % 2:
            raise ValueError(name + " must be even to balance A/B and B/A order")
    _validate_common(policy)
    for stage in ("confirm", "final"):
        alpha = stage_alpha(policy, stage)
        if not lower_rank(policy[stage + "_pairs"], alpha):
            raise ValueError(stage + " has too few pairs for its allocated alpha")
    return dict(policy)


def stage_alpha(policy, stage):
    # Bonferroni bounds false promotions across the predeclared confirmation
    # attempts. Final tests just one frozen choice, using independent new data.
    return policy["alpha"] / policy["max_confirmations"] if stage == "confirm" else policy["alpha"]


def look_sizes(policy, stage):
    if policy["method"] == SEQUENTIAL_METHOD:
        return [look["pairs"] for look in policy[stage + "_looks"]]
    return [policy[stage + "_pairs"]]


def planned_pairs(policy, stage):
    """Pairs a comparison may need; budgets must reserve all of them."""
    return look_sizes(policy, stage)[-1]


def pair_order(index):
    return ("reference", "candidate") if index % 2 == 0 else ("candidate", "reference")


def _ratio(log_value):
    try:
        value = math.exp(log_value)
    except OverflowError:
        return None
    return value if value > 0 else None


def _rank(statistic, n, alpha):
    return lower_rank(n, alpha) if statistic == "sign" else signed_rank_lower_rank(n, alpha)


def _log_ratios(pairs):
    if any(not valid_score(p.get(role)) for p in pairs for role in ("reference", "candidate")):
        raise ValueError("invalid paired score")
    return [math.log(p["candidate"]) - math.log(p["reference"]) for p in pairs]


def _decide(lo, hi, threshold):
    if lo > threshold + LOG_TOLERANCE:
        return "confirmed_gain"
    if hi < -threshold - LOG_TOLERANCE:
        return "regression"
    return "inconclusive"


def _check_stage(stage):
    if stage not in ("confirm", "final"):
        raise ValueError("unknown comparison stage")


def assess_look(pairs, policy, stage, look_index):
    """Bounds and stop decision at one predeclared look of a sequential policy."""
    look = policy[stage + "_looks"][look_index]
    if len(pairs) != look["pairs"]:
        raise ValueError("look requires exactly its planned pairs")
    logs = _log_ratios(pairs)
    alpha = stage_alpha(policy, stage) * look["alpha_share"]
    rank = _rank(policy["statistic"], len(logs), alpha)
    if policy["statistic"] == "sign":
        values = sorted(logs)
    else:
        values = sorted((logs[i] + logs[j]) / 2 for i in range(len(logs)) for j in range(i, len(logs)))
    lo, hi = values[rank - 1], values[-rank]
    threshold = math.log1p(policy["min_gain"])
    verdict = _decide(lo, hi, threshold)
    last = look_index == len(policy[stage + "_looks"]) - 1
    if verdict != "inconclusive":
        reason = verdict
    elif policy["futility_stop"] and hi < threshold - LOG_TOLERANCE:
        reason = "futility"
    else:
        reason = "max_pairs" if last else None
    return {"pairs": len(logs), "alpha_one_sided": alpha, "lower_rank": rank,
            "estimate_log_ratio": statistics.median(values),
            "lower_log_bound": lo, "upper_log_bound": hi, "verdict": verdict,
            "stop": reason is not None, "stop_reason": reason}


def _assess_sequential(pairs, policy, stage):
    looks = []
    for index, n in enumerate(look_sizes(policy, stage)):
        if n > len(pairs):
            break
        look = assess_look(pairs[:n], policy, stage, index)
        looks.append(look)
        if look["stop"]:
            break
    if not looks or not looks[-1]["stop"] or looks[-1]["pairs"] != len(pairs):
        raise ValueError("comparison must end exactly at its first stopping look")
    final, logs = looks[-1], _log_ratios(pairs)
    median = statistics.median(logs)
    return {"method": SEQUENTIAL_METHOD, "statistic": policy["statistic"],
            "verdict": final["verdict"], "stop_reason": final["stop_reason"],
            "pairs": len(logs), "planned_pairs": planned_pairs(policy, stage),
            "alpha_one_sided": final["alpha_one_sided"], "lower_rank": final["lower_rank"],
            "min_gain": policy["min_gain"], "log_tolerance": LOG_TOLERANCE,
            "log_ratios": logs, "median_log_ratio": median, "median_ratio": _ratio(median),
            "estimate_log_ratio": final["estimate_log_ratio"],
            "estimate_ratio": _ratio(final["estimate_log_ratio"]),
            "lower_log_bound": final["lower_log_bound"], "upper_log_bound": final["upper_log_bound"],
            "lower_ratio_bound": _ratio(final["lower_log_bound"]),
            "upper_ratio_bound": _ratio(final["upper_log_bound"]), "looks": looks,
            "scope": ("client_reported_scores; iid_pair_assumption_not_hardware_verified"
                      + ("; symmetric_pair_difference_assumed" if policy["statistic"] == "signed_rank" else ""))}


def assess_pairs(pairs, policy, stage):
    """Assess a complete sample; sequential samples must stop at their first decisive look.

Each input is {reference: positive score, candidate: positive score}. The
controller enforces correctness and supplies only fresh, complete pairs.
"""
    validate_policy(policy)
    _check_stage(stage)
    if policy["method"] == SEQUENTIAL_METHOD:
        return _assess_sequential(pairs, policy, stage)
    if len(pairs) != policy[stage + "_pairs"]:
        raise ValueError("comparison requires every planned pair")
    logs = _log_ratios(pairs)
    ordered = sorted(logs)
    alpha = stage_alpha(policy, stage)
    rank = lower_rank(len(logs), alpha)
    lo, hi = ordered[rank - 1], ordered[-rank]
    median = statistics.median(ordered)
    threshold = math.log1p(policy["min_gain"])
    verdict = _decide(lo, hi, threshold)
    return {"method": METHOD, "verdict": verdict, "pairs": len(logs),
            "alpha_one_sided": alpha, "lower_rank": rank,
            "min_gain": policy["min_gain"], "log_tolerance": LOG_TOLERANCE,
            "log_ratios": logs, "median_log_ratio": median,
            "lower_log_bound": lo, "upper_log_bound": hi,
            "median_ratio": _ratio(median), "lower_ratio_bound": _ratio(lo),
            "upper_ratio_bound": _ratio(hi),
            "scope": "client_reported_scores; iid_pair_assumption_not_hardware_verified"}
