from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from aiohttp import web

from app.sjsx import parse, emit
from app.sjsx.agreement import agreement_status, patch_agreement
from app.sjsx.models import SjsxGraph
from app.sjsx.scaffold import generate_scaffold, write_scaffold_file
from app.sjsx.storage import (
    design_path,
    list_designs,
    read_design,
    write_design,
)
from app.sjsx.vocabulary import load_all_vocabulary, validate_layer_tags
from app.sjsx.workflow_sync import sjsx_companion_path, write_sjsx_companion_file

if TYPE_CHECKING:
    from app.user_manager import UserManager

ROUTES = web.RouteTableDef()
logger = logging.getLogger(__name__)
_user_manager: "UserManager | None" = None


def _json_error(message: str, status: int = 400, **extra) -> web.Response:
    return web.json_response({"error": message, **extra}, status=status)


@ROUTES.get("/sjsx/designs")
async def get_designs(_request: web.Request) -> web.Response:
    return web.json_response(list_designs())


@ROUTES.get("/sjsx/designs/{name}")
async def get_design(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    as_graph = request.query.get("format") == "graph"
    try:
        data = read_design(name, as_graph=as_graph)
        if as_graph:
            return web.json_response(data)
        return web.Response(text=data, content_type="text/plain", charset="utf-8")
    except FileNotFoundError:
        return _json_error(f"Design not found: {name}", 404)
    except ValueError as exc:
        return _json_error(str(exc), 400)


@ROUTES.put("/sjsx/designs/{name}")
async def put_design(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    content_type = request.headers.get("Content-Type", "")
    try:
        if "application/json" in content_type:
            payload = await request.json()
            if "source" in payload:
                write_design(name, source=payload["source"])
            elif "graph" in payload:
                write_design(name, graph=payload["graph"])
            else:
                return _json_error("JSON body must include 'source' or 'graph'")
        else:
            source = await request.text()
            write_design(name, source=source)
        return web.json_response({"ok": True, "name": name})
    except ValueError as exc:
        return _json_error(str(exc), 400)


@ROUTES.post("/sjsx/parse")
async def post_parse(request: web.Request) -> web.Response:
    payload = await request.json()
    source = payload.get("source")
    if not source:
        return _json_error("Missing 'source'")
    graph = parse(source)
    warnings = validate_layer_tags(graph.meta.layer, graph.components)
    data = graph.to_dict()
    if warnings:
        data["layer_warnings"] = warnings
    return web.json_response(data)


@ROUTES.post("/sjsx/emit")
async def post_emit(request: web.Request) -> web.Response:
    payload = await request.json()
    graph_data = payload.get("graph")
    if graph_data is None:
        return _json_error("Missing 'graph'")
    graph = SjsxGraph.from_dict(graph_data)
    return web.json_response({"source": emit(graph)})


@ROUTES.patch("/sjsx/designs/{name}/agreement")
async def patch_design_agreement(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    payload = await request.json()
    try:
        source = read_design(name, as_graph=False)
        if not isinstance(source, str):
            return _json_error("Unexpected design format", 500)
        updated = patch_agreement(
            source,
            agree=payload.get("agree") or [],
            reopen=payload.get("reopen") or [],
        )
        write_design(name, source=updated)
        graph = parse(updated)
        return web.json_response(agreement_status(graph))
    except FileNotFoundError:
        return _json_error(f"Design not found: {name}", 404)


@ROUTES.post("/sjsx/scaffold/{name}")
async def post_scaffold(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    try:
        source = read_design(name, as_graph=False)
        if not isinstance(source, str):
            return _json_error("Unexpected design format", 500)
        graph = parse(source)
        out_path = write_scaffold_file(design_path(name), graph, source)
        return web.json_response({
            "ok": True,
            "scaffold_path": str(out_path),
            "pending": graph.agreement.pending,
        })
    except FileNotFoundError:
        return _json_error(f"Design not found: {name}", 404)


@ROUTES.post("/sjsx/workflow/emit")
async def post_workflow_emit(request: web.Request) -> web.Response:
    from app.sjsx.workflow import workflow_to_sjsx_source

    workflow = await request.json()
    if not isinstance(workflow, dict):
        return _json_error("Body must be a workflow object")
    return web.json_response({"source": workflow_to_sjsx_source(workflow)})


@ROUTES.post("/sjsx/workflow/apply")
async def post_workflow_apply(request: web.Request) -> web.Response:
    from app.sjsx.workflow_apply import apply_sjsx_source_to_workflow

    payload = await request.json()
    workflow = payload.get("workflow")
    source = payload.get("source")
    json_path = payload.get("json_path")

    if not isinstance(workflow, dict):
        return _json_error("workflow must be an object")

    if not source:
        if not json_path or not isinstance(json_path, str):
            return _json_error("source or json_path is required")
        if _user_manager is None:
            return _json_error("User manager unavailable", 500)
        try:
            sjsx_abs_path = _user_manager.get_request_user_filepath(
                request, sjsx_companion_path(json_path), create_dir=False
            )
        except KeyError:
            return web.Response(status=403, text="Invalid user specified in request")
        if not sjsx_abs_path or not os.path.exists(sjsx_abs_path):
            return _json_error(f"Companion .sjsx not found for {json_path}", 404)
        source = open(sjsx_abs_path, encoding="utf-8").read()

    if not isinstance(source, str):
        return _json_error("source must be a string")

    try:
        updated = apply_sjsx_source_to_workflow(workflow, source)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    return web.json_response({"ok": True, "workflow": updated})


@ROUTES.post("/sjsx/workflow/sync")
async def post_workflow_sync(request: web.Request) -> web.Response:
    if _user_manager is None:
        return _json_error("User manager unavailable", 500)

    payload = await request.json()
    workflow = payload.get("workflow")
    json_path = payload.get("json_path")
    if not isinstance(workflow, dict):
        return _json_error("workflow must be an object")
    if not json_path or not isinstance(json_path, str):
        return _json_error("json_path is required")
    if not json_path.endswith(".json"):
        return _json_error("json_path must end with .json")

    try:
        json_abs_path = _user_manager.get_request_user_filepath(
            request, json_path, create_dir=False
        )
    except KeyError:
        return web.Response(status=403, text="Invalid user specified in request")

    if not json_abs_path:
        return web.Response(status=400, text="Invalid path requested")

    sjsx_abs_path = sjsx_companion_path(json_abs_path)
    if not os.path.exists(json_abs_path) and not os.path.exists(sjsx_abs_path):
        return _json_error(f"Workflow file not found: {json_path}", 404)

    written_path = write_sjsx_companion_file(json_abs_path, workflow)
    if written_path is None:
        return web.json_response({"ok": True, "skipped": True})

    user_path = _user_manager.get_request_user_filepath(request, None)
    sjsx_rel_path = os.path.relpath(written_path, user_path).replace(os.sep, "/")
    return web.json_response({"ok": True, "sjsx_path": sjsx_rel_path})


@ROUTES.get("/sjsx/vocabulary")
async def get_vocabulary(_request: web.Request) -> web.Response:
    return web.json_response(load_all_vocabulary())


@ROUTES.get("/sjsx/status")
async def get_status(_request: web.Request) -> web.Response:
    designs = list_designs()
    return web.json_response({"designs": designs})


def register_sjsx_routes(app: web.Application, user_manager: "UserManager | None" = None) -> None:
    global _user_manager
    _user_manager = user_manager
    app.add_routes(ROUTES)
    api_routes = web.RouteTableDef()
    for route in ROUTES:
        if isinstance(route, web.RouteDef):
            api_routes.route(route.method, "/api" + route.path)(route.handler, **route.kwargs)
    app.add_routes(api_routes)
    logger.info("Registered sjsx routes under /sjsx and /api/sjsx")
