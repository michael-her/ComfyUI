"""Load sjsx vocabulary packs from node/sjsx/<pack>/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SJSX_ROOT = Path(__file__).resolve().parent
REACT_NATIVE_ROOT = SJSX_ROOT / "react-native"


def load_react_native_manifest() -> dict[str, Any]:
    return json.loads((REACT_NATIVE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def load_react_native_category(category_id: str) -> list[dict[str, Any]]:
    manifest = load_react_native_manifest()
    for cat in manifest["categories"]:
        if cat["id"] == category_id:
            return json.loads((REACT_NATIVE_ROOT / cat["file"]).read_text(encoding="utf-8"))
    raise KeyError(f"Unknown react-native category: {category_id}")


def load_react_native_components() -> list[dict[str, Any]]:
    manifest = load_react_native_manifest()
    components: list[dict[str, Any]] = []
    for cat in manifest["categories"]:
        components.extend(
            json.loads((REACT_NATIVE_ROOT / cat["file"]).read_text(encoding="utf-8"))
        )
    return components


def load_react_native_vocabulary() -> dict[str, Any]:
    manifest = load_react_native_manifest()
    by_category: dict[str, list[dict[str, Any]]] = {}
    for cat in manifest["categories"]:
        by_category[cat["id"]] = json.loads(
            (REACT_NATIVE_ROOT / cat["file"]).read_text(encoding="utf-8")
        )
    return {
        "manifest": manifest,
        "by_category": by_category,
        "components": load_react_native_components(),
    }
