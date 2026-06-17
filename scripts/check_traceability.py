"""Traceability-matrix guardrail: validate docs/control-traceability.md (issue #133).

The control traceability matrix maps each unsafe-baseline risk to a governed control,
the dgenio library it belongs to, where it lives in the code, and a status. It is only
trustworthy if it cannot quietly go stale. This dependency-free, offline checker validates
each data row of the matrix so a broken code link or an unconstrained/overstated status
fails CI rather than misleading a reader.

Checks performed per data row:

1. **Shape** — the row has the expected five columns.
2. **Status vocabulary** — ``Status`` begins with a constrained token
   (``Implemented`` / ``Local stand-in`` / ``Partial`` / ``Planned``), so a row cannot
   invent an unvalidated status.
3. **Known library** — the ``dgenio library`` cell names at least one library from the
   verified Weaver Stack inventory, catching naming drift (relates to issue #144).
4. **Resolvable code links** — every relative Markdown link in the ``Where it lives`` cell
   points at a file that exists, so a renamed/moved module is caught.
5. **Partial/Planned rows reference an issue** — any row not yet ``Implemented`` must link a
   tracking issue (``#NNN``), so unfinished claims are accountable.

Run it directly (``python scripts/check_traceability.py`` or ``make traceability``) or import
``collect_errors`` / the individual ``check_*`` functions from a test. Each returns a list of
human-readable error strings; an empty list means the check passed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The matrix file, relative to the repo root.
_MATRIX = Path("docs") / "control-traceability.md"

# The column the matrix declares (used to locate the table and to label errors).
_COLUMNS = ("Baseline risk", "Governed control", "dgenio library", "Where it lives", "Status")

# Constrained status vocabulary. A status cell is valid when it begins (case-insensitively)
# with one of these tokens; a cell may carry trailing detail (e.g. "Partial (issue #68)").
_ALLOWED_STATUSES = ("implemented", "local stand-in", "partial", "planned")

# The verified Weaver Stack library inventory (issue #80), plus the documented aliases
# (issue #144): weaver-kernel == agent-kernel, agentfence == AgentFence. Matching is
# case-insensitive and substring-based so "agent-kernel (audit)" or "AgentFence / agent-kernel"
# still resolve to a known library.
_KNOWN_LIBRARIES = (
    "contextweaver",
    "chainweaver",
    "agent-kernel",
    "weaver-kernel",
    "agentfence",
    "skdr-eval",
    "lessonweaver",
    "vibeguard",
    "weaver-spec",
)

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_ISSUE_REF = re.compile(r"#\d+")


def repo_root() -> Path:
    """The repository root (the directory two levels up from this file)."""
    return Path(__file__).resolve().parents[1]


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row into trimmed cells (dropping the outer pipes)."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _is_separator(cells: list[str]) -> bool:
    """True for the ``|---|---|`` header underline row."""
    return all(set(c) <= {"-", ":"} and c for c in cells)


def matrix_rows(root: Path | None = None) -> list[list[str]]:
    """Return the matrix's data rows (each a list of cells), excluding header/separator.

    Locates the table by its header row (the one containing every column name) and reads the
    contiguous pipe-delimited rows that follow, stopping at the first non-table line.
    """
    root = root or repo_root()
    text = (root / _MATRIX).read_text(encoding="utf-8")
    rows: list[list[str]] = []
    in_table = False
    seen_separator = False
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            if in_table:
                break  # table ended
            continue
        cells = _split_row(line)
        if not in_table:
            if all(col in cells for col in _COLUMNS):
                in_table = True
            continue
        if not seen_separator and _is_separator(cells):
            seen_separator = True
            continue
        rows.append(cells)
    return rows


def check_matrix(root: Path | None = None) -> list[str]:
    """Validate every data row of the traceability matrix; return human-readable errors."""
    root = root or repo_root()
    rows = matrix_rows(root)
    errors: list[str] = []
    if not rows:
        return [f"{_MATRIX}: no data rows found (is the table header intact?)"]

    matrix_path = root / _MATRIX
    for cells in rows:
        risk = cells[0] if cells else "<empty row>"
        if len(cells) != len(_COLUMNS):
            errors.append(f"{risk!r}: expected {len(_COLUMNS)} columns, found {len(cells)}")
            continue
        _, _, library, where, status = cells

        status_l = status.lower()
        if not any(status_l.startswith(tok) for tok in _ALLOWED_STATUSES):
            errors.append(
                f"{risk!r}: status {status!r} is not one of the allowed values "
                f"{_ALLOWED_STATUSES}"
            )

        if not any(lib in library.lower() for lib in _KNOWN_LIBRARIES):
            errors.append(
                f"{risk!r}: library cell {library!r} names no known Weaver Stack library"
            )

        for match in _LINK.finditer(where):
            target = match.group(1).split(" ", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = target.split("#", 1)[0]
            resolved = (matrix_path.parent / path_part).resolve()
            if not resolved.exists():
                errors.append(f"{risk!r}: broken code/doc link in 'Where it lives' -> {target!r}")

        if not status_l.startswith("implemented") and not _ISSUE_REF.search(" ".join(cells)):
            errors.append(
                f"{risk!r}: status {status!r} is not Implemented but the row links no "
                f"tracking issue (#NNN)"
            )
    return errors


def collect_errors(root: Path | None = None) -> list[str]:
    """All traceability-matrix errors."""
    return check_matrix(root or repo_root())


def main() -> int:
    errors = collect_errors(repo_root())
    if errors:
        print("traceability: FAILED")
        for err in errors:
            print(f"  - {err}")
        print(
            "\nFix the matrix in docs/control-traceability.md: resolve broken links, use a "
            "constrained status, name a known library, and link a tracking issue for any row "
            "that is not yet Implemented."
        )
        return 1
    print("traceability: OK (matrix rows are well-formed; links resolve; statuses are constrained)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
