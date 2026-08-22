"""Explicit assistant intent guards."""

from __future__ import annotations

import re


_CREATE_DRAFT_PATTERNS = (
    re.compile(r"\bcreate\b.*\b(draft )?mitigation plan\b", re.IGNORECASE),
    re.compile(r"\bgenerate\b.*\b(draft )?mitigation plan\b", re.IGNORECASE),
    re.compile(r"\bsave\b.*\bmitigation plan\b", re.IGNORECASE),
)

_HUMAN_ONLY_PATTERNS = (
    re.compile(r"\bapprove\b", re.IGNORECASE),
    re.compile(r"\breject\b", re.IGNORECASE),
    re.compile(r"\bexecute\b", re.IGNORECASE),
    re.compile(r"\breallocate\b", re.IGNORECASE),
    re.compile(r"\bmove\b.*\binventory\b", re.IGNORECASE),
    re.compile(r"\bcomplete\b.*\binventory transfer\b", re.IGNORECASE),
    re.compile(r"\bexpedite\b", re.IGNORECASE),
    re.compile(r"\bprioriti[sz]e\b", re.IGNORECASE),
    re.compile(r"\bresolve\b.*\brisk\b", re.IGNORECASE),
)


def allows_draft_plan_creation(message: str) -> bool:
    return any(pattern.search(message) for pattern in _CREATE_DRAFT_PATTERNS)


def requests_human_only_action(message: str) -> bool:
    return any(pattern.search(message) for pattern in _HUMAN_ONLY_PATTERNS)
