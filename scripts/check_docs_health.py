"""Docs-health guardrail: internal Markdown links + canonical-description drift (issue #101).

Two dependency-free, offline checks that keep the discoverability artifacts honest as the
docs evolve:

1. **Internal link check** — every relative Markdown link in ``README.md`` and ``docs/``
   resolves to a file that exists. External (``http(s)://``, ``mailto:``) links and
   pure in-page anchors (``#section``) are out of scope here.
2. **Canonical-description consistency** — the canonical repository description defined in
   ``METADATA.md`` appears verbatim (modulo line wrapping) in ``README.md``,
   ``pyproject.toml``, and ``CITATION.cff``, so the tagline cannot quietly say three
   different things across surfaces.

Run it directly (``python scripts/check_docs_health.py`` or ``make docs-health``) or import
``check_links`` / ``check_canonical_description`` / ``collect_errors`` from a test. Each
returns a list of human-readable error strings; an empty list means the check passed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Markdown inline link: [text](target) -- target captured. Reference-style and image links
# share the same target syntax, so this covers the internal-link cases the docs use.
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# The files that must carry the canonical description verbatim.
_DESCRIPTION_TARGETS = ("README.md", "pyproject.toml", "CITATION.cff")


def repo_root() -> Path:
    """The repository root (the directory two levels up from this file)."""
    return Path(__file__).resolve().parents[1]


def _markdown_files(root: Path) -> list[Path]:
    """README plus every Markdown file under docs/, in a stable order."""
    files = [root / "README.md"]
    files.extend(sorted((root / "docs").rglob("*.md")))
    return [f for f in files if f.is_file()]


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:"))


def check_links(root: Path | None = None) -> list[str]:
    """Return an error per unresolved internal Markdown link in README.md / docs/."""
    root = root or repo_root()
    errors: list[str] = []
    for md in _markdown_files(root):
        text = md.read_text(encoding="utf-8")
        for match in _LINK.finditer(text):
            target = match.group(1).strip()
            # Strip an optional "title": [t](path "title")
            target = target.split(" ", 1)[0].strip()
            if not target or _is_external(target) or target.startswith("#"):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (md.parent / path_part).resolve()
            rel = md.relative_to(root)
            if not resolved.is_relative_to(root.resolve()):
                # A link that resolves outside the repo (``../../...``) is not a
                # valid repo-internal link, even if the path happens to exist on
                # the runner -- flag it rather than silently passing.
                errors.append(f"{rel}: internal link escapes repo root -> {target!r}")
            elif not resolved.exists():
                errors.append(f"{rel}: broken internal link -> {target!r}")
    return errors


def _normalize(text: str) -> str:
    """Collapse all runs of whitespace so a line-wrapped occurrence still matches."""
    return re.sub(r"\s+", " ", text).strip()


def canonical_description(root: Path | None = None) -> str:
    """The canonical About description extracted from METADATA.md (issue #44)."""
    root = root or repo_root()
    metadata = (root / "METADATA.md").read_text(encoding="utf-8")
    # The description lives in the "GitHub About description" section as a blockquote line.
    in_section = False
    for line in metadata.splitlines():
        if line.startswith("## ") and "About description" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            stripped = line.lstrip("> ").strip()
            if stripped and not line.startswith("Use this"):
                return stripped
    raise ValueError("Could not find the canonical About description in METADATA.md")


def check_canonical_description(root: Path | None = None) -> list[str]:
    """Return an error per target file missing the canonical description verbatim."""
    root = root or repo_root()
    try:
        canonical = canonical_description(root)
    except ValueError as exc:  # METADATA.md changed shape
        return [str(exc)]
    needle = _normalize(canonical)
    errors: list[str] = []
    for name in _DESCRIPTION_TARGETS:
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: missing (cannot verify canonical description)")
            continue
        if needle not in _normalize(path.read_text(encoding="utf-8")):
            errors.append(
                f"{name}: canonical description drift -- does not contain "
                f"the METADATA.md description verbatim: {canonical!r}"
            )
    return errors


def collect_errors(root: Path | None = None) -> list[str]:
    """All docs-health errors (links + canonical description)."""
    root = root or repo_root()
    return check_links(root) + check_canonical_description(root)


def main() -> int:
    root = repo_root()
    errors = collect_errors(root)
    if errors:
        print("docs-health: FAILED")
        for err in errors:
            print(f"  - {err}")
        print(
            "\nFix the broken links and/or align the description with METADATA.md "
            "(the single source of truth for the canonical tagline)."
        )
        return 1
    print("docs-health: OK (internal links resolve; canonical description is consistent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
