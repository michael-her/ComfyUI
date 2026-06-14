from __future__ import annotations

import os
import re
from pathlib import Path

import folder_paths

from app.sjsx.models import SjsxGraph
from app.sjsx.parser import parse
from app.sjsx.emitter import emit
from app.sjsx.agreement import agreement_status


def get_design_dir() -> Path:
    base = os.path.dirname(os.path.realpath(folder_paths.__file__))
    return Path(base) / "design"


def _safe_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.sjsx", name):
        raise ValueError("Invalid design filename")
    return name


def list_designs() -> list[dict]:
    design_dir = get_design_dir()
    design_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(design_dir.glob("*.sjsx")):
        source = path.read_text(encoding="utf-8")
        graph = parse(source)
        status = agreement_status(graph)
        results.append({
            "name": path.name,
            "domain": graph.meta.domain,
            "layer": graph.meta.layer,
            "status": graph.meta.status,
            **status,
        })
    return results


def read_design(name: str, *, as_graph: bool = False) -> str | dict:
    path = get_design_dir() / _safe_name(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    source = path.read_text(encoding="utf-8")
    if as_graph:
        return parse(source).to_dict()
    return source


def write_design(name: str, *, source: str | None = None, graph: dict | SjsxGraph | None = None) -> None:
    path = get_design_dir() / _safe_name(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if source is not None:
        path.write_text(source, encoding="utf-8")
        return
    if graph is None:
        raise ValueError("source or graph required")
    if isinstance(graph, dict):
        graph = SjsxGraph.from_dict(graph)
    path.write_text(emit(graph), encoding="utf-8")


def design_path(name: str) -> Path:
    return get_design_dir() / _safe_name(name)
