from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_SJSX = REPO_ROOT / "node" / "sjsx"
SYSTEM_VOCAB = NODE_SJSX / "system" / "system.json"


def enrich_component(component: dict[str, Any]) -> dict[str, Any]:
    return component


def components_by_tag() -> dict[str, dict[str, Any]]:
    vocab = load_all_vocabulary()
    return {
        component["tag"]: enrich_component(component)
        for component in vocab["components"]
    }


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_react_native_vocabulary() -> dict[str, Any]:
    loader_path = NODE_SJSX / "load.py"
    mod = _load_module_from_path("node_sjsx_load", loader_path)
    return mod.load_react_native_vocabulary()


def load_system_vocabulary() -> dict[str, Any]:
    data = json.loads(SYSTEM_VOCAB.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {
            "manifest": {"vocabulary": "system", "palette_root": "sjsx/system"},
            "components": data,
        }
    return data


def load_all_vocabulary() -> dict[str, Any]:
    rn = load_react_native_vocabulary()
    system = load_system_vocabulary()
    return {
        "react_native": rn,
        "system": system,
        "components": rn["components"] + system["components"],
        "palette_roots": ["sjsx/react-native", "sjsx/system"],
    }


def validate_layer_tags(layer: str | None, tags: list[str]) -> list[str]:
    if not layer:
        return []
    vocab = load_all_vocabulary()
    by_layer: dict[str, set[str]] = {
        "ui": {c["tag"] for c in vocab["react_native"]["components"]},
        "system": {c["tag"] for c in vocab["system"]["components"]},
        "state": {c["tag"] for c in vocab["system"]["components"] if c.get("kind") == "state"},
    }
    allowed = by_layer.get(layer, set())
    if not allowed:
        return []
    return [t for t in tags if t not in allowed and t not in {"Checkbox", "EmptyState", "TodoInput", "FilterBar", "SyncBadge", "TodoItem"}]
