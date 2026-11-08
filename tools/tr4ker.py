#!/usr/bin/env python3
"""tr4ker - single entry point for the repository toolbox.

Works the same on Windows, macOS and Linux (no ``make`` required)::

    python tools/tr4ker.py doctor            # check required tools
    python tools/tr4ker.py list              # scripts, versions, install URLs
    python tools/tr4ker.py verify            # every gate that CI runs
    python tools/tr4ker.py build             # build dist/ for the legacy scripts
    python tools/tr4ker.py bump pimpmyshoutbox-next patch --dry-run
    python tools/tr4ker.py release pimpmyshoutbox-next patch   # bump + gates

The historical scripts (``build_userscripts.py``, ``bump_version.py``, ...)
keep working unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import build_userscripts as build
import bump_version

ROOT = Path(__file__).resolve().parents[1]
NEXT_DIR = ROOT / "next" / "pimpmyshoutbox"
NEXT_METADATA = NEXT_DIR / "metadata.user.js"
MIN_PYTHON = (3, 10)
NODE_MAJOR = 22


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _use_color() else text


def ok(text: str) -> str:
    return _paint("32", text)


def warn(text: str) -> str:
    return _paint("33", text)


def fail(text: str) -> str:
    return _paint("31", text)


def dim(text: str) -> str:
    return _paint("2", text)


def bold(text: str) -> str:
    return _paint("1", text)


# --------------------------------------------------------------------------- #
# Script inventory (legacy scripts + PimpMyShoutbox Next)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ScriptInfo:
    script_id: str
    name: str
    version: str
    source: str
    kind: str
    download_url: str
    update_url: str


def parse_header(content: str) -> dict[str, str]:
    match = build.USER_SCRIPT_RE.search(content.replace("\r\n", "\n"))
    values: dict[str, str] = {}
    if not match:
        return values
    for line in match.group("meta").splitlines():
        meta = build.META_LINE_RE.match(line)
        if meta and meta.group("key") not in values:
            values[meta.group("key")] = meta.group("value").strip()
    return values


def collect_scripts() -> list[ScriptInfo]:
    config = build.load_config()
    infos: list[ScriptInfo] = []

    for script in build.discover_scripts(config, None):
        outputs = build.build_outputs(config, script)
        infos.append(
            ScriptInfo(
                script_id=outputs["id"],
                name=outputs["name"],
                version=outputs["version"],
                source=outputs["source"],
                kind="legacy",
                download_url=outputs["download_url"],
                update_url=outputs["update_url"],
            )
        )

    if NEXT_METADATA.exists():
        values = parse_header(NEXT_METADATA.read_text(encoding="utf-8"))
        infos.append(
            ScriptInfo(
                script_id="pimpmyshoutbox-next",
                name=values.get("name", "PimpMyShoutbox Next"),
                version=values.get("version", "?"),
                source=NEXT_METADATA.relative_to(ROOT).as_posix(),
                kind="next",
                download_url=values.get("downloadURL", ""),
                update_url=values.get("updateURL", ""),
            )
        )
    return infos


# --------------------------------------------------------------------------- #
# Subprocess helpers
# --------------------------------------------------------------------------- #
def run(command: list[str], cwd: Path = ROOT) -> int:
    print(dim(f"$ {' '.join(command)}"))
    try:
        return subprocess.run(command, cwd=cwd, check=False).returncode
    except FileNotFoundError:
        print(fail(f"command not found: {command[0]}"), file=sys.stderr)
        return 127


def capture(command: list[str], cwd: Path = ROOT) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    return (result.stdout or result.stderr).strip()


def python_cmd() -> str:
    return sys.executable or "python3"


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_list(args: argparse.Namespace) -> int:
    infos = collect_scripts()
    if args.json:
        print(json.dumps([info.__dict__ for info in infos], indent=2, ensure_ascii=False))
        return 0

    width = max(len(info.script_id) for info in infos)
    for info in infos:
        print(f"{bold(info.script_id.ljust(width))}  v{info.version:<9} {dim(info.kind):<14} {info.name}")
        if args.urls:
            print(f"  {dim('source  ')} {info.source}")
            print(f"  {dim('install ')} {info.download_url}")
            print(f"  {dim('update  ')} {info.update_url}")
    if not args.urls:
        print(dim("\nUse --urls to show the Tampermonkey install and update URLs."))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    problems = 0

    def report(label: str, status: str, detail: str = "") -> None:
        print(f"{status}  {label.ljust(12)} {detail}")

    version = sys.version_info
    py_ok = (version.major, version.minor) >= MIN_PYTHON
    report("python", ok("ok  ") if py_ok else fail("FAIL"), f"{version.major}.{version.minor}.{version.micro}")
    problems += not py_ok

    node = shutil.which("node")
    if node:
        node_version = capture([node, "--version"])
        match = re.match(r"v(\d+)", node_version)
        node_ok = bool(match) and int(match.group(1)) == NODE_MAJOR
        report("node", ok("ok  ") if node_ok else warn("warn"), f"{node_version} (Node {NODE_MAJOR} expected)")
    else:
        report("node", fail("FAIL"), "not found: required for syntax checks and PimpMyShoutbox Next")
        problems += 1

    npm = shutil.which("npm")
    report("npm", ok("ok  ") if npm else fail("FAIL"), capture([npm, "--version"]) if npm else "not found")
    problems += not npm

    git = shutil.which("git")
    report("git", ok("ok  ") if git else warn("warn"), capture([git, "--version"]) if git else "not found")

    installed = (NEXT_DIR / "node_modules").is_dir()
    report(
        "next deps",
        ok("ok  ") if installed else warn("warn"),
        "installed" if installed else "missing: run `tr4ker.py verify` or `npm ci` in next/pimpmyshoutbox",
    )

    try:
        config = build.load_config()
        report("config", ok("ok  "), f"{config.repository} ({config.source_branch} -> {config.publish_branch})")
    except (build.BuildError, ValueError) as exc:
        report("config", fail("FAIL"), str(exc))
        problems += 1

    print()
    print(ok("Environment ready.") if not problems else fail(f"{problems} blocking problem(s)."))
    return 1 if problems else 0


def cmd_build(args: argparse.Namespace) -> int:
    command = [python_cmd(), str(ROOT / "tools" / "build_userscripts.py")]
    for script_id in args.scripts or []:
        command += ["--script", script_id]
    code = run(command)
    if code == 0 and args.next:
        code = run_next_build()
    return code


def run_next_build() -> int:
    npm = shutil.which("npm")
    if not npm:
        print(fail("npm not found: cannot build PimpMyShoutbox Next."), file=sys.stderr)
        return 1
    if not (NEXT_DIR / "node_modules").is_dir() and run([npm, "ci"], NEXT_DIR) != 0:
        return 1
    return run([npm, "run", "check"], NEXT_DIR)


def cmd_check(_: argparse.Namespace) -> int:
    for tool, extra in (("build_userscripts.py", ["--check"]), ("check_userscripts_syntax.py", [])):
        code = run([python_cmd(), str(ROOT / "tools" / tool), *extra])
        if code != 0:
            return code
    return 0


def cmd_audit(_: argparse.Namespace) -> int:
    return run([python_cmd(), str(ROOT / "tools" / "audit_userscripts.py")])


def cmd_bump(args: argparse.Namespace) -> int:
    argv = [args.script_id, args.version]
    if args.dry_run:
        argv.append("--dry-run")
    return bump_version.main(argv)


def verification_steps(skip_next: bool) -> list[tuple[str, list[str], Path]]:
    py = python_cmd()
    steps: list[tuple[str, list[str], Path]] = [
        ("Python tooling tests", [py, "-m", "unittest", "discover", "tests"], ROOT),
        ("Metadata validation", [py, str(ROOT / "tools" / "build_userscripts.py"), "--check"], ROOT),
        ("Userscript syntax", [py, str(ROOT / "tools" / "check_userscripts_syntax.py")], ROOT),
    ]
    if not skip_next:
        npm = shutil.which("npm")
        if npm:
            if not (NEXT_DIR / "node_modules").is_dir():
                steps.append(("Install Next dependencies", [npm, "ci"], NEXT_DIR))
            steps.append(("PimpMyShoutbox Next tests", [npm, "test"], NEXT_DIR))
            steps.append(("PimpMyShoutbox Next build", [npm, "run", "check"], NEXT_DIR))
    return steps


def cmd_verify(args: argparse.Namespace) -> int:
    if not args.skip_next and not shutil.which("npm"):
        print(warn("npm not found: Next steps skipped (use --skip-next to silence this)."))

    results: list[tuple[str, bool, float]] = []
    for label, command, cwd in verification_steps(args.skip_next):
        print(bold(f"\n==> {label}"))
        started = time.perf_counter()
        success = run(command, cwd) == 0
        results.append((label, success, time.perf_counter() - started))
        if not success and not args.keep_going:
            break

    print(bold("\nSummary"))
    for label, success, seconds in results:
        print(f"  {ok('PASS') if success else fail('FAIL')}  {label} {dim(f'({seconds:.1f}s)')}")
    passed = all(success for _, success, _ in results) and bool(results)
    print(ok("\nAll gates passed.") if passed else fail("\nVerification failed."))
    return 0 if passed else 1


def cmd_release(args: argparse.Namespace) -> int:
    bump_args = argparse.Namespace(script_id=args.script_id, version=args.version, dry_run=args.dry_run)
    if cmd_bump(bump_args) != 0:
        return 1
    if args.dry_run:
        return 0
    verify_args = argparse.Namespace(skip_next=False, keep_going=False)
    if cmd_verify(verify_args) != 0:
        return 1
    print(
        "\nNext steps: commit, merge into main, then tag if needed "
        "(Next: pimpmyshoutbox-next-v<version>)."
    )
    return 0


def cmd_clean(_: argparse.Namespace) -> int:
    removed = 0
    for target in (ROOT / "dist", NEXT_DIR / "dist"):
        if target.exists():
            shutil.rmtree(target)
            removed += 1
            print(f"removed {target.relative_to(ROOT)}")
    for cache in ROOT.rglob("__pycache__"):
        if "node_modules" not in cache.parts:
            shutil.rmtree(cache, ignore_errors=True)
    print("clean" if not removed else "done")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tr4ker",
        description="Toolbox of the tr4ker-scripting repository.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("list", help="List scripts with version and install URLs")
    p.add_argument("--urls", action="store_true", help="Show source and Tampermonkey URLs")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("doctor", help="Check Python, Node, npm, git and configuration")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("check", help="Validate metadata and JavaScript syntax")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="Build dist/ for the legacy scripts")
    p.add_argument("-s", "--script", action="append", dest="scripts", help="Only this id (repeatable)")
    p.add_argument("--next", action="store_true", help="Also build PimpMyShoutbox Next")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("verify", help="Run every gate that CI runs")
    p.add_argument("--skip-next", action="store_true", help="Skip the PimpMyShoutbox Next steps")
    p.add_argument("-k", "--keep-going", action="store_true", help="Do not stop at the first failure")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("audit", help="Informational size/safety report of the legacy scripts")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("bump", help="Bump a version (explicit, or major/minor/patch)")
    p.add_argument("script_id")
    p.add_argument("version", help="x.y.z or major|minor|patch")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.set_defaults(func=cmd_bump)

    p = sub.add_parser("release", help="Bump a version, then run every gate")
    p.add_argument("script_id")
    p.add_argument("version", help="x.y.z or major|minor|patch")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("clean", help="Remove dist/ folders and Python caches")
    p.set_defaults(func=cmd_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except (build.BuildError, RuntimeError, ValueError) as exc:
        print(fail(f"error: {exc}"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(warn("\ninterrupted"), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
