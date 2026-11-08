"""Unit tests for the Python build tooling (run with ``python3 -m unittest discover tests``)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_userscripts as build  # noqa: E402
import bump_version  # noqa: E402
import tr4ker  # noqa: E402

SAMPLE = """// ==UserScript==
// @name         Demo
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  Demo script
// @match        https://example.com/*
// ==/UserScript==

// @version 9.9 (inside the code, must never be touched)
console.log('hello');
"""

CONFIG = build.RepoConfig(
    repository="owner/repo",
    source_branch="main",
    publish_branch="userscripts",
    scripts_dir=ROOT / "src" / "userscripts",
    dist_dir=ROOT / "dist",
)


def make_script(source: str = SAMPLE) -> build.ScriptDefinition:
    return build.ScriptDefinition(
        script_id="demo",
        source_path=ROOT / "src" / "userscripts" / "demo.user.js",
        relative_source_path=Path("src/userscripts/demo.user.js"),
        user_dist_path=ROOT / "dist" / "demo.user.js",
        meta_dist_path=ROOT / "dist" / "demo.meta.js",
    )


class BumpVersionTests(unittest.TestCase):
    def test_only_header_version_is_changed(self) -> None:
        updated = bump_version.bump_content(SAMPLE, "2.0.1")
        self.assertIn("// @version      2.0.1", updated)
        self.assertIn("// @version 9.9 (inside the code", updated)
        self.assertTrue(updated.endswith("\n"))

    def test_missing_version_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            bump_version.bump_content("// ==UserScript==\n// @name X\n// ==/UserScript==\n", "1.0")

    def test_invalid_version_rejected(self) -> None:
        for bad in ("", "v1.0", "1.0-beta", "1..2"):
            with self.assertRaises(ValueError):
                bump_version.validate_version(bad)

    def test_next_script_is_listed(self) -> None:
        self.assertIn("pimpmyshoutbox-next", bump_version.iter_scripts())

    def test_increment_keeps_zero_padding(self) -> None:
        self.assertEqual(bump_version.increment_version("3.01.21", "patch"), "3.01.22")
        self.assertEqual(bump_version.increment_version("3.01.21", "minor"), "3.02.00")
        self.assertEqual(bump_version.increment_version("3.01.21", "major"), "4.00.00")

    def test_increment_creates_missing_segments(self) -> None:
        self.assertEqual(bump_version.increment_version("4.0", "patch"), "4.0.1")
        self.assertEqual(bump_version.increment_version("1", "minor"), "1.1")
        self.assertEqual(bump_version.increment_version("1.9.9", "minor"), "1.10.0")

    def test_resolve_version(self) -> None:
        self.assertEqual(bump_version.resolve_version("1.0.6", "patch"), "1.0.7")
        self.assertEqual(bump_version.resolve_version("1.0.6", "2.0"), "2.0")
        with self.assertRaises(ValueError):
            bump_version.resolve_version("1.0.6", "latest")

    def test_read_version(self) -> None:
        self.assertEqual(bump_version.read_version(SAMPLE), "1.2")

    def test_dry_run_does_not_write(self) -> None:
        path = ROOT / "next" / "pimpmyshoutbox" / "metadata.user.js"
        before = path.read_text(encoding="utf-8")
        bump_version.bump_script_version(path, "patch", dry_run=True)
        self.assertEqual(path.read_text(encoding="utf-8"), before)


class BuildMetadataTests(unittest.TestCase):
    def parse(self, source: str):
        match, entries = build.read_metadata_block(source, Path("demo.user.js"))
        return match, entries, build.extract_metadata_values(entries)

    def test_urls_are_injected(self) -> None:
        _, entries, values = self.parse(SAMPLE)
        overrides = build.compute_metadata_overrides(CONFIG, make_script(), values)
        self.assertEqual(overrides["namespace"], "https://github.com/owner/repo")
        self.assertEqual(
            overrides["updateURL"],
            "https://raw.githubusercontent.com/owner/repo/userscripts/demo.meta.js",
        )
        self.assertEqual(
            overrides["downloadURL"],
            "https://raw.githubusercontent.com/owner/repo/userscripts/demo.user.js",
        )
        merged = build.merge_metadata_entries(entries, overrides)
        self.assertEqual(sum(line.startswith("// @updateURL") for line in merged), 1)

    def test_duplicate_singleton_keys_are_rejected(self) -> None:
        source = SAMPLE.replace(
            "// @match",
            "// @updateURL    https://a.example/x.meta.js\n// @updateURL    https://a.example/x.meta.js\n// @match",
        )
        _, entries, values = self.parse(source)
        with self.assertRaises(build.BuildError):
            build.validate_metadata(values, Path("demo.user.js"), entries)

    def test_repeatable_keys_are_allowed(self) -> None:
        source = SAMPLE.replace("// @match", "// @grant none\n// @grant GM_getValue\n// @match")
        _, entries, values = self.parse(source)
        build.validate_metadata(values, Path("demo.user.js"), entries)

    def test_invalid_version_is_rejected(self) -> None:
        _, entries, values = self.parse(SAMPLE.replace("1.2", "1.2-beta"))
        with self.assertRaises(build.BuildError):
            build.validate_metadata(values, Path("demo.user.js"), entries)

    def test_missing_match_is_rejected(self) -> None:
        _, entries, values = self.parse(SAMPLE.replace("// @match        https://example.com/*\n", ""))
        with self.assertRaises(build.BuildError):
            build.validate_metadata(values, Path("demo.user.js"), entries)

    def test_url_validation(self) -> None:
        for bad in ("", "ftp://x.y/z", "https://a b", "https://`x`.dev"):
            with self.assertRaises(build.BuildError):
                build.validate_metadata_url("updateURL", bad, Path("demo.user.js"))
        build.validate_metadata_url("updateURL", "https://example.com/x.meta.js", Path("demo.user.js"))


class RepositoryScriptsTests(unittest.TestCase):
    def test_every_repository_script_builds(self) -> None:
        config = build.load_config()
        scripts = build.discover_scripts(config, None)
        self.assertTrue(scripts)
        for script in scripts:
            outputs = build.build_outputs(config, script)
            self.assertIn("@updateURL", outputs["meta_script"])
            self.assertEqual(outputs["user_script"].count("// @updateURL"), 1)
            self.assertEqual(outputs["user_script"].count("// @downloadURL"), 1)


class ToolboxCliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = tr4ker.main(list(argv))
        return code, buffer.getvalue()

    def test_list_json_contains_legacy_and_next(self) -> None:
        code, output = self.run_cli("list", "--json")
        self.assertEqual(code, 0)
        ids = {item["script_id"] for item in json.loads(output)}
        self.assertIn("pimpmyshoutbox-next", ids)
        self.assertIn("torr9conf", ids)

    def test_list_urls_mentions_install_urls(self) -> None:
        code, output = self.run_cli("list", "--urls")
        self.assertEqual(code, 0)
        self.assertIn("userscripts/pimpmyshoutbox-next.user.js", output)

    def test_no_command_prints_help(self) -> None:
        code, output = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("verify", output)

    def test_bump_dry_run_via_cli(self) -> None:
        code, output = self.run_cli("bump", "torr9conf", "patch", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would update torr9conf", output)

    def test_verification_steps_can_skip_next(self) -> None:
        labels = [label for label, _, _ in tr4ker.verification_steps(skip_next=True)]
        self.assertEqual(len(labels), 3)
        self.assertFalse(any("Next" in label for label in labels))


if __name__ == "__main__":
    unittest.main()
