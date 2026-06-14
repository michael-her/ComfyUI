from app.sjsx.workflow import is_sjsx_workflow, workflow_to_sjsx_source


def _sample_workflow() -> dict:
    return {
        "version": 0.4,
        "extra": {
            "document_type": "sjsx",
            "sjsx": {"domain": "HelloApp", "layer": "ui", "status": "design"},
        },
        "nodes": [
            {
                "id": 1,
                "type": "Sjsx_View",
                "title": "main",
                "inputs": [
                    {"name": "View", "type": "SJSX", "link": 1},
                    {
                        "name": "cx",
                        "type": "STRING",
                        "widget": {"name": "cx"},
                        "link": None,
                    },
                ],
                "widgets_values": ["entry-point"],
                "outputs": [{"name": "View", "type": "SJSX", "links": []}],
            },
            {
                "id": 2,
                "type": "Sjsx_Text",
                "title": "",
                "inputs": [
                    {
                        "name": "content",
                        "type": "STRING",
                        "widget": {"name": "content"},
                        "link": None,
                    }
                ],
                "widgets_values": ["Hello, World!"],
                "outputs": [{"name": "Text", "type": "SJSX", "links": [1]}],
                "properties": {"sjsxActiveParams": ["content"]},
            },
        ],
        "links": [[1, 2, 0, 1, 0, "SJSX"]],
    }


def test_is_sjsx_workflow_detects_sjsx_nodes():
    assert is_sjsx_workflow(_sample_workflow())


def test_workflow_to_sjsx_source_emits_nested_jsx():
    source = workflow_to_sjsx_source(_sample_workflow())
    assert "@sjsx" in source
    assert "domain: HelloApp" in source
    assert "const main = (" in source
    assert '<View cx="entry-point">' in source
    assert "<Text>Hello, World!</Text>" in source
    assert "numberOfLines" not in source
    assert "Not a buildable app entry" in source


def test_inactive_number_of_lines_default_is_not_emitted():
    workflow = _sample_workflow()
    text = next(node for node in workflow["nodes"] if node["type"] == "Sjsx_Text")
    text["widgets_values"] = ["", 0, False, "", "", "Hello, World!"]
    source = workflow_to_sjsx_source(workflow)
    assert "numberOfLines" not in source


def test_workflow_export_uses_widgets_values_when_stored_map_is_stale():
    workflow = _sample_workflow()
    text = next(node for node in workflow["nodes"] if node["type"] == "Sjsx_Text")
    text["widgets_values"] = ["Hello from canvas!"]
    text["properties"]["sjsxWidgetValues"] = {"content": ""}
    source = workflow_to_sjsx_source(workflow)
    assert "<Text>Hello from canvas!</Text>" in source


