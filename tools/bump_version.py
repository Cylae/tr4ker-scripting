#!/usr/bin/env python3
"""Update the ``@version`` metadata of a userscript.

Supported ids are the legacy scripts found in ``src/userscripts`` plus
``pimpmyshoutbox-next`` (``next/pimpmyshoutbox/metadata.user.js``).
Only the first ``@version`` line of the ``==UserScript==`` header is touched.
"""

from __future__ import annotations

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


def bump_script_version(source_path: Path, next_version: str) -> None:
    content = source_path.read_text(encoding="utf-8")
    source_path.write_text(bump_content(content, next_version, str(source_path)), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 tools/bump_version.py <script-id> <version>", file=sys.stderr)
        return 1

    script_id = argv[1]
    next_version = argv[2]

    try:
        validate_version(next_version)
        scripts = iter_scripts()
        if script_id not in scripts:
            available = ", ".join(sorted(scripts)) or "none"
            raise RuntimeError(f"Unknown script id '{script_id}'. Available ids: {available}")

        bump_script_version(scripts[script_id], next_version)
        print(f"updated {script_id} to v{next_version}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
