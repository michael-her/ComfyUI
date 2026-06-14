import json
from pathlib import Path

from app.sjsx.workflow_normalize import normalize_sjsx_workflow


def _broken_hello_workflow() -> dict:
    return {
        "version": 0.4,
        "last_link_id": 19,
        "extra": {"document_type": "sjsx", "sjsx": {"domain": "NewApp", "layer": "ui", "status": "design"}},
        "nodes": [
            {
                "id": 6,
                "type": "Sjsx_View",
                "title": "main",
                "inputs": [
                    {"name": "View", "type": "SJSX", "link": 12},
                    {"name": "state", "type": "STRING", "link": None},
                    {"name": "cx", "type": "STRING", "widget": {"name": "cx"}, "link": None},
                ],
                "widgets_values": ["", ""],
                "outputs": [{"name": "View", "type": "SJSX", "links": None}],
                "properties": {"sjsxActiveParams": ["state"]},
            },
            {
                "id": 7,
                "type": "Sjsx_Text",
                "inputs": [
                    {"name": "Text", "type": "SJSX", "link": None},
                    {"name": "state", "type": "STRING", "link": 6},
                    {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
                ],
                "widgets_values": ["", "Hello, {target}!"],
                "outputs": [{"name": "Text", "type": "SJSX", "links": [1, 11]}],
                "properties": {"sjsxActiveParams": ["content", "state"]},
            },
            {
                "id": 8,
                "type": "Sjsx_TextInput",
                "inputs": [
                    {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}, "link": None},
                    {
                        "label": "onChangeText",
                        "name": "onChange",
                        "type": "STRING",
                        "widget": {"name": "onChange"},
                        "link": None,
                    },
                ],
                "widgets_values": ["World", "target"],
                "outputs": [
                    {"name": "TextInput", "type": "SJSX", "links": [12]},
                    {"name": "target", "type": "STRING", "links": [6]},
                ],
                "properties": {"sjsxActiveParams": ["placeholder", "onChange"]},
            },
        ],
        "links": [
            [11, 7, 0, 6, 0, "SJSX"],
            [12, 8, 0, 6, 0, "SJSX"],
            [6, 8, 1, 7, 1, "STRING"],
        ],
    }


def test_normalize_removes_stale_links_and_state_inputs():
    workflow = _broken_hello_workflow()
    normalize_sjsx_workflow(workflow)

    link_ids = {link[0] for link in workflow["links"]}
    assert link_ids == {11, 12}

    text = next(node for node in workflow["nodes"] if node["id"] == 7)
    assert not any(inp.get("name") == "state" for inp in text["inputs"])
    assert text["outputs"][0]["links"] == [11]

    view = next(node for node in workflow["nodes"] if node["id"] == 6)
    assert not any(
        inp.get("name") == "state" and not inp.get("widget")
        for inp in view["inputs"]
    )
    assert view["inputs"][0]["link"] in (11, 12)
    assert "state" in view["properties"]["sjsxActiveParams"]
    assert view["properties"]["sjsxWidgetValues"]["state"] == "target"

    text_input = next(node for node in workflow["nodes"] if node["id"] == 8)
    assert len(text_input["outputs"]) == 1
    onchange_inp = next(inp for inp in text_input["inputs"] if inp.get("name") == "onChange")
    assert onchange_inp["label"] == "onChange"
    assert text_input["properties"]["sjsxWidgetValues"]["onChange"] == "target"


def test_normalize_inserts_state_widget_without_shifting_values():
    workflow = _broken_hello_workflow()
    text_input = next(node for node in workflow["nodes"] if node["id"] == 8)
    text_input["inputs"].insert(
        0,
        {"name": "state", "type": "STRING", "link": None},
    )
    normalize_sjsx_workflow(workflow)
    assert "state" not in text_input["inputs"]
    assert text_input["properties"]["sjsxWidgetValues"]["onChange"] == "target"
    assert text_input["properties"]["sjsxWidgetValues"]["placeholder"] == "World"


def test_normalize_view_node_derives_state_from_children():
    workflow = _broken_hello_workflow()
    view = next(node for node in workflow["nodes"] if node["id"] == 6)
    view["properties"]["sjsxActiveParams"] = []
    view["properties"]["sjsxWidgetValues"] = {}

    normalize_sjsx_workflow(workflow)

    assert "state" in view["properties"]["sjsxActiveParams"]
    assert view["properties"]["sjsxWidgetValues"]["state"] == "target"


def test_normalize_text_node_keeps_content_value():
    workflow = _broken_hello_workflow()
    text = next(node for node in workflow["nodes"] if node["id"] == 7)
    text["properties"]["sjsxActiveParams"] = ["content"]
    text["properties"]["sjsxWidgetValues"] = {"content": "Hello, {target}!"}
    text["widgets_values"] = [""]

    normalize_sjsx_workflow(workflow)

    assert text["properties"]["sjsxActiveParams"] == ["content"]
    assert text["properties"]["sjsxWidgetValues"]["content"] == "Hello, {target}!"
    assert text["widgets_values"][-1] == "Hello, {target}!"


def test_normalize_text_input_strips_cx_and_keyboard_type_defaults():
    workflow = _broken_hello_workflow()
    text_input = next(node for node in workflow["nodes"] if node["id"] == 8)
    text_input["properties"]["sjsxActiveParams"] = [
        "cx",
        "keyboardType",
        "placeholder",
        "onChange",
    ]
    text_input["properties"]["sjsxWidgetValues"] = {
        "cx": "",
        "keyboardType": "default",
        "placeholder": "World",
        "onChange": "target",
    }

    normalize_sjsx_workflow(workflow)

    active = text_input["properties"]["sjsxActiveParams"]
    assert "cx" not in active
    assert "keyboardType" not in active
    assert active == ["placeholder", "onChange"]
    assert not any(inp.get("name") == "cx" for inp in text_input["inputs"])
    assert not any(inp.get("name") == "keyboardType" for inp in text_input["inputs"])
    assert text_input["properties"]["sjsxWidgetValues"] == {
        "placeholder": "World",
        "onChange": "target",
    }


def test_read_write_widget_values_map_roundtrip():
    from app.sjsx.state_sync import read_widget_values_map, write_widget_values_map

    node = {
        "inputs": [
            {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}},
            {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}},
        ],
        "widgets_values": ["World", "target"],
        "properties": {},
    }
    write_widget_values_map(node, read_widget_values_map(node))
    assert node["properties"]["sjsxWidgetValues"] == {
        "placeholder": "World",
        "onChange": "target",
    }
    assert node["widgets_values"] == ["World", "target"]


def test_normalize_current_hello_file():
    path = Path("user/default/workflows/hello.json")
    if not path.exists():
        return
    workflow = json.loads(path.read_text(encoding="utf-8"))
    normalize_sjsx_workflow(workflow)

    link_ids = {link[0] for link in workflow["links"]}
    for node in workflow["nodes"]:
        assert not any(
            inp.get("name") == "state" and not inp.get("widget")
            for inp in node.get("inputs") or []
        )
        for inp in node.get("inputs") or []:
            if inp.get("link") is not None:
                assert inp["link"] in link_ids
        for out in node.get("outputs") or []:
            for link_id in out.get("links") or []:
                assert link_id in link_ids
