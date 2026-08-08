"""Regression tests for the VS Code-to-Sublime color-scheme builder."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import build_theme  # noqa: E402
import jsonc  # noqa: E402


class JsoncTests(unittest.TestCase):
    def test_comments_and_trailing_commas_preserve_string_content(self) -> None:
        data = jsonc.loads(
            '''{
                // A line comment
                "url": "https://example.test/a//b", /* block comment */
                "items": [1, 2,],
                "nested": {"value": true,},
            }'''
        )

        self.assertEqual(
            data,
            {
                "url": "https://example.test/a//b",
                "items": [1, 2],
                "nested": {"value": True},
            },
        )

    def test_unterminated_block_comment_is_rejected(self) -> None:
        with self.assertRaisesRegex(jsonc.JsoncError, "Unterminated block comment"):
            jsonc.loads('{ /* unfinished')


class ThemeResolutionTests(unittest.TestCase):
    def _write_theme(self, folder: Path, name: str, contents: dict[str, object]) -> Path:
        path = folder / name
        path.write_text(json.dumps(contents), encoding="utf-8")
        return path

    def test_three_level_inheritance_preserves_rule_order_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self._write_theme(
                folder,
                "base.json",
                {
                    "name": "Base",
                    "colors": {"editor.background": "#111111", "editor.foreground": "#AAAAAA"},
                    "tokenColors": [{"name": "base", "scope": "keyword", "settings": {"foreground": "#111111"}}],
                    "semanticTokenColors": {"thing": "#111111"},
                },
            )
            self._write_theme(
                folder,
                "middle.json",
                {
                    "include": "base.json",
                    "colors": {"editor.foreground": "#BBBBBB"},
                    "tokenColors": [{"name": "middle", "scope": "string", "settings": {"foreground": "#222222"}}],
                    "semanticTokenColors": {"thing": "#222222", "other": "#333333"},
                },
            )
            leaf = self._write_theme(
                folder,
                "leaf.json",
                {
                    "name": "Leaf",
                    "include": "middle.json",
                    "colors": {"editor.background": "#444444"},
                    "tokenColors": [{"name": "leaf", "scope": "comment", "settings": {"foreground": "#555555"}}],
                    "semanticTokenColors": {"other": "#666666"},
                },
            )

            theme = build_theme.resolve_theme(leaf)

        self.assertEqual(theme.name, "Leaf")
        self.assertEqual([rule["name"] for rule in theme.token_colors], ["base", "middle", "leaf"])
        self.assertEqual(theme.colors["editor.background"].value, "#444444")
        self.assertEqual(theme.colors["editor.foreground"].value, "#BBBBBB")
        self.assertEqual(theme.semantic_colors["thing"].value, "#222222")
        self.assertEqual(theme.semantic_colors["other"].value, "#666666")
        self.assertEqual([Path(item).name for item in theme.chain], ["base.json", "middle.json", "leaf.json"])

    def test_missing_include_reports_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_theme(Path(directory), "root.json", {"include": "missing.json"})
            with self.assertRaisesRegex(build_theme.BuildError, "Missing theme include"):
                build_theme.resolve_theme(source)

    def test_include_cycle_reports_full_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = self._write_theme(folder, "one.json", {"include": "two.json"})
            self._write_theme(folder, "two.json", {"include": "one.json"})
            with self.assertRaisesRegex(build_theme.BuildError, r"Theme include cycle detected: one\.json -> two\.json -> one\.json"):
                build_theme.resolve_theme(source)


class ConversionTests(unittest.TestCase):
    def test_scope_aliases_and_font_style_are_converted_without_reordering(self) -> None:
        rules, provenance = build_theme._convert_token_rules(
            [
                {
                    "__source": "source.json",
                    "name": "Function",
                    "scope": ["entity.name.function", "keyword"],
                    "settings": {"foreground": "#DCDCAA", "background": "#111111", "fontStyle": "bold italic"},
                }
            ],
            {"entity.name.function": ["variable.function", "entity.name.function"]},
        )

        self.assertEqual(
            rules,
            [{
                "name": "Function",
                "scope": "entity.name.function, variable.function, keyword",
                "foreground": "#DCDCAA",
                "background": "#111111",
                "font_style": "bold italic",
            }],
        )
        self.assertEqual(provenance[0]["source"], "source.json")

    def test_vscode_strikethrough_uses_supported_sublime_style(self) -> None:
        rules, _ = build_theme._convert_token_rules(
            [{
                "__source": "source.json",
                "scope": "markup.strikethrough",
                "settings": {"fontStyle": "strikethrough"},
            }],
            {},
        )

        self.assertEqual(rules[0]["font_style"], "stippled_underline")

    def test_semantic_token_and_language_selector_conversion(self) -> None:
        theme = build_theme.ResolvedTheme(
            name="Test",
            chain=[],
            colors={},
            token_colors=[
                {"__source": "base.json", "scope": "entity.name.function", "settings": {"foreground": "#DCDCAA"}},
                {"__source": "base.json", "scope": "keyword", "settings": {"foreground": "#C586C0"}},
            ],
            semantic_colors={
                "newOperator": build_theme.TracedValue("#C586C0", "leaf.json"),
                "variable:typescript": build_theme.TracedValue({"foreground": "#9CDCFE", "fontStyle": "italic"}, "leaf.json"),
            },
        )
        rules, provenance = build_theme._convert_semantic_rules(
            theme,
            {"groups": [{"name": "Functions", "tokens": ["function"], "color_from": "entity.name.function"}], "modifier_groups": []},
        )

        self.assertEqual(rules[0]["background"], build_theme.LSP_ACTIVATION_BACKGROUND)
        self.assertEqual(rules[1], {"name": "Functions", "scope": "meta.semantic-token.function", "foreground": "#DCDCAA"})
        self.assertIn(
            {"name": "VS Code semantic token: newOperator", "scope": "meta.semantic-token.newoperator", "foreground": "#C586C0"},
            rules,
        )
        self.assertIn(
            {"name": "VS Code semantic token: variable:typescript", "scope": "source.typescript meta.semantic-token.variable", "foreground": "#9CDCFE", "font_style": "italic"},
            rules,
        )
        self.assertEqual(provenance[-1]["source"], "leaf.json")


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scheme, cls.report = build_theme.build(ROOT / "dark_modern.json")

    def test_build_has_expected_chain_and_semantic_activation(self) -> None:
        self.assertEqual(self.report["source_chain"], ["dark_vs.json", "dark_plus.json", "dark_modern.json"])
        self.assertEqual(self.scheme["globals"]["background"], "#1F1F1F")
        self.assertGreater(self.report["generated_rule_count"], 50)
        self.assertTrue(any(rule.get("background") == build_theme.LSP_ACTIVATION_BACKGROUND for rule in self.scheme["rules"]))

    def test_legacy_sublime_ui_colors_are_applied(self) -> None:
        expected = {
            "line_highlight": "#2A2D2E",
            "gutter_foreground_highlight": "#CCCCCC",
            "caret": "#AEAFAD",
            "brackets_options": "underline",
            "brackets_foreground": "#D7BA7D",
            "bracket_contents_options": "underline",
            "bracket_contents_foreground": "#D7BA7D",
            "selection": "#264F78",
            "selection_border": "#264F78",
        }
        self.assertEqual(
            {name: self.scheme["globals"].get(name) for name in expected},
            expected,
        )
        provenance = {
            entry["name"]: entry
            for entry in self.report["provenance"]
            if entry["kind"] == "sublime-global-override"
        }
        self.assertEqual(set(provenance), set(expected))
        self.assertTrue(all(entry["mapping"] == "mappings/sublime_ui_overrides.json" for entry in provenance.values()))

    def test_every_generated_syntax_color_has_source_provenance(self) -> None:
        source_colors = self._all_source_colors(ROOT / "dark_modern.json")
        generated_colors = {
            value
            for rule in self.scheme["rules"]
            for key, value in rule.items()
            if key in {"foreground", "background"}
        }
        override_colors = {
            entry["value"]
            for entry in self.report["provenance"]
            if entry["kind"] == "sublime-global-override" and entry["value"].startswith("#")
        }
        generated_colors.update(
            value for value in self.scheme["globals"].values() if value.startswith("#")
        )
        self.assertTrue(
            generated_colors - source_colors
            <= override_colors | {build_theme.LSP_ACTIVATION_BACKGROUND}
        )

        source_backed = [
            entry for entry in self.report["provenance"]
            if entry["kind"] not in {"lsp-activation", "sublime-global-override"}
        ]
        for entry in source_backed:
            for key in ("foreground", "background", "color"):
                if entry.get(key) is not None:
                    self.assertIn(entry[key], source_colors, entry)

    def test_check_mode_does_not_write_requested_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output = folder / "scheme.sublime-color-scheme"
            report = folder / "report.json"
            result = subprocess.run(
                [sys.executable, str(TOOLS / "build_theme.py"), "--check", "--output", str(output), "--report", str(report)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Built VS Code Dark Modern Enhanced", result.stdout)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())

    def _all_source_colors(self, source: Path) -> set[str]:
        theme = build_theme.resolve_theme(source)
        colors = {item.value for item in theme.colors.values()}
        for rule in theme.token_colors:
            settings = rule.get("settings", {})
            if isinstance(settings, dict):
                colors.update(value for key, value in settings.items() if key in {"foreground", "background"})
        for item in theme.semantic_colors.values():
            if isinstance(item.value, str):
                colors.add(item.value)
            elif isinstance(item.value, dict):
                colors.update(value for key, value in item.value.items() if key in {"foreground", "background"})
        return colors


if __name__ == "__main__":
    unittest.main()
