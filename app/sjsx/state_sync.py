"""Collect Redux state path keys from TextInput onChange widgets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

_SJSX_PREFIX = "Sjsx_"
_TEXT_INPUT_TYPE = f"{_SJSX_PREFIX}TextInput"
_ONCHANGE_PARAM = "onChange"
_DEFAULT_ONCHANGE_KEY = "value"


def _widget_input_names(node: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for inp in node.get("inputs") or []:
        if inp.get("widget"):
            names.append(str(inp.get("name") or inp["widget"].get("name", "")))
    return [name for name in names if name]


def read_widget_values_map(node: dict[str, Any]) -> dict[str, Any]:
    names = _widget_input_names(node)
    values = node.get("widgets_values") or []
    from_widgets = {
        name: values[index] if index < len(values) else ""
        for index, name in enumerate(names)
    }

    stored = (node.get("properties") or {}).get("sjsxWidgetValues")
    if isinstance(stored, dict):
        merged = {**stored, **from_widgets}
        for name, val in stored.items():
            if not str(merged.get(name) or "").strip() and str(val or "").strip():
                merged[name] = val
        return merged

    return from_widgets


def _get_widget_value(node: dict[str, Any], name: str) -> str:
    return str(read_widget_values_map(node).get(name, "") or "").strip()


def write_widget_values_map(node: dict[str, Any], values_map: dict[str, Any]) -> None:
    props = node.setdefault("properties", {})
    active = props.get("sjsxActiveParams")
    if isinstance(active, list) and active:
        values_map = {name: values_map.get(name, "") for name in active}
    props["sjsxWidgetValues"] = dict(values_map)
    names = _widget_input_names(node)
    node["widgets_values"] = [values_map.get(name, "") for name in names]


def _set_widget_value(node: dict[str, Any], name: str, value: str) -> None:
    values_map = read_widget_values_map(node)
    values_map[name] = value
    write_widget_values_map(node, values_map)


def _sjsx_nodes_by_id(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node["id"]): node
        for node in workflow.get("nodes") or []
        if str(node.get("type", "")).startswith(_SJSX_PREFIX)
    }


def _sjsx_children_map(
    workflow: dict[str, Any],
    nodes_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = defaultdict(list)
    for link in workflow.get("links") or []:
        if not isinstance(link, (list, tuple)) or len(link) < 6:
            continue
        if str(link[5]) != "SJSX":
            continue
        origin_id, target_id = str(link[1]), str(link[3])
        if origin_id not in nodes_by_id or target_id not in nodes_by_id:
            continue
        if origin_id not in children[target_id]:
            children[target_id].append(origin_id)
    return children


def _sjsx_parent_map(children_map: dict[str, list[str]]) -> dict[str, str]:
    parent_map: dict[str, str] = {}
    for parent_id, child_ids in children_map.items():
        for child_id in child_ids:
            parent_map[child_id] = parent_id
    return parent_map


def _text_input_onchange_key(node: dict[str, Any]) -> str | None:
    if node.get("type") != _TEXT_INPUT_TYPE:
        return None

    active = set(node.get("properties", {}).get("sjsxActiveParams") or [])
    if _ONCHANGE_PARAM not in active:
        return None

    key = _get_widget_value(node, _ONCHANGE_PARAM)
    if not key or key == _DEFAULT_ONCHANGE_KEY:
        return None
    return key


def collect_state_keys(workflow: dict[str, Any], target_node: dict[str, Any]) -> list[str]:
    nodes_by_id = _sjsx_nodes_by_id(workflow)
    target_id = str(target_node["id"])
    children_map = _sjsx_children_map(workflow, nodes_by_id)
    parent_map = _sjsx_parent_map(children_map)

    keys: list[str] = []

    def walk_descendants(node_id: str) -> None:
        for child_id in children_map.get(node_id, []):
            node = nodes_by_id.get(child_id)
            if node and node.get("type") == _TEXT_INPUT_TYPE:
                key = _text_input_onchange_key(node)
                if key:
                    keys.append(key)
            walk_descendants(child_id)

    walk_descendants(target_id)

    parent_id = parent_map.get(target_id)
    if parent_id:
        for sibling_id in children_map.get(parent_id, []):
            if sibling_id == target_id:
                continue
            node = nodes_by_id.get(sibling_id)
            if node and node.get("type") == _TEXT_INPUT_TYPE:
                key = _text_input_onchange_key(node)
                if key:
                    keys.append(key)

    return sorted({key for key in keys if key})


def format_state_string(keys: list[str]) -> str:
    if not keys:
        return ""
    if len(keys) == 1:
        return keys[0]
    return ", ".join(keys)


def ensure_text_input_onchange(node: dict[str, Any], *, key: str | None = None) -> None:
    if node.get("type") != _TEXT_INPUT_TYPE:
        return

    props = node.setdefault("properties", {})
    active = list(props.get("sjsxActiveParams") or [])
    if _ONCHANGE_PARAM not in active:
        active.append(_ONCHANGE_PARAM)
        props["sjsxActiveParams"] = active

    current = _get_widget_value(node, _ONCHANGE_PARAM)
    if not current:
        resolved = (key or _DEFAULT_ONCHANGE_KEY).strip() or _DEFAULT_ONCHANGE_KEY
        _set_widget_value(node, _ONCHANGE_PARAM, resolved)
