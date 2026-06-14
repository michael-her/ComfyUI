import json
import os

import pytest
from aiohttp import web

from app.sjsx.routes import ROUTES, register_sjsx_routes
from app.sjsx.workflow_sync import sjsx_companion_path, write_sjsx_companion_file
from app.user_manager import UserManager


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


def test_sjsx_companion_path_replaces_json_extension():
    assert sjsx_companion_path("workflows/hello.json") == "workflows/hello.sjsx"


def test_write_sjsx_companion_file(tmp_path):
    json_path = tmp_path / "hello.json"
    json_path.write_text("{}", encoding="utf-8")
    workflow = _sample_workflow()

    sjsx_path = write_sjsx_companion_file(str(json_path), workflow)

    assert sjsx_path == str(tmp_path / "hello.sjsx")
    text = (tmp_path / "hello.sjsx").read_text(encoding="utf-8")
    assert "const main = (" in text
    assert "<Text>Hello, World!</Text>" in text


@pytest.fixture
def sync_app(tmp_path, monkeypatch):
    monkeypatch.setattr("folder_paths.get_user_directory", lambda: str(tmp_path))
    user_dir = tmp_path / "default"
    workflows = user_dir / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "hello.json").write_text("{}", encoding="utf-8")

    application = web.Application()
    register_sjsx_routes(application, UserManager())
    return application, workflows


@pytest.mark.asyncio
async def test_workflow_sync_writes_companion(aiohttp_client, sync_app):
    app, workflows = sync_app
    client = await aiohttp_client(app)
    workflow = _sample_workflow()
    workflow["nodes"][1]["widgets_values"] = ["Updated text"]

    resp = await client.post(
        "/sjsx/workflow/sync",
        json={"workflow": workflow, "json_path": "workflows/hello.json"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["ok"] is True
    assert body["sjsx_path"] == "workflows/hello.sjsx"

    sjsx_text = (workflows / "hello.sjsx").read_text(encoding="utf-8")
    assert "Updated text" in sjsx_text


@pytest.mark.asyncio
async def test_workflow_sync_requires_existing_json(aiohttp_client, sync_app):
    app, _workflows = sync_app
    client = await aiohttp_client(app)

    resp = await client.post(
        "/sjsx/workflow/sync",
        json={"workflow": _sample_workflow(), "json_path": "workflows/missing.json"},
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_workflow_apply_route(aiohttp_client, sync_app):
    from app.sjsx.workflow import workflow_to_sjsx_source
    from app.sjsx.workflow_apply import apply_sjsx_source_to_workflow

    app, _workflows = sync_app
    client = await aiohttp_client(app)
    workflow = _sample_workflow()
    workflow["nodes"][0]["inputs"] = [
        {"name": "View", "type": "SJSX", "link": 1},
        {"name": "cx", "type": "STRING", "widget": {"name": "cx"}, "link": None},
        {"name": "accessible", "type": "BOOLEAN", "widget": {"name": "accessible"}, "link": None},
        {"name": "accessibilityLabel", "type": "STRING", "widget": {"name": "accessibilityLabel"}, "link": None},
        {"name": "onLayout", "type": "STRING", "widget": {"name": "onLayout"}, "link": None},
        {"name": "onTouchStart", "type": "STRING", "widget": {"name": "onTouchStart"}, "link": None},
        {"name": "onTouchEnd", "type": "STRING", "widget": {"name": "onTouchEnd"}, "link": None},
    ]
    workflow["nodes"][0]["widgets_values"] = ["entry-point", False, "", "", "", ""]
    workflow["nodes"][0]["properties"] = {"sjsxActiveParams": ["cx"], "sjsxParamsVersion": 1}
    workflow["nodes"][1]["inputs"] = [
        {"name": "Text", "type": "SJSX", "link": None},
        {"name": "content", "type": "STRING", "widget": {"name": "content"}, "link": None},
    ]
    workflow["last_node_id"] = 5
    workflow["last_link_id"] = 1

    source = workflow_to_sjsx_source(workflow)
    source = source.replace(
        "<Text>Hello, World!</Text>",
        "<Text>Hello, World!</Text>\n    <TextInput placeholder=\"Name\" />",
    )

    resp = await client.post(
        "/sjsx/workflow/apply",
        json={"workflow": workflow, "source": source},
    )
    assert resp.status == 200
    body = await resp.json()
    tags = [node["type"] for node in body["workflow"]["nodes"]]
    assert "Sjsx_TextInput" in tags
    assert "<TextInput" in workflow_to_sjsx_source(body["workflow"])
