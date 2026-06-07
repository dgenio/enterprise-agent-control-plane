"""VibeGuard domain safety gate (issues #10, #91, #125).

A dependency-free, offline *domain gate* that complements the official VibeGuard action
rather than standing in for it. The official ``vibeguard-gate`` runs as a separate CI job
and covers artifact hygiene; this script inspects a unified diff for the repo-specific
change classes documented in [`demos/README.md`](../demos/README.md) that quietly weaken the
agent's safety posture and that neither the official gate nor any other CI check catches:

1. **Widened money-movement / fallback bound** — e.g. the unsafe baseline's hardcoded
   fallback refund amount, or raising ``REFUND_AUTO_LIMIT``. This is the class the
   ``demos/risky_ai_change.diff`` fixture demonstrates.
2. **A capability removed from ``WRITE_OR_DESTRUCTIVE``** — hides a write so it is no
   longer treated as policy-blind / gated.
3. **An introduced outbound network call** — this repo is offline-only, so any added call
   is suspect.

``scan_diff`` returns a list of human-readable findings; an empty list means the diff is
clean. Only changes to the agent's *runtime* source are scanned -- tests, docs, demo
fixtures, and these maintenance scripts are skipped (see ``_IGNORED_PREFIXES``), so example
diffs and the gate's own vocabulary do not trip it. Run it directly (``python
scripts/vibeguard_gate.py --self-check`` or ``make vibeguard-domain``), pipe a diff (``git diff
origin/main...HEAD | python scripts/vibeguard_gate.py``), or import ``scan_diff`` from a test.

This is a reference-architecture domain gate, not production protection; it runs alongside
the official VibeGuard action, which provides the artifact-hygiene layer (see
[`docs/vibeguard.md`](../docs/vibeguard.md)).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A numeric literal (int or float, optionally negative).
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# Lines that move money or set a safety bound -- widening one of these is the risk class
# the risky_ai_change.diff fixture demonstrates.
_MONEY_CONTEXT = re.compile(
    r"amount|refund|fallback|limit|budget|ceiling|threshold|payout|price", re.IGNORECASE
)

# Outbound network primitives -- this repo is offline-only, so an added call is suspect.
_NETWORK = re.compile(
    r"requests\.|httpx\.|urllib\.request|urlopen|http\.client|socket\.|aiohttp|\.get\(['\"]https?://"
)

# A dotted capability literal inside a string, e.g. "billing.issue_refund".
_CAPABILITY = re.compile(r"""['"][a-z_]+\.[a-z_]+['"]""")

_WRITE_SET = "WRITE_OR_DESTRUCTIVE"

# Paths whose diffs are not scanned: they are not the agent's runtime, and they legitimately
# contain example diffs and safety vocabulary (e.g. this gate's own regex, the risky
# fixture, test snippets) that would otherwise produce false positives.
_IGNORED_PREFIXES = ("tests/", "docs/", "demos/", "scripts/")


def repo_root() -> Path:
    """The repository root (the directory two levels up from this file)."""
    return Path(__file__).resolve().parents[1]


def _is_scanned(path: str | None) -> bool:
    """Whether a changed file's hunks should be scanned. A bare hunk with no file header
    (``None``) -- e.g. a snippet passed straight to ``scan_diff`` -- is always scanned."""
    if path is None:
        return True
    if path.endswith(".md"):
        return False
    return not path.startswith(_IGNORED_PREFIXES)


def _skeleton(body: str) -> str:
    """The line with every numeric literal blanked, so two versions that differ only in
    their numbers compare equal."""
    return _NUMBER.sub("#", body).strip()


def _numbers(body: str) -> list[float]:
    return [float(n) for n in _NUMBER.findall(body)]


