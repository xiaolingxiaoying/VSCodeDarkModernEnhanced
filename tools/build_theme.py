#!/usr/bin/env python3
"""Build the Sublime Text color scheme from the VS Code Dark Modern sources."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from . import jsonc
except ImportError:
    import jsonc  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{3,8}$")
ALLOWED_TOKEN_SETTINGS = {"foreground", "background", "fontStyle"}
SUPPORTED_FONT_STYLES = {"bold", "italic", "glow", "underline", "stippled_underline", "squiggly_underline"}
FONT_STYLE_ADAPTATIONS = {"strikethrough": "stippled_underline"}
LSP_ACTIVATION_BACKGROUND = "#00000101"


class BuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class TracedValue:
    value: Any
    source: str


@dataclass
class ResolvedTheme:
    name: str
    chain: list[str]
    colors: dict[str, TracedValue]
    token_colors: list[dict[str, Any]]
    semantic_colors: dict[str, TracedValue]


def _relative_source(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _validate_color(value: Any, context: str) -> str:
    if not isinstance(value, str) or not COLOR_PATTERN.fullmatch(value):
        raise BuildError(f"Invalid or unsupported color in {context}: {value!r}")
    if len(value) not in (4, 5, 7, 9):
        raise BuildError(f"Invalid hex color length in {context}: {value!r}")
    return value


def resolve_theme(path: Path, stack: tuple[Path, ...] = ()) -> ResolvedTheme:
    resolved_path = path.resolve()
    if resolved_path in stack:
        cycle = " -> ".join(item.name for item in (*stack, resolved_path))
        raise BuildError(f"Theme include cycle detected: {cycle}")
    if not resolved_path.is_file():
        raise BuildError(f"Missing theme include: {resolved_path}")

    data = jsonc.load(resolved_path)
    if not isinstance(data, dict):
        raise BuildError(f"Theme root must be an object: {resolved_path}")
    source = _relative_source(resolved_path)

    include = data.get("include")
    if include is not None:
        if not isinstance(include, str):
            raise BuildError(f"Theme include must be a string in {source}")
        parent = resolve_theme(resolved_path.parent / include, (*stack, resolved_path))
    else:
        parent = ResolvedTheme("", [], {}, [], {})

    colors = dict(parent.colors)
    raw_colors = data.get("colors", {})
    if not isinstance(raw_colors, dict):
        raise BuildError(f"colors must be an object in {source}")
    for key, value in raw_colors.items():
        colors[key] = TracedValue(_validate_color(value, f"{source}: colors.{key}"), source)

    token_colors = list(parent.token_colors)
    raw_rules = data.get("tokenColors", [])
    if not isinstance(raw_rules, list):
        raise BuildError(f"tokenColors must be an array in {source}")
    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict):
            raise BuildError(f"tokenColors[{index}] must be an object in {source}")
        traced_rule = dict(rule)
        traced_rule["__source"] = source
        token_colors.append(traced_rule)

    semantic_colors = dict(parent.semantic_colors)
    raw_semantic = data.get("semanticTokenColors", {})
    if not isinstance(raw_semantic, dict):
        raise BuildError(f"semanticTokenColors must be an object in {source}")
    for selector, value in raw_semantic.items():
        semantic_colors[selector] = TracedValue(value, source)

    return ResolvedTheme(
        name=str(data.get("name") or parent.name or "VS Code Dark Modern"),
        chain=[*parent.chain, source],
        colors=colors,
        token_colors=token_colors,
        semantic_colors=semantic_colors,
    )


def _load_mapping(name: str) -> Any:
    path = ROOT / "mappings" / name
    data = jsonc.load(path)
    if not isinstance(data, dict):
        raise BuildError(f"Mapping root must be an object: {path}")
    return data


def _scope_list(value: Any, context: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise BuildError(f"Scope must be a string or string array in {context}")


def _convert_font_style(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise BuildError(f"fontStyle must be a string in {context}")
    converted: list[str] = []
    for style in value.split():
        style = FONT_STYLE_ADAPTATIONS.get(style, style)
        if style not in SUPPORTED_FONT_STYLES:
            raise BuildError(f"Unsupported fontStyle {style!r} in {context}")
        if style not in converted:
            converted.append(style)
    return " ".join(converted)


def _expand_scopes(scopes: Iterable[str], aliases: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for scope in scopes:
        for candidate in (scope, *aliases.get(scope, [])):
            if candidate not in result:
                result.append(candidate)
    return result


def _convert_token_rules(
    rules: list[dict[str, Any]], aliases: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []

    for index, source_rule in enumerate(rules):
        source = source_rule["__source"]
        context = f"{source}: tokenColors[{index}]"
        if "scope" not in source_rule:
            continue
        settings = source_rule.get("settings", {})
        if not isinstance(settings, dict):
            raise BuildError(f"settings must be an object in {context}")
        unsupported = set(settings) - ALLOWED_TOKEN_SETTINGS
        if unsupported:
            raise BuildError(f"Unsupported token settings {sorted(unsupported)} in {context}")

        converted: dict[str, Any] = {}
        if source_rule.get("name"):
            converted["name"] = str(source_rule["name"])
        scopes = _expand_scopes(_scope_list(source_rule["scope"], context), aliases)
        converted["scope"] = ", ".join(scopes)
        if "foreground" in settings:
            converted["foreground"] = _validate_color(settings["foreground"], context)
        if "background" in settings:
            converted["background"] = _validate_color(settings["background"], context)
        if "fontStyle" in settings:
            converted["font_style"] = _convert_font_style(settings["fontStyle"], context)
        if len(converted) == 1 and "scope" in converted:
            raise BuildError(f"Rule has no convertible settings in {context}")
        output.append(converted)
        provenance.append({
            "kind": "token",
            "name": converted.get("name", ""),
            "scope": converted["scope"],
            "source": source,
            "foreground": converted.get("foreground"),
            "background": converted.get("background"),
        })
    return output, provenance


def _find_foreground(theme: ResolvedTheme, selector: str) -> TracedValue:
    match: TracedValue | None = None
    for index, rule in enumerate(theme.token_colors):
        if "scope" not in rule:
            continue
        scopes = _scope_list(rule["scope"], f"{rule['__source']}: tokenColors[{index}]")
        settings = rule.get("settings", {})
        if selector in scopes and isinstance(settings, dict) and "foreground" in settings:
            match = TracedValue(
                _validate_color(settings["foreground"], f"{rule['__source']}: {selector}"),
                rule["__source"],
            )
    if match is None:
        raise BuildError(f"No source foreground rule found for selector {selector!r}")
    return match


def _semantic_scope(selector: str) -> str:
    base, separator, language = selector.partition(":")
    normalized = base.lower()
    scope = "meta.semantic-token" if normalized == "*" else f"meta.semantic-token.{normalized}"
    if separator:
        scope = f"source.{language.lower()} {scope}"
    return scope


def _convert_semantic_rules(
    theme: ResolvedTheme, mapping: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = [{
        "name": "LSP semantic highlighting activation",
        "scope": "meta.semantic-token",
        "background": LSP_ACTIVATION_BACKGROUND,
    }]
    provenance: list[dict[str, Any]] = [{
        "kind": "lsp-activation",
        "name": "LSP semantic highlighting activation",
        "scope": "meta.semantic-token",
        "source": "LSP activation exception",
        "background": LSP_ACTIVATION_BACKGROUND,
    }]

    for group in mapping.get("groups", []):
        color = _find_foreground(theme, group["color_from"])
        scopes = [_semantic_scope(token) for token in group["tokens"]]
        rule = {
            "name": group["name"],
            "scope": ", ".join(scopes),
            "foreground": color.value,
        }
        output.append(rule)
        provenance.append({
            "kind": "semantic-standard",
            "name": rule["name"],
            "scope": rule["scope"],
            "source": color.source,
            "color_from": group["color_from"],
            "foreground": color.value,
        })

    for group in mapping.get("modifier_groups", []):
        color = _find_foreground(theme, group["color_from"])
        rule = {
            "name": group["name"],
            "scope": ", ".join(_semantic_scope(item) for item in group["selectors"]),
            "foreground": color.value,
        }
        output.append(rule)
        provenance.append({
            "kind": "semantic-modifier",
            "name": rule["name"],
            "scope": rule["scope"],
            "source": color.source,
            "color_from": group["color_from"],
            "foreground": color.value,
        })

    for selector, traced in theme.semantic_colors.items():
        value = traced.value
        if isinstance(value, str):
            settings = {"foreground": value}
        elif isinstance(value, dict):
            settings = value
        else:
            raise BuildError(f"Invalid semantic token value for {selector!r} in {traced.source}")
        unsupported = set(settings) - ALLOWED_TOKEN_SETTINGS
        if unsupported:
            raise BuildError(
                f"Unsupported semantic settings {sorted(unsupported)} for {selector!r} in {traced.source}"
            )
        rule: dict[str, Any] = {
            "name": f"VS Code semantic token: {selector}",
            "scope": _semantic_scope(selector),
        }
        if "foreground" in settings:
            rule["foreground"] = _validate_color(
                settings["foreground"], f"{traced.source}: semanticTokenColors.{selector}"
            )
        if "background" in settings:
            rule["background"] = _validate_color(
                settings["background"], f"{traced.source}: semanticTokenColors.{selector}"
            )
        if "fontStyle" in settings:
            rule["font_style"] = _convert_font_style(
                settings["fontStyle"], f"{traced.source}: semanticTokenColors.{selector}"
            )
        output.append(rule)
        provenance.append({
            "kind": "semantic-source",
            "name": rule["name"],
            "scope": rule["scope"],
            "source": traced.source,
            "foreground": rule.get("foreground"),
            "background": rule.get("background"),
        })
    return output, provenance


def _build_enhancement_rules(
    theme: ResolvedTheme, mapping: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for entry in mapping.get("rules", []):
        color = _find_foreground(theme, entry["color_from"])
        rule: dict[str, Any] = {
            "name": entry["name"],
            "scope": entry["scopes"],
            "foreground": color.value,
        }
        if "font_style" in entry:
            rule["font_style"] = entry["font_style"]
        output.append(rule)
        provenance.append({
            "kind": "enhancement",
            "name": rule["name"],
            "scope": rule["scope"],
            "source": color.source,
            "color_from": entry["color_from"],
            "foreground": color.value,
        })
    return output, provenance


def build(source: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    theme = resolve_theme(source)
    ui_mapping = _load_mapping("ui_colors.json")
    sublime_ui_overrides = _load_mapping("sublime_ui_overrides.json")
    aliases = _load_mapping("scope_aliases.json")
    semantic_mapping = _load_mapping("semantic_tokens.json")
    enhancement_mapping = _load_mapping("enhancements.json")

    globals_output: dict[str, str] = {}
    provenance: list[dict[str, Any]] = []
    for vscode_key, sublime_key in ui_mapping.items():
        traced = theme.colors.get(vscode_key)
        if traced is None:
            continue
        globals_output[sublime_key] = traced.value
        provenance.append({
            "kind": "global",
            "name": sublime_key,
            "vscode_key": vscode_key,
            "source": traced.source,
            "color": traced.value,
        })

    override_source = sublime_ui_overrides.get("source")
    overrides = sublime_ui_overrides.get("globals")
    if not isinstance(override_source, str) or not isinstance(overrides, dict):
        raise BuildError("sublime_ui_overrides.json requires string 'source' and object 'globals'")
    option_globals = {"brackets_options", "bracket_contents_options"}
    for name, value in overrides.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise BuildError("Sublime UI override names and values must be strings")
        if name in option_globals:
            if value != "underline":
                raise BuildError(f"Unsupported Sublime UI option {name}={value!r}")
        else:
            _validate_color(value, f"sublime_ui_overrides.json: globals.{name}")
        globals_output[name] = value
        provenance.append({
            "kind": "sublime-global-override",
            "name": name,
            "source": override_source,
            "mapping": "mappings/sublime_ui_overrides.json",
            "value": value,
        })

    token_rules, token_provenance = _convert_token_rules(theme.token_colors, aliases)
    enhancement_rules, enhancement_provenance = _build_enhancement_rules(theme, enhancement_mapping)
    semantic_rules, semantic_provenance = _convert_semantic_rules(theme, semantic_mapping)
    provenance.extend(token_provenance)
    provenance.extend(enhancement_provenance)
    provenance.extend(semantic_provenance)

    scheme = {
        "name": "VS Code Dark Modern Enhanced",
        "author": "Microsoft VS Code palette; generated Sublime Text adaptation",
        "globals": globals_output,
        "rules": [*token_rules, *enhancement_rules, *semantic_rules],
    }
    report = {
        "name": scheme["name"],
        "source_chain": theme.chain,
        "generated_rule_count": len(scheme["rules"]),
        "ignored_ui_colors": sorted(set(theme.colors) - set(ui_mapping)),
        "provenance": provenance,
    }
    return scheme, report


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "dark_modern.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "VS Code Dark Modern Enhanced.sublime-color-scheme",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "theme-build-report.json",
    )
    parser.add_argument("--check", action="store_true", help="Validate without writing files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        scheme, report = build(args.source)
        if not args.check:
            _write_json(args.output, scheme)
            _write_json(args.report, report)
        print(
            f"Built {report['name']} from {' -> '.join(report['source_chain'])}; "
            f"{report['generated_rule_count']} rules"
        )
        return 0
    except (BuildError, jsonc.JsoncError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
