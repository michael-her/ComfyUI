from __future__ import annotations

import re
from typing import Any

from app.sjsx.models import (
    SjsxAgreement,
    SjsxDefinition,
    SjsxGraph,
    SjsxMeta,
    SjsxNode,
    SjsxSection,
)

HEADER_RE = re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE)
META_BLOCK_RE = re.compile(r"@sjsx([\s\S]*?)\*/")
AGREED_RE = re.compile(r"\[x\]\s*(.+)", re.MULTILINE)
PENDING_RE = re.compile(r"\[ \]\s*(.+)", re.MULTILINE)
COMPONENT_RE = re.compile(r"<([A-Z][A-Za-z0-9]*)")
SECTION_SPLIT_RE = re.compile(r"(?m)^(?=// ───)")
DEF_START_RE = re.compile(r"^const (\w+) = ", re.MULTILINE)


def _meta_from_block(block: str) -> SjsxMeta:
    def get(key: str) -> str | None:
        match = re.search(rf"{key}:\s*(.+)", block)
        return match.group(1).strip() if match else None

    return SjsxMeta(
        domain=get("domain"),
        layer=get("layer"),
        status=get("status"),
    )


def extract_meta(source: str) -> SjsxMeta:
    match = META_BLOCK_RE.search(source)
    if not match:
        return SjsxMeta()
    return _meta_from_block(match.group(1))


def extract_agreement(source: str) -> SjsxAgreement:
    header_match = HEADER_RE.search(source)
    scope = header_match.group(0) if header_match else source
    agreed = [m.group(1).strip() for m in AGREED_RE.finditer(scope)]
    pending = [m.group(1).strip() for m in PENDING_RE.finditer(scope)]
    return SjsxAgreement(agreed=agreed, pending=pending)


def extract_components(source: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in COMPONENT_RE.finditer(source):
        tag = match.group(1)
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def detect_layer(source: str, meta: SjsxMeta | None = None) -> str:
    if meta and meta.layer:
        return meta.layer
    if "ThreadPool" in source or "DbJob" in source:
        return "system"
    if "View" in source or "TouchableOpacity" in source:
        return "ui"
    return "unknown"


def _extract_balanced(text: str, open_char: str, close_char: str) -> tuple[str, int]:
    if not text.startswith(open_char):
        raise ValueError(f"Expected {open_char!r} at start")
    depth = 0
    in_string: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[: i + 1], i + 1
        i += 1
    raise ValueError(f"Unbalanced {open_char}{close_char}")


def _extract_jsx_self_closing(text: str) -> tuple[str, int]:
    if not text.startswith("<"):
        raise ValueError("Expected JSX element")
    in_string: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if text.startswith("/>", i):
            return text[: i + 2], i + 2
        i += 1
    raise ValueError("Unterminated JSX element")


def _extract_rhs(text: str, start: int) -> tuple[str, int]:
    rest = text[start:]
    leading = len(rest) - len(rest.lstrip())
    rest = rest.lstrip()
    abs_start = start + leading
    if rest.startswith("("):
        body, consumed = _extract_balanced(rest, "(", ")")
        return body, abs_start + consumed
    if rest.startswith("<"):
        body, consumed = _extract_jsx_self_closing(rest)
        return body, abs_start + consumed
    raise ValueError(f"Unsupported RHS at offset {start}")


def _split_sections(body: str) -> list[SjsxSection]:
    parts = SECTION_SPLIT_RE.split(body)
    sections: list[SjsxSection] = []
    for part in parts:
        part = part.strip("\n")
        if not part.strip():
            continue
        comment: str | None = None
        if part.startswith("// ───"):
            lines = part.split("\n", 1)
            comment = lines[0].strip()
            content = lines[1] if len(lines) > 1 else ""
        else:
            content = part
        definitions: list[SjsxDefinition] = []
        for match in DEF_START_RE.finditer(content):
            name = match.group(1)
            rhs_start = match.end()
            body_text, _ = _extract_rhs(content, rhs_start)
            definitions.append(SjsxDefinition(name=name, body=body_text))
        if comment or definitions:
            sections.append(SjsxSection(comment=comment, definitions=definitions))
    return sections


def _shallow_nodes_from_definitions(sections: list[SjsxSection]) -> dict[str, SjsxNode]:
    nodes: dict[str, SjsxNode] = {}
    counter = 1
    for section in sections:
        for definition in section.definitions:
            root_id = str(counter)
            counter += 1
            tag_match = re.search(r"<\s*([A-Z][A-Za-z0-9]*)", definition.body)
            tag = tag_match.group(1) if tag_match else definition.name
            attrs: dict[str, Any] = {}
            for attr_match in re.finditer(r'(\w+)=\{([^}]+)\}|(\w+)="([^"]*)"|(\w+)=\{`([^`]*)`\}', definition.body):
                if attr_match.group(1):
                    attrs[attr_match.group(1)] = attr_match.group(2)
                elif attr_match.group(3):
                    attrs[attr_match.group(3)] = attr_match.group(4)
                elif attr_match.group(5):
                    attrs[attr_match.group(5)] = attr_match.group(6)
            cx_match = re.search(r'cx="([^"]*)"', definition.body)
            if cx_match:
                attrs["cx"] = cx_match.group(1)
            nodes[root_id] = SjsxNode(type=tag, attrs=attrs, children=[])
    return nodes


def parse(source: str) -> SjsxGraph:
    header_match = HEADER_RE.search(source)
    header = header_match.group(0) if header_match else ""
    body = source[header_match.end() :] if header_match else source
    meta = extract_meta(source)
    agreement = extract_agreement(source)
    if not meta.layer:
        meta.layer = detect_layer(source, meta)
    sections = _split_sections(body)
    components = extract_components(source)
    nodes = _shallow_nodes_from_definitions(sections)
    return SjsxGraph(
        header=header.strip(),
        meta=meta,
        agreement=agreement,
        sections=sections,
        components=components,
        nodes=nodes,
    )
