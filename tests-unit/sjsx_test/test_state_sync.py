import pytest

from app.sjsx.state_sync import (
    collect_state_keys,
    ensure_text_input_onchange,
    format_state_string,
)


def _text_input_node(*, onchange_key: str = "value", node_id: int = 2) -> dict:
    return {
        "id": node_id,
        "type": "Sjsx_TextInput",
        "outputs": [{"name": "TextInput", "type": "SJSX", "links": []}],
        "properties": {"sjsxActiveParams": ["placeholder", "onChange"]},
        "inputs": [
            {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}, "link": None},
            {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
        ],
        "widgets_values": ["", onchange_key],
    }


def _view_root(*, node_id: int = 1) -> dict:
    return {
        "id": node_id,
        "type": "Sjsx_View",
        "title": "main",
        "inputs": [
            {"name": "View", "type": "SJSX", "link": None},
            {"name": "cx", "type": "STRING", "widget": {"name": "cx"}, "link": None},
        ],
        "widgets_values": ["entry-point"],
        "properties": {"sjsxActiveParams": ["cx"]},
        "outputs": [{"name": "View", "type": "SJSX", "links": []}],
    }


def test_format_state_string_single_key():
    assert format_state_string(["target"]) == "target"


def test_format_state_string_multiple_keys():
    assert format_state_string(["email", "target"]) == "email, target"


def test_collect_state_keys_from_sibling_text_input():
    view = _view_root()
    text = {
        "id": 3,
        "type": "Sjsx_Text",
        "inputs": [
            {"name": "Text", "type": "SJSX", "link": None},
            {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
        ],
        "widgets_values": ["Hello, {label}!"],
        "properties": {"sjsxActiveParams": ["content"]},
        "outputs": [{"name": "Text", "type": "SJSX", "links": []}],
    }
    text_input = _text_input_node(onchange_key="label", node_id=4)
    workflow = {
        "nodes": [view, text, text_input],
        "links": [
            [1, 3, 0, 1, 0, "SJSX"],
            [2, 4, 0, 1, 0, "SJSX"],
        ],
    }

    assert collect_state_keys(workflow, text) == ["label"]


def test_read_widget_values_map_prefers_widgets_values_over_stale_stored():
    from app.sjsx.state_sync import read_widget_values_map, write_widget_values_map

    node = {
        "inputs": [
            {"name": "content", "type": "STRING", "widget": {"name": "content"}},
        ],
        "widgets_values": ["Hello, {target}!"],
        "properties": {"sjsxWidgetValues": {"content": ""}},
    }
    assert read_widget_values_map(node)["content"] == "Hello, {target}!"

    write_widget_values_map(node, read_widget_values_map(node))
    assert node["properties"]["sjsxWidgetValues"]["content"] == "Hello, {target}!"
    assert node["widgets_values"] == ["Hello, {target}!"]


def test_read_widget_values_map_keeps_stored_when_canvas_empty():
    from app.sjsx.state_sync import read_widget_values_map, write_widget_values_map

    node = {
        "inputs": [
            {"name": "content", "type": "STRING", "widget": {"name": "content"}},
        ],
        "widgets_values": [""],
        "properties": {"sjsxWidgetValues": {"content": "Hello, {target}!"}},
    }
    assert read_widget_values_map(node)["content"] == "Hello, {target}!"

    write_widget_values_map(node, read_widget_values_map(node))
    assert node["properties"]["sjsxWidgetValues"]["content"] == "Hello, {target}!"
    assert node["widgets_values"] == ["Hello, {target}!"]


def test_ensure_text_input_onchange_sets_default():
    node = {
        "id": 1,
        "type": "Sjsx_TextInput",
        "inputs": [
            {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
        ],
        "widgets_values": [""],
        "properties": {"sjsxActiveParams": []},
        "outputs": [{"name": "TextInput", "type": "SJSX", "links": []}],
    }
    ensure_text_input_onchange(node)
    assert "onChange" in node["properties"]["sjsxActiveParams"]
    assert node["widgets_values"][0] == "value"
    assert collect_state_keys({"nodes": [node], "links": []}, node) == []
