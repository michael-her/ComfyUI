from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.sjsx.parser import _extract_balanced, _extract_jsx_self_closing, parse


@dataclass
class JsxElement:
    tag: str
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list[JsxElement] = field(default_factory=list)
    content: str | None = None

    def signature(self) -> tuple[Any, ...]:
        return (
            self.tag,
            self.content,
            tuple(sorted((key, _normalize_attr(value)) for key, value in self.attrs.items())),
        )


def _normalize_attr(value: Any) -> Any:
    if isinstance(value, str):
        if value in ("true", "false"):
            return value == "true"
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    return value


def _parse_attr_value(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


_ATTR_RE = re.compile(
    r"""
    (?P<name>[A-Za-z_]\w*)
    =
    (?:
        "(?P<dquote>[^"]*)"
      | \{(?P<brace>[^}]*)\}
    )
    """,
    re.VERBOSE,
)


def _parse_attrs(fragment: str) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for match in _ATTR_RE.finditer(fragment):
        name = match.group("name")
        if match.group("dquote") is not None:
            attrs[name] = match.group("dquote")
        else:
            attrs[name] = _parse_attr_value(match.group("brace") or "")
    return attrs


def _unescape_jsx_text(value: str) -> str:
    return (
        value.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&#123;", "{")
        .replace("&#125;", "}")
    )


def _is_self_closing(text: str) -> bool:
    gt = text.find(">")
    return gt > 0 and text[gt - 1] == "/"


def _parse_self_closing(text: str) -> tuple[JsxElement, int]:
    tag_match = re.match(r"<\s*([A-Z][A-Za-z0-9]*)", text)
    if not tag_match:
        raise ValueError("Invalid self-closing JSX")
    tag = tag_match.group(1)
    opening, consumed = _extract_jsx_self_closing(text)
    attrs_part = opening[tag_match.end() : opening.rfind("/>")]
    return JsxElement(tag=tag, attrs=_parse_attrs(attrs_part)), consumed


def _parse_element(text: str) -> JsxElement:
    text = text.strip()
    if not text.startswith("<"):
        raise ValueError("Expected JSX element")
    if _is_self_closing(text):
        element, _ = _parse_self_closing(text)
        return element

    tag_match = re.match(r"<\s*([A-Z][A-Za-z0-9]*)", text)
    if not tag_match:
        raise ValueError("Invalid JSX opening tag")
    tag = tag_match.group(1)

    close_token = f"</{tag}>"
    close_index = text.find(close_token)
    if close_index == -1:
        raise ValueError(f"Unclosed JSX element <{tag}>")

    opening_end = text.index(">", tag_match.end()) + 1
    attrs_part = text[tag_match.end() : opening_end - 1]
    inner = text[opening_end:close_index].strip()
    element = JsxElement(tag=tag, attrs=_parse_attrs(attrs_part))

    if not inner:
        return element

    if inner.startswith("<"):
        remaining = inner
        while remaining.strip():
            child, consumed = _parse_element_chunk(remaining)
            element.children.append(child)
            remaining = remaining[consumed:].strip()
        return element

    element.content = _unescape_jsx_text(inner)
    return element


def _parse_element_chunk(text: str) -> tuple[JsxElement, int]:
    text = text.lstrip()
    if not text.startswith("<"):
        raise ValueError("Expected child JSX element")
    if _is_self_closing(text):
        return _parse_self_closing(text)

    tag_match = re.match(r"<\s*([A-Z][A-Za-z0-9]*)", text)
    if not tag_match:
        raise ValueError("Invalid child JSX")

    tag = tag_match.group(1)

    close_token = f"</{tag}>"
    close_index = text.find(close_token)
    if close_index == -1:
        raise ValueError(f"Unclosed child <{tag}>")
    close_end = close_index + len(close_token)
    return _parse_element(text[:close_end]), close_end


def parse_jsx_tree(text: str) -> JsxElement:
    stripped = text.strip()
    while stripped.startswith("("):
        inner, _ = _extract_balanced(stripped, "(", ")")
        stripped = inner[1:-1].strip()
    return _parse_element(stripped)


def find_main_definition_body(source: str) -> tuple[str, str]:
    graph = parse(source)
    for section in graph.sections:
        for definition in section.definitions:
            if definition.name == "main":
                return definition.name, definition.body
    for section in graph.sections:
        for definition in section.definitions:
            if 'cx="entry-point"' in definition.body or "cx='entry-point'" in definition.body:
                return definition.name, definition.body
    for section in graph.sections:
        if section.definitions:
            definition = section.definitions[0]
            return definition.name, definition.body
    raise ValueError("No component definition found in .sjsx source")


def tree_from_sjsx_source(source: str) -> tuple[str, JsxElement]:
    name, body = find_main_definition_body(source)
    return name, parse_jsx_tree(body)
