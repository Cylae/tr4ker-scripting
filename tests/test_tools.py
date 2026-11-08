"""Unit tests for the Python build tooling (run with ``python3 -m unittest discover tests``)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_userscripts as build  # noqa: E402
import bump_version  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
