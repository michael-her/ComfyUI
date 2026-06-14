"""Normalize SJSX workflow JSON before save/load."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.sjsx.state_sync import read_widget_values_map, write_widget_values_map
from app.sjsx.workflow import is_sjsx_workflow

_SJSX_PREFIX = "Sjsx_"
_VIEW_TYPE = f"{_SJSX_PREFIX}View"
_TEXT_TYPE = f"{_SJSX_PREFIX}Text"
_TEXT_INPUT_TYPE = f"{_SJSX_PREFIX}TextInput"
_STATE_PARAM = "state"
_TEXT_INPUT_DROP_PARAMS = frozenset({"cx", "keyboardType"})


def _meaningful_text_input_param(name: str, value: Any) -> bool:
    if value is None or value == "" or value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if name == "keyboardType" and str(value).strip() == "default":
        return False
    return True


def _normalize_text_input_node(node: dict[str, Any]) -> None:
    from app.sjsx.vocabulary import components_by_tag
    from app.sjsx.workflow_apply import _build_node_from_vocabulary

    component = components_by_tag().get("TextInput")
    if not component:
        return

    values_map = read_widget_values_map(node)
    props = node.setdefault("properties", {})
    active = list(props.get("sjsxActiveParams") or [])

    for name in _TEXT_INPUT_DROP_PARAMS:
        if not _meaningful_text_input_param(name, values_map.get(name)):
            active = [param for param in active if param != name]
            values_map.pop(name, None)

    default_active = list(dict.fromkeys([*(component.get("default_params") or []), "onChange"]))
    if not active:
        active = default_active

    props["sjsxActiveParams"] = active

    template = _build_node_from_vocabulary("TextInput", component)
    old_outputs = list(node.get("outputs") or [])
    new_outputs = list(template["outputs"])
    for index, out in enumerate(new_outputs):
        if index < len(old_outputs) and old_outputs[index].get("links"):
            out["links"] = list(old_outputs[index]["links"])
    node["inputs"] = template["inputs"]
    node["outputs"] = new_outputs

    filtered_map = {name: values_map[name] for name in active if name in values_map}
    for name in active:
        filtered_map.setdefault(name, values_map.get(name, ""))
    write_widget_values_map(node, filtered_map)


def _normalize_text_node(node: dict[str, Any]) -> None:
    from app.sjsx.vocabulary import components_by_tag
    from app.sjsx.workflow_apply import _build_node_from_vocabulary

    component = components_by_tag().get("Text")
    if not component:
        return

    values_map = read_widget_values_map(node)
    props = node.setdefault("properties", {})
    active = list(props.get("sjsxActiveParams") or [])
    content = str(values_map.get("content", "") or "")

    default_active = list(component.get("default_params") or ["content"])
    if content and "content" not in active:
        active.append("content")
    if not active:
        active = default_active

    props["sjsxActiveParams"] = active

    template = _build_node_from_vocabulary("Text", component)
    old_outputs = list(node.get("outputs") or [])
    new_outputs = list(template["outputs"])
    for index, out in enumerate(new_outputs):
        if index < len(old_outputs) and old_outputs[index].get("links"):
            out["links"] = list(old_outputs[index]["links"])
    node["inputs"] = template["inputs"]
    node["outputs"] = new_outputs

    filtered_map = {name: values_map.get(name, "") for name in active}
    write_widget_values_map(node, filtered_map)


def _normalize_view_node(node: dict[str, Any], workflow: dict[str, Any]) -> None:
    from app.sjsx.state_sync import collect_state_keys, format_state_string
    from app.sjsx.vocabulary import components_by_tag
    from app.sjsx.workflow_apply import (
        _build_node_from_vocabulary,
        _ensure_on_demand_inputs,
        _widget_input_names,
    )

    component = components_by_tag().get("View")
    if not component:
        return

    values_map = read_widget_values_map(node)
    props = node.setdefault("properties", {})
    active = list(props.get("sjsxActiveParams") or [])
    state = str(values_map.get("state", "") or "").strip()
    if not state and "state" not in active:
        keys = collect_state_keys(workflow, node)
        if keys:
            state = format_state_string(keys)
            values_map["state"] = state

    if state and "state" not in active:
        active.append("state")
    if _STATE_PARAM in active and not state:
        active = [name for name in active if name != _STATE_PARAM]

    props["sjsxActiveParams"] = active

    template = _build_node_from_vocabulary("View", component)
    old_outputs = list(node.get("outputs") or [])
    new_outputs = list(template["outputs"])
    for index, out in enumerate(new_outputs):
        if index < len(old_outputs) and old_outputs[index].get("links"):
            out["links"] = list(old_outputs[index]["links"])
    node["inputs"] = template["inputs"]
    node["outputs"] = new_outputs

    if state:
        _ensure_on_demand_inputs(node, component, {"state": state})
        widget_names = _widget_input_names(node)
        if "state" in widget_names:
            index = widget_names.index("state")
            widgets_values = list(node.get("widgets_values") or [])
            while len(widgets_values) <= index:
                widgets_values.append("")
            widgets_values[index] = state
            node["widgets_values"] = widgets_values

    filtered_map = {name: values_map.get(name, "") for name in active}
    write_widget_values_map(node, filtered_map)


def _is_state_input(inp: dict[str, Any]) -> bool:
    """Legacy graph port only — not vocabulary widget-backed state attrs."""
    return (
        inp.get("name") == _STATE_PARAM
        and inp.get("type") == "STRING"
        and not inp.get("widget")
    )


def _strip_state_input(node: dict[str, Any]) -> None:
    inputs = node.get("inputs") or []
    if not any(_is_state_input(inp) for inp in inputs):
        return

    node["inputs"] = [inp for inp in inputs if not _is_state_input(inp)]
    values_map = read_widget_values_map(node)
    values_map.pop(_STATE_PARAM, None)
    write_widget_values_map(node, values_map)

    props = node.setdefault("properties", {})
    active = list(props.get("sjsxActiveParams") or [])
    if _STATE_PARAM in active:
        props["sjsxActiveParams"] = [name for name in active if name != _STATE_PARAM]


def normalize_sjsx_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    if not is_sjsx_workflow(workflow):
        return workflow

    nodes_by_id = {
        node["id"]: node
        for node in workflow.get("nodes") or []
        if isinstance(node, dict) and "id" in node
    }

    valid_links: list[list[Any]] = []
    for link in workflow.get("links") or []:
        if not isinstance(link, (list, tuple)) or len(link) < 6:
            continue

        link_id, origin_id, origin_slot, target_id, target_slot, link_type = link[:6]
        if origin_id not in nodes_by_id or target_id not in nodes_by_id:
            continue

        origin_node = nodes_by_id[origin_id]
        if origin_node.get("type") == _TEXT_INPUT_TYPE and str(link_type) == "STRING":
            continue

        valid_links.append(
            [link_id, origin_id, origin_slot, target_id, target_slot, link_type]
        )

    workflow["links"] = valid_links
    valid_link_ids = {link[0] for link in valid_links}

    links_by_origin: dict[tuple[int, int], list[Any]] = defaultdict(list)
    links_by_target: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for link in valid_links:
        link_id, origin_id, origin_slot, target_id, target_slot, _ = link
        links_by_origin[(origin_id, origin_slot)].append(link_id)
        links_by_target[(target_id, target_slot)].append(link_id)

    for node in workflow.get("nodes") or []:
        write_widget_values_map(node, read_widget_values_map(node))
        _strip_state_input(node)
        if node.get("type") == _TEXT_INPUT_TYPE:
            _normalize_text_input_node(node)
        if node.get("type") == _TEXT_TYPE:
            _normalize_text_node(node)
        if node.get("type") == _VIEW_TYPE:
            _normalize_view_node(node, workflow)

    for node in workflow.get("nodes") or []:
        node_id = node["id"]

        if node.get("type") == _TEXT_INPUT_TYPE:
            node["outputs"] = [
                out
                for out in node.get("outputs") or []
                if out.get("type") != "STRING"
            ]

        for index, inp in enumerate(node.get("inputs") or []):
            target_links = links_by_target.get((node_id, index), [])
            inp["link"] = target_links[0] if target_links else None

        for index, out in enumerate(node.get("outputs") or []):
            origin_links = links_by_origin.get((node_id, index), [])
            out["links"] = origin_links if origin_links else None

        for inp in node.get("inputs") or []:
            if inp.get("name") == "onChange":
                inp["label"] = "onChange"
                inp["localized_name"] = "onChange"
                widget = inp.get("widget")
                if isinstance(widget, dict):
                    widget["name"] = "onChange"

    if valid_link_ids:
        workflow["last_link_id"] = max(
            int(workflow.get("last_link_id") or 0),
            max(int(link_id) for link_id in valid_link_ids),
        )

    for node in workflow.get("nodes") or []:
        write_widget_values_map(node, read_widget_values_map(node))

    return workflow
