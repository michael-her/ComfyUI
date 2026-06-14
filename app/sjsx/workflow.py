"""Convert ComfyUI workflow JSON (canvas) to SjsxGraph / .sjsx source."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from app.sjsx.emitter import emit
from app.sjsx.models import (
    SjsxAgreement,
    SjsxDefinition,
    SjsxGraph,
    SjsxMeta,
    SjsxNode,
    SjsxSection,
)
from app.sjsx.state_sync import collect_state_keys, format_state_string, read_widget_values_map

_SJSX_NODE_PREFIX = "Sjsx_"


def is_sjsx_workflow(workflow: dict[str, Any]) -> bool:
    if workflow.get("document_type") == "sjsx":
        return True
    extra = workflow.get("extra") or {}
    if extra.get("document_type") == "sjsx":
        return True
    if extra.get("sjsx"):
        return True
    for node in workflow.get("nodes") or []:
        if _is_sjsx_node(node):
            return True
    return False


def workflow_to_sjsx_source(workflow: dict[str, Any]) -> str:
    return emit(workflow_to_graph(workflow))


def workflow_to_graph(workflow: dict[str, Any]) -> SjsxGraph:
    meta = _meta_from_workflow(workflow)
    nodes_by_id = {
        str(node["id"]): node
        for node in workflow.get("nodes") or []
        if _is_sjsx_node(node)
    }
    parent_map, children_map = _build_hierarchy(workflow, nodes_by_id)
    roots = _find_roots(nodes_by_id, parent_map)

    shallow_nodes: dict[str, SjsxNode] = {}
    for node_id, node in nodes_by_id.items():
        attrs, content = _extract_node_data(node, workflow)
        shallow_nodes[node_id] = SjsxNode(
            type=_node_tag(node),
            name=_const_name(node),
            attrs=attrs,
            children=children_map.get(node_id, []),
            content=content,
        )

    definitions: list[SjsxDefinition] = []
    for root_id in roots:
        root_node = nodes_by_id[root_id]
        name = _const_name(root_node)
        body = _emit_jsx_tree(root_id, nodes_by_id, children_map, indent=1, workflow=workflow)
        definitions.append(SjsxDefinition(name=name, body=f"(\n{body}\n)"))

    components = sorted({_node_tag(node) for node in nodes_by_id.values()})
    section = SjsxSection(
        comment="// ─── UI Layer ───",
        definitions=definitions,
    )

    return SjsxGraph(
        header=_default_header(meta),
        meta=meta,
        agreement=SjsxAgreement(pending=["Initial layout"]),
        sections=[section] if definitions else [],
        components=components,
        nodes=shallow_nodes,
    )


def _meta_from_workflow(workflow: dict[str, Any]) -> SjsxMeta:
    extra = workflow.get("extra") or {}
    sjsx = extra.get("sjsx") or {}
    return SjsxMeta(
        domain=sjsx.get("domain") or "NewApp",
        layer=sjsx.get("layer") or "ui",
        status=sjsx.get("status") or "design",
    )


def _default_header(meta: SjsxMeta) -> str:
    domain = meta.domain or "NewApp"
    layer = meta.layer or "ui"
    status = meta.status or "design"
    return f'''/**
 * @sjsx
 * domain: {domain}
 * layer: {layer}
 * status: {status}
 *
 * Agreement items:
 * [ ] Initial layout
 *
 * NOTE: Design-only export from ComfyUI canvas. Not a buildable app entry.
 */'''


def _is_sjsx_node(node: dict[str, Any]) -> bool:
    return str(node.get("type", "")).startswith(_SJSX_NODE_PREFIX)


def _node_tag(node: dict[str, Any]) -> str:
    node_type = str(node.get("type", ""))
    if node_type.startswith(_SJSX_NODE_PREFIX):
        return node_type[len(_SJSX_NODE_PREFIX) :]
    return node_type


def _const_name(node: dict[str, Any]) -> str:
    title = str(node.get("title") or "").strip()
    if title:
        cleaned = re.sub(r"[^\w]+", "", title.replace(" ", ""))
        if cleaned and cleaned[0].isalpha():
            return cleaned[0].lower() + cleaned[1:]
    tag = _node_tag(node)
    if not tag:
        return "root"
    return tag[0].lower() + tag[1:] if len(tag) > 1 else tag.lower()


def _iter_sjsx_links(workflow: dict[str, Any]):
    for link in workflow.get("links") or []:
        if isinstance(link, dict):
            yield (
                str(link["origin_id"]),
                str(link["target_id"]),
                str(link.get("type") or ""),
            )
        elif isinstance(link, (list, tuple)) and len(link) >= 6:
            yield (str(link[1]), str(link[3]), str(link[5]))


def _build_hierarchy(
    workflow: dict[str, Any],
    nodes_by_id: dict[str, dict[str, Any]],
):
    parent_map: dict[str, str] = {}
    children_map: dict[str, list[str]] = defaultdict(list)

    for origin_id, target_id, link_type in _iter_sjsx_links(workflow):
        if link_type != "SJSX":
            continue
        if origin_id not in nodes_by_id or target_id not in nodes_by_id:
            continue
        if origin_id not in children_map[target_id]:
            children_map[target_id].append(origin_id)
        parent_map[origin_id] = target_id

    return parent_map, children_map


def _find_roots(
    nodes_by_id: dict[str, dict[str, Any]],
    parent_map: dict[str, str],
) -> list[str]:
    entry_points: list[str] = []
    roots: list[str] = []
    for node_id, node in nodes_by_id.items():
        attrs, _ = _extract_node_data(node)
        if attrs.get("cx") == "entry-point":
            entry_points.append(node_id)
        if node_id not in parent_map:
            roots.append(node_id)
    if entry_points:
        return entry_points
    return roots or list(nodes_by_id.keys())


def _extract_node_data(
    node: dict[str, Any],
    workflow: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    attrs: dict[str, Any] = {}
    content: str | None = None
    active = node.get("properties", {}).get("sjsxActiveParams")
    active_set = set(active) if isinstance(active, list) else None
    values_map = read_widget_values_map(node)

    for name, value in values_map.items():
        if active_set is not None and name not in active_set:
            continue
        if value is None or value == "" or value is False:
            continue
        if isinstance(value, (int, float)) and value == 0:
            continue
        if name == "content":
            content = str(value)
        elif name == "onChange" and str(value).strip() == "value":
            continue
        else:
            attrs[name] = value

    if workflow is not None and _node_tag(node) == "View" and "state" not in attrs:
        active_list = list(node.get("properties", {}).get("sjsxActiveParams") or [])
        if "state" not in active_list:
            keys = collect_state_keys(workflow, node)
            if keys:
                attrs["state"] = format_state_string(keys)

    return attrs, content


def _state_keys_for_node(
    node: dict[str, Any],
    workflow: dict[str, Any] | None,
) -> list[str]:
    if workflow is None:
        return []
    return collect_state_keys(workflow, node)


def _escape_jsx_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
    )


def _format_jsx_text_content(content: str, state_keys: list[str]) -> str:
    """Escape literal text but preserve `{key}` placeholders wired via state."""
    if not state_keys:
        return _escape_jsx_text(content)

    token_re = re.compile(
        r"\{(" + "|".join(re.escape(key) for key in state_keys) + r")\}"
    )
    parts: list[str] = []
    last = 0
    for match in token_re.finditer(content):
        if match.start() > last:
            parts.append(_escape_jsx_text(content[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    if last < len(content):
        parts.append(_escape_jsx_text(content[last:]))
    return "".join(parts)


def _format_attr(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{key}={{{str(value).lower()}}}"
    if isinstance(value, (int, float)):
        return f"{key}={{{value}}}"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f"{key}={{{json.dumps(value)}}}"


def _emit_jsx_tree(
    node_id: str,
    nodes_by_id: dict[str, dict[str, Any]],
    children_map: dict[str, list[str]],
    *,
    indent: int,
    workflow: dict[str, Any] | None = None,
) -> str:
    node = nodes_by_id[node_id]
    tag = _node_tag(node)
    attrs, content = _extract_node_data(node, workflow)
    state_keys = _state_keys_for_node(node, workflow)
    children = children_map.get(node_id, [])
    pad = "  " * indent
    attr_part = (
        " " + " ".join(_format_attr(key, value) for key, value in sorted(attrs.items()))
        if attrs
        else ""
    )

    if children:
        lines = [f"{pad}<{tag}{attr_part}>"]
        for child_id in children:
            lines.append(
                _emit_jsx_tree(
                    child_id,
                    nodes_by_id,
                    children_map,
                    indent=indent + 1,
                    workflow=workflow,
                )
            )
        lines.append(f"{pad}</{tag}>")
        return "\n".join(lines)

    if content is not None:
        body = _format_jsx_text_content(content, state_keys)
        return f"{pad}<{tag}{attr_part}>{body}</{tag}>"

    if attr_part:
        return f"{pad}<{tag}{attr_part} />"
    return f"{pad}<{tag} />"
