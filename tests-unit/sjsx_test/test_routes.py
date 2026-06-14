import pytest
from aiohttp import web

from app.sjsx.routes import ROUTES
from app.sjsx.models import SjsxGraph


@pytest.fixture
def app():
    application = web.Application()
    application.add_routes(ROUTES)
    return application


@pytest.mark.asyncio
async def test_vocabulary(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/sjsx/vocabulary")
    assert resp.status == 200
    data = await resp.json()
    assert "react_native" in data
    assert "system" in data
    assert any(c["tag"] == "View" for c in data["components"])


@pytest.mark.asyncio
async def test_design_crud(aiohttp_client, app, tmp_path, monkeypatch):
    monkeypatch.setattr("app.sjsx.storage.get_design_dir", lambda: tmp_path)
    client = await aiohttp_client(app)
    graph = SjsxGraph.empty_template(domain="TestApp", layer="ui")
    resp = await client.put("/sjsx/designs/test.sjsx", json={"graph": graph.to_dict()})
    assert resp.status == 200
    resp = await client.get("/sjsx/designs/test.sjsx")
    assert resp.status == 200
    text = await resp.text()
    assert "@sjsx" in text
    resp = await client.get("/sjsx/designs")
    names = [d["name"] for d in await resp.json()]
    assert "test.sjsx" in names


@pytest.mark.asyncio
async def test_parse_emit(aiohttp_client, app):
    client = await aiohttp_client(app)
    source = '/**\n * @sjsx\n * domain: X\n * layer: ui\n * status: design\n *\n * Agreement items:\n * [ ] one\n */\n'
    resp = await client.post("/sjsx/parse", json={"source": source})
    assert resp.status == 200
    graph = await resp.json()
    assert graph["document_type"] == "sjsx"
    resp = await client.post("/sjsx/emit", json={"graph": graph})
    assert resp.status == 200
    emitted = await resp.json()
    assert "@sjsx" in emitted["source"]


@pytest.mark.asyncio
async def test_agreement_patch(aiohttp_client, app, tmp_path, monkeypatch):
    monkeypatch.setattr("app.sjsx.storage.get_design_dir", lambda: tmp_path)
    client = await aiohttp_client(app)
    graph = SjsxGraph.empty_template(domain="AgreeApp", layer="ui")
    await client.put("/sjsx/designs/agree.sjsx", json={"graph": graph.to_dict()})
    resp = await client.patch("/sjsx/designs/agree.sjsx/agreement", json={"agree": ["Initial layout"]})
    assert resp.status == 200
    body = await resp.json()
    assert body["percent"] == 100
    assert "Initial layout" in body["agreed"]
