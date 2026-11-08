#!/usr/bin/env python3
"""Update the ``@version`` metadata of a userscript.

Supported ids are the legacy scripts found in ``src/userscripts`` plus
``pimpmyshoutbox-next`` (``next/pimpmyshoutbox/metadata.user.js``).
Only the first ``@version`` line of the ``==UserScript==`` header is touched.

Examples::

    python3 tools/bump_version.py torr9conf 1.0.7
    python3 tools/bump_version.py pimpmyshoutbox-next patch
    python3 tools/bump_version.py pimpmyshoutbox-next minor --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "src" / "userscripts"
NEXT_SCRIPTS = {
    "pimpmyshoutbox-next": ROOT / "next" / "pimpmyshoutbox" / "metadata.user.js",
}
VERSION_RE = re.compile(r"^(?P<prefix>//\s*@version\s+)(?P<version>\S+)(?P<suffix>.*)$")
HEADER_START = "// ==UserScript=="
HEADER_END = "// ==/UserScript=="
PARTS = ("major", "minor", "patch")


def iter_scripts() -> dict[str, Path]:
    scripts: dict[str, Path] = {}
    for source_path in sorted(SCRIPTS_DIR.rglob("*.user.js")):
        script_id = source_path.relative_to(SCRIPTS_DIR).as_posix()[: -len(".user.js")].replace("/", "-")
        scripts[script_id] = source_path
    for script_id, source_path in NEXT_SCRIPTS.items():
        if source_path.exists():
            scripts[script_id] = source_path
    return scripts


def validate_version(version: str) -> None:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise ValueError("Version must use numeric segments like 2.15 or 2.15.1")


def read_version(content: str, label: str = "script") -> str:
    """Return the ``@version`` declared in the userscript header."""
    in_header = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == HEADER_START:
            in_header = True
        elif stripped == HEADER_END:
            break
        elif in_header:
            match = VERSION_RE.match(line)
            if match:
                return match.group("version")
    raise RuntimeError(f"{label}: missing @version metadata line")


def increment_version(version: str, part: str) -> str:
    """Increment ``major``/``minor``/``patch`` while keeping zero-padded widths.

    ``3.01.21`` + ``patch`` -> ``3.01.22``; ``3.01.21`` + ``minor`` -> ``3.02.00``.
    Missing segments are created (``4.0`` + ``patch`` -> ``4.0.1``).
    """
    validate_version(version)
    if part not in PARTS:
        raise ValueError(f"Unknown part '{part}'. Use one of: {', '.join(PARTS)}")

    segments = version.split(".")
    index = PARTS.index(part)
    while len(segments) <= index:
        segments.append("0")

    width = len(segments[index]) if segments[index].startswith("0") and len(segments[index]) > 1 else 0
    segments[index] = str(int(segments[index]) + 1).zfill(width)
    for later in range(index + 1, len(segments)):
        segments[later] = "0".zfill(len(segments[later]))
    return ".".join(segments)


def resolve_version(current: str, requested: str) -> str:
    """Turn ``patch``/``minor``/``major`` or an explicit version into a version."""
    if requested in PARTS:
        return increment_version(current, requested)
    validate_version(requested)
    return requested


def bump_content(content: str, next_version: str, label: str = "script") -> str:
    """Return ``content`` with the header ``@version`` set to ``next_version``."""
    lines = content.splitlines()
    in_header = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == HEADER_START:
            in_header = True
            continue
        if stripped == HEADER_END:
            break
        if not in_header:
            continue
        match = VERSION_RE.match(line)
        if match:
            lines[index] = f"{match.group('prefix')}{next_version}{match.group('suffix')}"
            return "\n".join(lines) + "\n"

    raise RuntimeError(f"{label}: missing @version metadata line")


def bump_script_version(source_path: Path, requested: str, dry_run: bool = False) -> tuple[str, str]:
    """Bump one script and return ``(old_version, new_version)``."""
    content = source_path.read_text(encoding="utf-8")
    old_version = read_version(content, str(source_path))
    new_version = resolve_version(old_version, requested)
    if not dry_run:
        source_path.write_text(bump_content(content, new_version, str(source_path)), encoding="utf-8")
    return old_version, new_version


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the @version of a userscript (legacy ids or pimpmyshoutbox-next)."
    )
    parser.add_argument("script_id", help="Script id (see tools/tr4ker.py list).")
    parser.add_argument(
        "version",
        help="Explicit version (2.15.1) or one of: major, minor, patch.",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Show the change without writing it.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(sys.argv[1:] if argv is None else argv)

    try:
        scripts = iter_scripts()
        if args.script_id not in scripts:
            available = ", ".join(sorted(scripts)) or "none"
            raise RuntimeError(f"Unknown script id '{args.script_id}'. Available ids: {available}")

        old_version, new_version = bump_script_version(scripts[args.script_id], args.version, args.dry_run)
        verb = "would update" if args.dry_run else "updated"
        print(f"{verb} {args.script_id}: v{old_version} -> v{new_version}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