def test_text_content_preserves_state_placeholders():
    workflow = {
        "version": 0.4,
        "extra": {"document_type": "sjsx", "sjsx": {"domain": "HelloApp", "layer": "ui", "status": "design"}},
        "nodes": [
            {
                "id": 1,
                "type": "Sjsx_View",
                "title": "main",
                "inputs": [
                    {"name": "View", "type": "SJSX", "link": 1},
                    {"name": "View", "type": "SJSX", "link": 2},
                ],
                "outputs": [{"name": "View", "type": "SJSX", "links": []}],
            },
            {
                "id": 2,
                "type": "Sjsx_Text",
                "inputs": [
                    {"name": "Text", "type": "SJSX", "link": None},
                    {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
                ],
                "widgets_values": ["Hello, {target}!"],
                "outputs": [{"name": "Text", "type": "SJSX", "links": [1]}],
                "properties": {"sjsxActiveParams": ["content"]},
            },
            {
                "id": 3,
                "type": "Sjsx_TextInput",
                "inputs": [
                    {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}, "link": None},
                    {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
                ],
                "outputs": [
                    {"name": "TextInput", "type": "SJSX", "links": [2]},
                ],
                "properties": {"sjsxActiveParams": ["placeholder", "onChange"]},
                "widgets_values": ["World", "target"],
            },
        ],
        "links": [
            [1, 2, 0, 1, 0, "SJSX"],
            [2, 3, 0, 1, 0, "SJSX"],
        ],
    }
    source = workflow_to_sjsx_source(workflow)
    assert "<Text>Hello, {target}!</Text>" in source
    assert 'onChange="target"' in source
    assert 'placeholder="World"' in source
    assert "&#123;target&#125;" not in source


def test_view_export_uses_explicit_state_over_children():
    workflow = {
        "version": 0.4,
        "extra": {"document_type": "sjsx", "sjsx": {"domain": "HelloApp", "layer": "ui", "status": "design"}},
        "nodes": [
            {
                "id": 1,
                "type": "Sjsx_View",
                "title": "main",
                "inputs": [
                    {"name": "View", "type": "SJSX", "link": 1},
                    {"name": "View", "type": "SJSX", "link": 2},
                    {"name": "state", "type": "STRING", "widget": {"name": "state"}, "link": None},
                ],
                "widgets_values": ["", "", "custom/state"],
                "outputs": [{"name": "View", "type": "SJSX", "links": []}],
                "properties": {
                    "sjsxActiveParams": ["state"],
                    "sjsxWidgetValues": {"state": "custom/state"},
                },
            },
            {
                "id": 2,
                "type": "Sjsx_TextInput",
                "inputs": [
                    {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
                ],
                "outputs": [{"name": "TextInput", "type": "SJSX", "links": [2]}],
                "properties": {"sjsxActiveParams": ["onChange"]},
                "widgets_values": ["main/target"],
            },
            {
                "id": 3,
                "type": "Sjsx_Text",
                "inputs": [
                    {"name": "Text", "type": "SJSX", "link": None},
                    {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
                ],
                "widgets_values": ["Hi"],
                "outputs": [{"name": "Text", "type": "SJSX", "links": [1]}],
                "properties": {"sjsxActiveParams": ["content"]},
            },
        ],
        "links": [
            [1, 3, 0, 1, 0, "SJSX"],
            [2, 2, 0, 1, 0, "SJSX"],
        ],
    }
    source = workflow_to_sjsx_source(workflow)
    assert 'state="custom/state"' in source
    assert 'state="main/target"' not in source


def test_view_exports_derived_state_from_children():
    workflow = {
        "version": 0.4,
        "extra": {"document_type": "sjsx", "sjsx": {"domain": "HelloApp", "layer": "ui", "status": "design"}},
        "nodes": [
            {
                "id": 1,
                "type": "Sjsx_View",
                "title": "main",
                "inputs": [{"name": "View", "type": "SJSX", "link": 1}, {"name": "View", "type": "SJSX", "link": 2}],
                "outputs": [{"name": "View", "type": "SJSX", "links": []}],
                "properties": {"sjsxActiveParams": []},
            },
            {
                "id": 2,
                "type": "Sjsx_Text",
                "inputs": [
                    {"name": "Text", "type": "SJSX", "link": None},
                    {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
                ],
                "widgets_values": ["Hello, {main/target}"],
                "outputs": [{"name": "Text", "type": "SJSX", "links": [1]}],
                "properties": {"sjsxActiveParams": ["content"]},
            },
            {
                "id": 3,
                "type": "Sjsx_TextInput",
                "inputs": [
                    {"name": "placeholder", "type": "STRING", "widget": {"name": "placeholder"}, "link": None},
                    {"name": "onChange", "type": "STRING", "widget": {"name": "onChange"}, "link": None},
                ],
                "outputs": [{"name": "TextInput", "type": "SJSX", "links": [2]}],
                "properties": {"sjsxActiveParams": ["placeholder", "onChange"]},
                "widgets_values": ["World", "main/target"],
            },
        ],
        "links": [
            [1, 2, 0, 1, 0, "SJSX"],
            [2, 3, 0, 1, 0, "SJSX"],
        ],
    }
    source = workflow_to_sjsx_source(workflow)
    assert 'state="main/target"' in source
