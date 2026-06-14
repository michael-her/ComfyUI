import pytest

from app.sjsx.jsx_tree import parse_jsx_tree, tree_from_sjsx_source
from app.sjsx.workflow import workflow_to_sjsx_source
from app.sjsx.workflow_apply import apply_sjsx_source_to_workflow


def _hello_like_workflow() -> dict:
    view = {
        "id": 1,
        "type": "Sjsx_View",
        "title": "main",
        "pos": [900, 400],
        "inputs": [
            {"name": "View", "type": "SJSX", "link": 1},
            {"name": "cx", "type": "STRING", "widget": {"name": "cx"}, "link": None},
            {"name": "accessible", "type": "BOOLEAN", "widget": {"name": "accessible"}, "link": None},
            {"name": "accessibilityLabel", "type": "STRING", "widget": {"name": "accessibilityLabel"}, "link": None},
            {"name": "onLayout", "type": "STRING", "widget": {"name": "onLayout"}, "link": None},
            {"name": "onTouchStart", "type": "STRING", "widget": {"name": "onTouchStart"}, "link": None},
            {"name": "onTouchEnd", "type": "STRING", "widget": {"name": "onTouchEnd"}, "link": None},
        ],
        "widgets_values": ["entry-point", False, "", "", "", ""],
        "outputs": [{"name": "View", "type": "SJSX", "links": []}],
        "properties": {
            "Node name for S&R": "Sjsx_View",
            "sjsxActiveParams": ["cx"],
            "sjsxParamsVersion": 1,
        },
    }
    text = {
        "id": 2,
        "type": "Sjsx_Text",
        "title": "",
        "pos": [430, 460],
        "inputs": [
            {"name": "Text", "type": "SJSX", "link": None},
            {"name": "cx", "type": "STRING", "widget": {"name": "cx"}, "link": None},
            {"name": "numberOfLines", "type": "FLOAT", "widget": {"name": "numberOfLines"}, "link": None},
            {"name": "selectable", "type": "BOOLEAN", "widget": {"name": "selectable"}, "link": None},
            {"name": "onPress", "type": "STRING", "widget": {"name": "onPress"}, "link": None},
            {"name": "onLongPress", "type": "STRING", "widget": {"name": "onLongPress"}, "link": None},
            {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
        ],
        "widgets_values": ["", 0, False, "", "", "Hello, World!"],
        "outputs": [{"name": "Text", "type": "SJSX", "links": [1]}],
        "properties": {"sjsxActiveParams": ["content"], "sjsxParamsVersion": 1},
    }
    return {
        "version": 0.4,
        "extra": {
            "document_type": "sjsx",
            "sjsx": {"domain": "HelloApp", "layer": "ui", "status": "design"},
        },
        "nodes": [view, text],
        "links": [[1, 2, 0, 1, 0, "SJSX"]],
        "last_node_id": 5,
        "last_link_id": 1,
    }


def test_parse_jsx_tree_nested_children():
    root = parse_jsx_tree(
        """(
  <View cx="entry-point">
    <Text>Hello, World!</Text>
    <TextInput placeholder="Name" />
  </View>
)"""
    )
    assert root.tag == "View"
    assert root.attrs["cx"] == "entry-point"
    assert len(root.children) == 2
    assert root.children[0].tag == "Text"
    assert root.children[0].content == "Hello, World!"
    assert root.children[1].tag == "TextInput"
    assert root.children[1].attrs["placeholder"] == "Name"


def test_apply_adds_text_input_from_sjsx():
    workflow = _hello_like_workflow()
    source = workflow_to_sjsx_source(workflow)
    source = source.replace(
        "<Text>Hello, World!</Text>",
        "<Text>Hello, World!</Text>\n    <TextInput placeholder=\"Name\" />",
    )

    updated = apply_sjsx_source_to_workflow(workflow, source)
    tags = [node["type"] for node in updated["nodes"]]
    assert tags.count("Sjsx_View") == 1
    assert tags.count("Sjsx_Text") == 1
    assert tags.count("Sjsx_TextInput") == 1

    roundtrip = workflow_to_sjsx_source(updated)
    assert "<TextInput" in roundtrip
    assert 'placeholder="Name"' in roundtrip


def test_apply_removes_deleted_component():
    workflow = _hello_like_workflow()
    source = workflow_to_sjsx_source(workflow)
    source = source.replace("\n    <Text>Hello, World!</Text>", "")

    updated = apply_sjsx_source_to_workflow(workflow, source)
    tags = [node["type"] for node in updated["nodes"]]
    assert "Sjsx_Text" not in tags
    assert "Sjsx_View" in tags

    roundtrip = workflow_to_sjsx_source(updated)
    assert "<Text>" not in roundtrip


def test_apply_text_input_sets_onchange_for_state():
    workflow = _hello_like_workflow()
    source = """/**
 * @sjsx
 * domain: HelloApp
 * layer: ui
 * status: design
 */
const main = (
  <View cx="entry-point">
    <Text>Hello, World!</Text>
    <TextInput placeholder="Name" />
  </View>
)"""

    updated = apply_sjsx_source_to_workflow(workflow, source)
    text_input = next(n for n in updated["nodes"] if n["type"] == "Sjsx_TextInput")
    view = next(n for n in updated["nodes"] if n["type"] == "Sjsx_View")

    assert len(text_input["outputs"]) == 1
    assert text_input["outputs"][0]["type"] == "SJSX"
    assert "onChange" in text_input["properties"]["sjsxActiveParams"]

    string_links = [
        link
        for link in updated["links"]
        if isinstance(link, (list, tuple))
        and len(link) >= 6
        and link[1] == text_input["id"]
        and link[5] == "STRING"
    ]
    assert string_links == []
    text = next(n for n in updated["nodes"] if n["type"] == "Sjsx_Text")
    assert not any(inp.get("name") == "state" for inp in text["inputs"])
    assert not any(inp.get("name") == "state" for inp in view["inputs"])


def test_apply_preserves_onchange_key_from_template():
    workflow = _hello_like_workflow()
    workflow["nodes"].append(
        {
            "id": 3,
            "type": "Sjsx_TextInput",
            "title": "",
            "pos": [500, 500],
            "inputs": [
                {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}, "link": None},
                {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
            ],
            "widgets_values": ["Name", "target"],
            "outputs": [{"name": "TextInput", "type": "SJSX", "links": []}],
            "properties": {"sjsxActiveParams": ["placeholder", "onChange"]},
        }
    )
    workflow["links"].append([2, 3, 0, 1, 0, "SJSX"])
    source = """const main = (
  <View cx="entry-point">
    <Text>Hello, World!</Text>
    <TextInput placeholder="Name" />
  </View>
)"""

    updated = apply_sjsx_source_to_workflow(workflow, source)
    text_input = next(n for n in updated["nodes"] if n["type"] == "Sjsx_TextInput")

    assert len(text_input["outputs"]) == 1
    assert "onChange" in text_input["properties"]["sjsxActiveParams"]
    assert text_input["widgets_values"][1] == "target"


def test_apply_preserves_text_content_when_sjsx_has_empty_text():
    workflow = _hello_like_workflow()
    text = next(n for n in workflow["nodes"] if n["type"] == "Sjsx_Text")
    text["properties"]["sjsxActiveParams"] = ["content"]
    text["properties"]["sjsxWidgetValues"] = {"content": ""}
    text["widgets_values"] = ["", 0, False, "", "", "Hello, {target}!"]

    source = """const main = (
  <View cx="entry-point">
    <Text />
    <TextInput placeholder="Name" />
  </View>
)"""
    updated = apply_sjsx_source_to_workflow(workflow, source)
    text = next(n for n in updated["nodes"] if n["type"] == "Sjsx_Text")
    from app.sjsx.state_sync import read_widget_values_map

    assert "content" in text["properties"]["sjsxActiveParams"]
    assert read_widget_values_map(text)["content"] == "Hello, {target}!"


def test_apply_view_state_attr_roundtrip():
    workflow = _hello_like_workflow()
    source = """const main = (
  <View state="main/target">
    <Text>Hello, {main/target}</Text>
    <TextInput onChange="main/target" placeholder="World" />
  </View>
)"""
    updated = apply_sjsx_source_to_workflow(workflow, source)
    view = next(n for n in updated["nodes"] if n["type"] == "Sjsx_View")
    assert "state" in view["properties"]["sjsxActiveParams"]
    assert view["properties"]["sjsxWidgetValues"]["state"] == "main/target"

    roundtrip = workflow_to_sjsx_source(updated)
    assert 'state="main/target"' in roundtrip
    assert "Hello, {main/target}" in roundtrip
    assert 'onChange="main/target"' in roundtrip


def test_apply_adds_second_child_without_dropping_first():
    workflow = _hello_like_workflow()
    source = """const main = (
  <View cx="entry-point">
    <Text>Hello, World!</Text>
    <TextInput placeholder="Name" />
  </View>
)"""
    updated = apply_sjsx_source_to_workflow(workflow, source)
    view = next(n for n in updated["nodes"] if n["type"] == "Sjsx_View")
    text = next(n for n in updated["nodes"] if n["type"] == "Sjsx_Text")
    text_input = next(n for n in updated["nodes"] if n["type"] == "Sjsx_TextInput")

    sjsx_links = [
        link
        for link in updated["links"]
        if isinstance(link, (list, tuple))
        and len(link) >= 6
        and link[5] == "SJSX"
        and link[3] == view["id"]
    ]
    child_ids = {link[1] for link in sjsx_links}
    assert child_ids == {text["id"], text_input["id"]}
    assert len({link[4] for link in sjsx_links}) == 1

    roundtrip = workflow_to_sjsx_source(updated)
    assert "<Text>Hello, World!</Text>" in roundtrip
    assert "<TextInput" in roundtrip


def test_apply_collapses_legacy_autogrow_child_slots():
    workflow = _hello_like_workflow()
    workflow["nodes"][0]["inputs"] = [
        {"name": "View.View0", "type": "SJSX", "link": 1},
        {"name": "View.View1", "type": "SJSX", "link": None},
        *workflow["nodes"][0]["inputs"][2:],
    ]
    source = workflow_to_sjsx_source(workflow)

    updated = apply_sjsx_source_to_workflow(workflow, source)
    view = next(n for n in updated["nodes"] if n["type"] == "Sjsx_View")
    child_names = [
        inp["name"]
        for inp in view["inputs"]
        if inp.get("type") == "SJSX"
    ]
    assert child_names == ["View"]


def test_tree_from_sjsx_source_finds_main():
    workflow = _hello_like_workflow()
    source = workflow_to_sjsx_source(workflow)
    name, root = tree_from_sjsx_source(source)
    assert name == "main"
    assert root.tag == "View"
