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
            "Monokai Enhanced.sublime-color-scheme",
            "VS Code Dark Modern.sublime-theme",
            "tab_square_highlight_thin.png",
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

    def test_ui_theme_uses_packaged_tab_highlight(self) -> None:
        theme = json.loads((ROOT / "VS Code Dark Modern.sublime-theme").read_text(encoding="utf-8"))
        textures = [rule.get("layer2.texture") for rule in theme["rules"]]
        self.assertIn("tab_square_highlight_thin.png", textures)
        self.assertFalse([texture for texture in textures if texture and texture.startswith("User/")])

    def test_packaged_sidebar_file_icons_include_all_scale_variants(self) -> None:
        icon_names = {
            "binary",
            "css",
            "default",
            "image",
            "markup",
            "source",
            "text",
        }
        scale_suffixes = ("", "@2x", "@3x")
        expected = {
            ROOT / "icons" / f"file_type_{name}{suffix}.png"
            for name in icon_names
            for suffix in scale_suffixes
        }
        self.assertFalse([path for path in expected if not path.is_file()])

    def test_ui_theme_maps_common_sidebar_file_types_to_packaged_icons(self) -> None:
        manifest = json.loads(
            (ROOT / "VS Code Dark Modern.sublime-file-icons").read_text(encoding="utf-8")
        )
        expected = {
            "py": "file_type_source",
            "md": "file_type_markup",
            "json": "file_type_source",
            "sublime-theme": "file_type_source",
            ".gitignore": "file_type_text",
        }
        self.assertEqual(
            {extension: manifest["icons"].get(extension) for extension in expected},
            expected,
        )
        for icon_name in set(manifest["icons"].values()):
            self.assertTrue((ROOT / "icons" / f"{icon_name}.png").is_file(), icon_name)

        theme = json.loads((ROOT / "VS Code Dark Modern.sublime-theme").read_text(encoding="utf-8"))
        icon_rules = [rule for rule in theme["rules"] if rule.get("class") == "icon_file_type"]
        self.assertEqual(icon_rules, [{
            "class": "icon_file_type",
            "layer0.tint": "#CCCCCC",
            "layer0.opacity": 0.5,
            "content_margin": [9, 8],
        }])

    def test_ui_theme_command_activates_its_file_icon_theme(self) -> None:
        plugin = (ROOT / "dark_modern_enhanced.py").read_text(encoding="utf-8")
        self.assertIn('FILE_ICON_THEME = "VS Code Dark Modern"', plugin)
        self.assertIn('settings.set("file_icon_theme", FILE_ICON_THEME)', plugin)

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

    def test_legacy_editor_interaction_colors_are_packaged(self) -> None:
        expected = {
            "line_highlight": "#2A2D2E",
            "gutter_foreground_highlight": "#CCCCCC",
            "caret": "#AEAFAD",
            "brackets_options": "underline",
            "brackets_foreground": "#FFFFFF",
            "bracket_contents_options": "underline",
            "bracket_contents_foreground": "#FFFFFF",
            "selection": "#264F78",
            "selection_border": "#264F78",
        }
        self.assertEqual(
            {name: self.scheme["globals"].get(name) for name in expected},
            expected,
        )


class MonokaiEnhancedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scheme = json.loads((ROOT / "Monokai Enhanced.sublime-color-scheme").read_text(encoding="utf-8"))
        cls.rules = cls.scheme["rules"]

    def test_classic_monokai_base_and_globals_are_declared(self) -> None:
        self.assertEqual(self.scheme["name"], "Monokai Enhanced")
        self.assertEqual(
            self.scheme["extends"],
            "Packages/Color Scheme - Default/Monokai.sublime-color-scheme",
        )
        self.assertEqual(self.scheme["globals"]["background"], "var(black3)")
        self.assertEqual(self.scheme["globals"]["selection"], "var(grey)")
        self.assertEqual(self.scheme["globals"]["caret"], "color(var(white2) alpha(0.9))")

    def test_semantic_categories_and_document_enhancements_are_covered(self) -> None:
        selectors = " ".join(rule["scope"] for rule in self.rules)
        required_semantic = {
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
        self.assertFalse([scope for scope in required_semantic if scope not in selectors])
        names = {rule.get("name") for rule in self.rules}
        self.assertTrue(
            {
                "Markdown links and URLs",
                "LaTeX commands",
                "LSP semantic highlighting activation",
            }.issubset(names)
        )

    def test_selection_command_is_packaged(self) -> None:
        commands = json.loads((ROOT / "VS Code Dark Modern Enhanced.sublime-commands").read_text(encoding="utf-8"))
        self.assertIn(
            "vscode_dark_modern_select_monokai_enhanced_color_scheme",
            {entry["command"] for entry in commands},
        )


if __name__ == "__main__":
    unittest.main()
