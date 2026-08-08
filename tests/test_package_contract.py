"""Static package checks that do not require a running Sublime Text instance."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scheme = json.loads(
            (ROOT / "VS Code Dark Modern Enhanced.sublime-color-scheme").read_text(encoding="utf-8")
        )
        cls.rules = cls.scheme["rules"]

    def test_required_runtime_resources_exist(self) -> None:
        required = {
            "VS Code Dark Modern Enhanced.sublime-color-scheme",
            "VS Code Dark Modern Enhanced.sublime-commands",
            "Main.sublime-menu",
            "dark_modern_enhanced.py",
            "messages.json",
            "README.md",
            "LICENSE",
            "theme-build-report.json",
        }
        self.assertFalse([name for name in required if not (ROOT / name).is_file()])
        self.assertFalse((ROOT / "package-metadata.json").exists())

    def test_no_continuous_buffer_processing_hooks(self) -> None:
        plugin = (ROOT / "dark_modern_enhanced.py").read_text(encoding="utf-8")
        forbidden = ("on_modified", "add_regions(", "find_all(")
        self.assertFalse([name for name in forbidden if name in plugin])

    def test_semantic_categories_are_covered(self) -> None:
        selectors = " ".join(rule["scope"] for rule in self.rules)
        required = {
            "meta.semantic-token.function",
            "meta.semantic-token.method",
            "meta.semantic-token.macro",
            "meta.semantic-token.type",
            "meta.semantic-token.class",
            "meta.semantic-token.parameter",
            "meta.semantic-token.property",
            "meta.semantic-token.enummember",
            "meta.semantic-token.variable.readonly",
            "meta.semantic-token.newoperator",
        }
        self.assertFalse([scope for scope in required if scope not in selectors])

    def test_markdown_and_latex_enhancements_are_present(self) -> None:
        names = {rule.get("name") for rule in self.rules}
        required = {
            "Markdown links and URLs",
            "Markdown list and quote markers",
            "Markdown fenced code punctuation",
            "Markdown table punctuation",
            "LaTeX commands",
            "LaTeX environments and sections",
            "LaTeX references and citations",
            "LaTeX parameters",
            "LaTeX math operators",
        }
        self.assertFalse(sorted(required - names))

    def test_only_supported_sublime_font_styles_are_emitted(self) -> None:
        supported = {"bold", "italic", "glow", "underline", "stippled_underline", "squiggly_underline"}
        for rule in self.rules:
            styles = set(rule.get("font_style", "").split())
            self.assertFalse(styles - supported, rule)


if __name__ == "__main__":
    unittest.main()