def _file_hunks(diff_text: str) -> list[tuple[str | None, list[str]]]:
    """Split a unified diff into ``(file_path, hunk_lines)`` pairs.

    The file path is taken from each ``+++ b/<path>`` header so hunks can be filtered by
    location. Anything before the first hunk header -- the fixture's freeform comment
    banner, the ``diff --git`` / ``---`` lines -- is ignored, so only real changed lines
    are scanned.

    Note: a *content* line that itself begins with ``+++ `` or ``--- `` (e.g. a diff that
    adds the literal text ``++ x``) is parsed as a header. This is an accepted limitation
    of the line-prefix heuristic -- it is a reference-architecture gate, not a hardened
    parser -- and standard ``git diff`` output for this repo's source does not produce it.
    """
    pairs: list[tuple[str | None, list[str]]] = []
    current_file: str | None = None
    current: list[str] | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current_file = target[2:] if target.startswith("b/") else target
            current = None
        elif line.startswith("@@"):
            current = []
            pairs.append((current_file, current))
        elif current is not None:
            current.append(line)
    return pairs


def scan_diff(diff_text: str) -> list[str]:
    """Return one finding per risky change class detected in ``diff_text`` (empty == clean)."""
    findings: list[str] = []
    for path, hunk in _file_hunks(diff_text):
        if not _is_scanned(path):
            continue
        removed = [ln[1:] for ln in hunk if ln.startswith("-") and not ln.startswith("---")]
        added = [ln[1:] for ln in hunk if ln.startswith("+") and not ln.startswith("+++")]

        # Class 1 -- a money/bound line whose number was widened (a fallback refund amount,
        # or REFUND_AUTO_LIMIT raised). Pair an added line with the removed line it replaces
        # by matching their number-blanked skeletons, then compare the numbers in order.
        removed_by_skeleton: dict[str, str] = {}
        for body in removed:
            removed_by_skeleton.setdefault(_skeleton(body), body)
        for body in added:
            if not _MONEY_CONTEXT.search(body):
                continue
            prior = removed_by_skeleton.get(_skeleton(body))
            if prior is None:
                continue
            if any(new > old for old, new in zip(_numbers(prior), _numbers(body))):
                findings.append(
                    f"widened money-movement/fallback bound in `{body.strip()}` "
                    f"(was `{prior.strip()}`)"
                )

        # Class 2 -- a capability removed from the WRITE_OR_DESTRUCTIVE set (hides a write).
        # The set may be formatted across several lines (one capability per line), so once
        # the set name appears anywhere in the hunk, collect capability literals from the
        # whole hunk rather than only the line that carries the name -- otherwise a reformat
        # to multi-line would silently defeat the check.
        if any(_WRITE_SET in b for b in removed + added):
            removed_caps = {c for b in removed for c in _CAPABILITY.findall(b)}
            added_caps = {c for b in added for c in _CAPABILITY.findall(b)}
            for cap in sorted(removed_caps - added_caps):
                findings.append(
                    f"capability {cap} removed from {_WRITE_SET} -- a write would no longer be gated"
                )

        # Class 3 -- an outbound network call introduced into an offline-only repo.
        for body in added:
            if _NETWORK.search(body):
                findings.append(f"outbound network call introduced: `{body.strip()}`")

    return findings


def _read_diff(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VibeGuard pre-merge diff safety gate.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--diff",
        help="path to a unified diff file, or '-' for stdin (the default)",
    )
    group.add_argument(
        "--self-check",
        action="store_true",
        help="scan the committed risky fixture and require that the gate flags it",
    )
    args = parser.parse_args(argv)

    if args.self_check:
        fixture = repo_root() / "demos" / "risky_ai_change.diff"
        findings = scan_diff(fixture.read_text(encoding="utf-8"))
        if not findings:
            print("vibeguard: SELF-CHECK FAILED -- the gate did not flag the risky fixture")
            return 1
        print(f"vibeguard: self-check OK -- {fixture.name} is flagged:")
        for finding in findings:
            print(f"  - {finding}")
        return 0

    findings = scan_diff(_read_diff(args.diff or "-"))
    if findings:
        print("vibeguard: BLOCKED -- the diff weakens the agent's safety posture:")
        for finding in findings:
            print(f"  - {finding}")
        print(
            "\nIf this change is intentional, document the rationale and update the gate "
            "(scripts/vibeguard_gate.py) or fixtures accordingly."
        )
        return 1
    print("vibeguard: OK (no risky change classes detected in the diff)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
