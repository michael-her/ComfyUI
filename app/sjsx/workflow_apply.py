from __future__ import annotations

import copy
from typing import Any

from app.sjsx.jsx_tree import JsxElement, tree_from_sjsx_source
from app.sjsx.parser import extract_meta
from app.sjsx.state_sync import (
    ensure_text_input_onchange,
    read_widget_values_map,
    write_widget_values_map,
)
from app.sjsx.vocabulary import components_by_tag
from app.sjsx.workflow import (
    _build_hierarchy,
    _const_name,
    _extract_node_data,
    _find_roots,
    _is_sjsx_node,
    _node_tag,
)

_SJSX_PREFIX = "Sjsx_"
_DEFAULT_SIZE = [270, 200]
_CHILD_OFFSET_X = -420
_CHILD_OFFSET_Y = 80


def _component_by_tag() -> dict[str, dict[str, Any]]:
    return components_by_tag()


def _alloc_id(workflow: dict[str, Any], key: str) -> int:
    current = int(workflow.get(key, 0))
    next_id = current + 1
    workflow[key] = next_id
    return next_id


def _alloc_link_id(workflow: dict[str, Any]) -> int:
    return _alloc_id(workflow, "last_link_id")


def _index_templates(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    for node in workflow.get("nodes") or []:
        node_type = str(node.get("type", ""))
        if not node_type.startswith(_SJSX_PREFIX):
            continue
        tag = node_type[len(_SJSX_PREFIX) :]
        templates.setdefault(tag, copy.deepcopy(node))
    if templates:
        templates["_fallback"] = copy.deepcopy(next(iter(templates.values())))
    return templates


def _index_positions(workflow: dict[str, Any]) -> dict[tuple[Any, ...], list[float]]:
    nodes_by_id = {
        str(node["id"]): node
        for node in workflow.get("nodes") or []
        if _is_sjsx_node(node)
    }
    parent_map, children_map = _build_hierarchy(workflow, nodes_by_id)
    roots = _find_roots(nodes_by_id, parent_map)
    positions: dict[tuple[Any, ...], list[float]] = {}

    def walk(node_id: str, path: tuple[int, ...]) -> None:
        node = nodes_by_id[node_id]
        attrs, content = _extract_node_data(node)
        positions[( _node_tag(node), content, tuple(sorted(attrs.items())) )] = list(node.get("pos") or _DEFAULT_SIZE)
        for index, child_id in enumerate(children_map.get(node_id, [])):
            walk(child_id, path + (index,))

    for root_id in roots:
        walk(root_id, ())
    return positions


def _widget_input_names(node: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for inp in node.get("inputs") or []:
        if inp.get("widget"):
            names.append(inp.get("name") or inp["widget"].get("name", ""))
    return [name for name in names if name]


def _get_widget_value(node: dict[str, Any], name: str) -> str:
    return str(read_widget_values_map(node).get(name, "") or "").strip()


def _input_type_for_attr(spec: dict[str, Any]) -> str:
    attr_type = spec.get("type", "string")
    if attr_type == "boolean":
        return "BOOLEAN"
    if attr_type == "number":
        return "FLOAT"
    if attr_type == "enum":
        return "COMBO"
    return "STRING"


def _default_widget_value(spec: dict[str, Any]) -> Any:
    attr_type = spec.get("type", "string")
    if attr_type == "boolean":
        return False
    if attr_type == "number":
        return 0
    return ""


def _build_input_slot(name: str, *, widget: bool, input_type: str = "STRING") -> dict[str, Any]:
    slot: dict[str, Any] = {
        "label": name,
        "localized_name": name,
        "name": name,
        "shape": 7,
        "type": input_type,
        "link": None,
    }
    if widget:
        slot["widget"] = {"name": name}
    return slot


def _is_sjsx_child_input(inp: dict[str, Any], tag: str) -> bool:
    if inp.get("type") != "SJSX":
        return False
    name = str(inp.get("name") or "")
    if name == tag:
        return True
    return name.startswith(f"{tag}.View")


def _collapse_autogrow_child_inputs(
    workflow: dict[str, Any],
    node: dict[str, Any],
    tag: str,
) -> None:
    inputs = node.get("inputs") or []
    child_indices = [
        index for index, inp in enumerate(inputs) if _is_sjsx_child_input(inp, tag)
    ]
    if not child_indices:
        return
    if len(child_indices) == 1:
        slot = inputs[child_indices[0]]
        slot["name"] = tag
        slot["label"] = tag
        slot["localized_name"] = tag
        return

    primary = child_indices[0]
    removed = sorted(child_indices[1:])
    removed_set = set(removed)
    node_id = node["id"]
    for link in workflow.get("links") or []:
        if not isinstance(link, (list, tuple)) or len(link) < 5:
            continue
        if link[3] != node_id:
            continue
        target_slot = link[4]
        if target_slot in removed_set:
            link[4] = primary
        elif target_slot > primary:
            link[4] = target_slot - sum(1 for index in removed if index < target_slot)

    for index in sorted(removed, reverse=True):
        del inputs[index]

    slot = inputs[primary]
    slot["name"] = tag
    slot["label"] = tag
    slot["localized_name"] = tag


def _child_input_slot(parent_tag: str, parent_node: dict[str, Any]) -> int:
    for index, inp in enumerate(parent_node.get("inputs") or []):
        if inp.get("type") == "SJSX" and inp.get("name") == parent_tag:
            return index
    for index, inp in enumerate(parent_node.get("inputs") or []):
        if _is_sjsx_child_input(inp, parent_tag):
            return index
    return 0


def _build_outputs_from_vocabulary(tag: str, component: dict[str, Any]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    explicit = component.get("outputs")
    specs = explicit if explicit else (
        [{"id": "element", "type": "SJSX", "display_name": tag}]
        if component.get("can_have_children")
        else []
    )
    for spec in specs:
        out_type = spec.get("type", "SJSX")
        out_id = spec["id"]
        display = spec.get("display_name", tag if out_type == "SJSX" else out_id)
        name = tag if out_type == "SJSX" and out_id == "element" else out_id
        outputs.append(
            {
                "localized_name": display,
                "name": name,
                "type": out_type,
                "links": [],
            }
        )
    return outputs


def _sync_ports_from_vocabulary(node: dict[str, Any], tag: str, component: dict[str, Any]) -> None:
    if not component:
        return

    old_outputs = list(node.get("outputs") or [])
    new_outputs = _build_outputs_from_vocabulary(tag, component)
    for index, out in enumerate(new_outputs):
        if index >= len(old_outputs):
            continue
        old = old_outputs[index]
        links = old.get("links")
        if links:
            out["links"] = list(links)
    node["outputs"] = new_outputs


def _ensure_on_demand_inputs(
    node: dict[str, Any],
    component: dict[str, Any],
    values: dict[str, Any],
) -> None:
    inputs = list(node.get("inputs") or [])
    widgets_values = list(node.get("widgets_values") or [])
    widget_names = _widget_input_names({"inputs": inputs})

    for attr_name, spec in component.get("attrs", {}).items():
        if not spec.get("on_demand"):
            continue
        if attr_name in widget_names:
            continue
        value = values.get(attr_name)
        if value in (None, "", False) and value != 0:
            continue
        inputs.append(
            _build_input_slot(attr_name, widget=True, input_type=_input_type_for_attr(spec))
        )
        widgets_values.append(value)

    node["inputs"] = inputs
    node["widgets_values"] = widgets_values


def _build_node_from_vocabulary(tag: str, component: dict[str, Any]) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    widgets_values: list[Any] = []

    if component.get("can_have_children"):
        inputs.append(_build_input_slot(tag, widget=False, input_type="SJSX"))

    for attr_name, spec in component.get("attrs", {}).items():
        if spec.get("on_demand"):
            continue
        inputs.append(
            _build_input_slot(attr_name, widget=True, input_type=_input_type_for_attr(spec))
        )
        widgets_values.append(_default_widget_value(spec))

    for event_name in component.get("events", {}):
        inputs.append(_build_input_slot(event_name, widget=True, input_type="STRING"))
        if tag == "TextInput" and event_name == "onChange":
            widgets_values.append("value")
        else:
            widgets_values.append("")

    if component.get("content_slot"):
        inputs.append(_build_input_slot("content", widget=True, input_type="STRING"))
        widgets_values.append("")

    default_params = list(component.get("default_params") or [])
    if tag == "TextInput":
        default_params = list(dict.fromkeys([*default_params, "onChange"]))

    return {
        "type": f"{_SJSX_PREFIX}{tag}",
        "pos": [0, 0],
        "size": list(_DEFAULT_SIZE),
        "flags": {"collapsed": False},
        "order": 0,
        "mode": 0,
        "showAdvanced": False,
        "inputs": inputs,
        "outputs": _build_outputs_from_vocabulary(tag, component),
        "title": "",
        "properties": {
            "Node name for S&R": f"{_SJSX_PREFIX}{tag}",
            "sjsxActiveParams": default_params,
            "sjsxParamsVersion": 0,
        },
        "widgets_values": widgets_values,
    }


def _resolve_template(tag: str, templates: dict[str, dict[str, Any]], components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if tag in templates:
        return copy.deepcopy(templates[tag])
    component = components.get(tag)
    if component:
        return _build_node_from_vocabulary(tag, component)
    if "_fallback" in templates:
        node = copy.deepcopy(templates["_fallback"])
        node["type"] = f"{_SJSX_PREFIX}{tag}"
        return node
    raise ValueError(f"No workflow template available for <{tag}>")


def _set_node_values(
    node: dict[str, Any],
    element: JsxElement,
    *,
    title: str | None,
    components: dict[str, dict[str, Any]],
    template_onchange: str = "",
    template_content: str = "",
) -> None:
    component = components.get(element.tag, {})
    active_params: list[str] = []
    existing_active = list((node.get("properties") or {}).get("sjsxActiveParams") or [])

    widget_names = _widget_input_names(node)
    values: dict[str, Any] = dict(element.attrs)
    if element.content is not None and component.get("content_slot"):
        values["content"] = element.content

    preserved_onchange = ""
    if element.tag == "TextInput" and "onChange" not in values:
        preserved_onchange = template_onchange

    preserved_content = ""
    if element.tag == "Text" and component.get("content_slot") and "content" not in values:
        preserved_content = template_content

    _ensure_on_demand_inputs(node, component, values)
    widget_names = _widget_input_names(node)

    widgets_values: list[Any] = []
    for name in widget_names:
        if name in values and values[name] not in (None, "", False) and values[name] != 0:
            active_params.append(name)
            widgets_values.append(values[name])
        elif name == "onChange" and preserved_onchange:
            active_params.append(name)
            widgets_values.append(preserved_onchange)
        elif name == "content" and preserved_content:
            active_params.append(name)
            widgets_values.append(preserved_content)
        else:
            spec = component.get("attrs", {}).get(name, {})
            widgets_values.append(_default_widget_value(spec) if spec else "")

    if component.get("content_slot") and "content" in existing_active and "content" not in active_params:
        active_params.append("content")
        if "content" in widget_names:
            index = widget_names.index("content")
            if not widgets_values[index]:
                widgets_values[index] = preserved_content or read_widget_values_map(node).get("content", "")

    node["widgets_values"] = widgets_values
    node["properties"] = node.get("properties") or {}
    node["properties"]["sjsxActiveParams"] = active_params
    node["properties"]["sjsxParamsVersion"] = int(
        node["properties"].get("sjsxParamsVersion", 0)
    ) + 1
    write_widget_values_map(node, {name: widgets_values[widget_names.index(name)] for name in active_params if name in widget_names})
    if title is not None:
        node["title"] = title


def _clear_sjsx_input_links(node: dict[str, Any], tag: str | None = None) -> None:
    for inp in node.get("inputs") or []:
        if inp.get("type") != "SJSX":
            continue
        if tag is not None and not _is_sjsx_child_input(inp, tag):
            continue
        inp["link"] = None


def _output_slot(node: dict[str, Any], *, link_type: str, name: str | None = None) -> int:
    for index, out in enumerate(node.get("outputs") or []):
        if out.get("type") != link_type:
            continue
        if name is None or out.get("name") == name:
            return index
    return 0


def _add_link(
    workflow: dict[str, Any],
    *,
    child_id: int,
    child_slot: int,
    parent_id: int,
    parent_slot: int,
    link_type: str,
    parent_node: dict[str, Any],
) -> None:
    link_id = _alloc_link_id(workflow)
    workflow.setdefault("links", []).append(
        [link_id, child_id, child_slot, parent_id, parent_slot, link_type]
    )
    for index, inp in enumerate(parent_node.get("inputs") or []):
        if index == parent_slot and inp.get("link") is None:
            inp["link"] = link_id
            break
    for node in workflow["nodes"]:
        if node["id"] != child_id:
            continue
        outputs = node.get("outputs") or []
        if child_slot >= len(outputs):
            break
        links = outputs[child_slot].setdefault("links", [])
        if isinstance(links, list):
            links.append(link_id)
        break


def _add_sjsx_link(
    workflow: dict[str, Any],
    *,
    child_id: int,
    child_node: dict[str, Any],
    parent_id: int,
    parent_tag: str,
    parent_node: dict[str, Any],
) -> None:
    target_slot = _child_input_slot(parent_tag, parent_node)
    _add_link(
        workflow,
        child_id=child_id,
        child_slot=_output_slot(child_node, link_type="SJSX"),
        parent_id=parent_id,
        parent_slot=target_slot,
        link_type="SJSX",
        parent_node=parent_node,
    )


def _has_explicit_onchange_key(node: dict[str, Any]) -> bool:
    active = set(node.get("properties", {}).get("sjsxActiveParams") or [])
    if "onChange" not in active:
        return False
    widget_names = _widget_input_names(node)
    if "onChange" not in widget_names:
        return False
    index = widget_names.index("onChange")
    values = node.get("widgets_values") or []
    if index >= len(values):
        return False
    return bool(str(values[index] or "").strip())


def _wire_default_state_injections(workflow: dict[str, Any], _root_node: dict[str, Any]) -> None:
    for node in workflow.get("nodes") or []:
        if node.get("type") != f"{_SJSX_PREFIX}TextInput":
            continue
        if not _has_explicit_onchange_key(node):
            ensure_text_input_onchange(node)


def _default_position(
    positions: dict[tuple[Any, ...], list[float]],
    element: JsxElement,
    *,
    parent_pos: list[float] | None,
    child_index: int,
) -> list[float]:
    key = element.signature()
    if key in positions:
        return list(positions[key])
    if parent_pos:
        return [
            parent_pos[0] + _CHILD_OFFSET_X,
            parent_pos[1] + child_index * _CHILD_OFFSET_Y,
        ]
    return [400.0, 300.0]


def _remove_sjsx_nodes(workflow: dict[str, Any]) -> None:
    sjsx_ids = {
        node["id"]
        for node in workflow.get("nodes") or []
        if str(node.get("type", "")).startswith(_SJSX_PREFIX)
    }
    workflow["nodes"] = [
        node for node in workflow.get("nodes") or [] if node["id"] not in sjsx_ids
    ]
    workflow["links"] = [
        link
        for link in workflow.get("links") or []
        if not (
            isinstance(link, (list, tuple))
            and len(link) >= 4
            and (link[1] in sjsx_ids or link[3] in sjsx_ids)
        )
    ]


def _build_subtree(
    workflow: dict[str, Any],
    element: JsxElement,
    *,
    definition_name: str,
    parent: dict[str, Any] | None,
    parent_tag: str | None,
    templates: dict[str, dict[str, Any]],
    components: dict[str, dict[str, Any]],
    positions: dict[tuple[Any, ...], list[float]],
    child_index: int,
    is_root: bool,
) -> dict[str, Any]:
    node = _resolve_template(element.tag, templates, components)
    component = components.get(element.tag, {})
    template_onchange = ""
    template_content = ""
    if element.tag == "TextInput":
        template_onchange = _get_widget_value(node, "onChange")
    elif element.tag == "Text":
        template_content = str(read_widget_values_map(node).get("content", "") or "")
    _sync_ports_from_vocabulary(node, element.tag, component)
    _collapse_autogrow_child_inputs(workflow, node, element.tag)
    node_id = _alloc_id(workflow, "last_node_id")
    node["id"] = node_id
    node["pos"] = _default_position(
        positions,
        element,
        parent_pos=list(parent.get("pos") or _DEFAULT_SIZE) if parent else None,
        child_index=child_index,
    )
    _clear_sjsx_input_links(node, element.tag)
    _set_node_values(
        node,
        element,
        title=definition_name if is_root else "",
        components=components,
        template_onchange=template_onchange,
        template_content=template_content,
    )
    workflow.setdefault("nodes", []).append(node)

    if parent is not None and parent_tag is not None:
        _add_sjsx_link(
            workflow,
            child_id=node_id,
            child_node=node,
            parent_id=parent["id"],
            parent_tag=parent_tag,
            parent_node=parent,
        )

    for index, child in enumerate(element.children):
        _build_subtree(
            workflow,
            child,
            definition_name=definition_name,
            parent=node,
            parent_tag=element.tag,
            templates=templates,
            components=components,
            positions=positions,
            child_index=index,
            is_root=False,
        )

    return node


def _apply_meta(workflow: dict[str, Any], source: str) -> None:
    meta = extract_meta(source)
    extra = workflow.setdefault("extra", {})
    extra["document_type"] = "sjsx"
    sjsx_meta = extra.setdefault("sjsx", {})
    if meta.domain:
        sjsx_meta["domain"] = meta.domain
    if meta.layer:
        sjsx_meta["layer"] = meta.layer
    if meta.status:
        sjsx_meta["status"] = meta.status
    workflow["document_type"] = "sjsx"


def workflow_to_jsx_tree(workflow: dict[str, Any]) -> tuple[str, JsxElement]:
    nodes_by_id = {
        str(node["id"]): node
        for node in workflow.get("nodes") or []
        if _is_sjsx_node(node)
    }
    if not nodes_by_id:
        raise ValueError("Workflow has no SJSX nodes")

    parent_map, children_map = _build_hierarchy(workflow, nodes_by_id)
    roots = _find_roots(nodes_by_id, parent_map)
    root_id = roots[0]
    root_node = nodes_by_id[root_id]
    definition_name = _const_name(root_node)

    def to_element(node_id: str) -> JsxElement:
        node = nodes_by_id[node_id]
        attrs, content = _extract_node_data(node)
        children = [to_element(child_id) for child_id in children_map.get(node_id, [])]
        return JsxElement(tag=_node_tag(node), attrs=attrs, children=children, content=content)

    return definition_name, to_element(root_id)


def apply_sjsx_source_to_workflow(workflow: dict[str, Any], source: str) -> dict[str, Any]:
    definition_name, desired_root = tree_from_sjsx_source(source)
    updated = copy.deepcopy(workflow)
    templates = _index_templates(updated)
    if not templates:
        raise ValueError("Workflow has no SJSX nodes to use as templates")
    positions = _index_positions(updated)
    components = _component_by_tag()

    _remove_sjsx_nodes(updated)
    root_node = _build_subtree(
        updated,
        desired_root,
        definition_name=definition_name,
        parent=None,
        parent_tag=None,
        templates=templates,
        components=components,
        positions=positions,
        child_index=0,
        is_root=True,
    )
    _wire_default_state_injections(updated, root_node)
    _apply_meta(updated, source)
    return updated
