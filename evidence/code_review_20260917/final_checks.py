"""Collect fresh existing test results in a new review-only directory."""
from __future__ import annotations

from pathlib import Path

import collect_review


if __name__ == "__main__":
    destination = Path(__file__).resolve().parent / "final_checks"
    destination.mkdir(exist_ok=False)
    collect_review.OUT = destination
    # checks() records process failures; its own successful return does not
    # mean those recorded test suites or harness checks passed.
    collect_review.checks()
