#!/usr/bin/env python3
"""Independent reference implementation of fubo-flags bucketing (DESIGN.md §5).

This is deliberately a SECOND implementation of the algorithm, separate from any
SDK. Its purpose is cross-language verification: the Go evaluator must agree with
the expected values in the conformance vectors, and those expected values are
derived here. Two independent implementations agreeing is the actual guarantee.

Usage:
    python reference_bucket.py <flagKey> <salt> <bucketByValue>
    python reference_bucket.py --rollout <flagKey> <salt> <value> w0 w1 [w2 ...]
"""
from __future__ import annotations

import hashlib
import sys

_DENOM = 0xFFFFFFFFFFFFFFF  # 15 hex F's, per LaunchDarkly's algorithm


def bucket(flag_key: str, salt: str, value: str) -> float:
    h = hashlib.sha1(f"{flag_key}.{salt}.{value}".encode()).hexdigest()
    return int(h[:15], 16) / _DENOM


def rollout_variation(b: float, weights: list[int]) -> int:
    """weights are in hundred-thousandths (sum == 100000). Returns variation index."""
    cum = 0.0
    for i, w in enumerate(weights):
        cum += w / 100_000
        if b < cum:
            return i
    return len(weights) - 1  # rounding catch-all


if __name__ == "__main__":
    if sys.argv[1:2] == ["--rollout"]:
        flag_key, salt, value, *ws = sys.argv[2:]
        weights = [int(w) for w in ws]
        b = bucket(flag_key, salt, value)
        print(f"bucket={b:.10f} variation={rollout_variation(b, weights)}")
    else:
        flag_key, salt, value = sys.argv[1:4]
        print(f"bucket={bucket(flag_key, salt, value):.10f}")
