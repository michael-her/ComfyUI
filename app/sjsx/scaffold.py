from __future__ import annotations

import re
from pathlib import Path

from app.sjsx.models import SjsxGraph
from app.sjsx.parser import extract_components, extract_meta, detect_layer


def _scaffold_system(meta, components: list[str], src: str, basename: str) -> str:
    lines = [
        f"// AUTO-SCAFFOLDED from {basename}",
        f"// domain: {meta.domain} | layer: system",
        "",
        'import { ThreadPool, DbJob } from "@sjsx/runtime";',
        "",
    ]
    if "Store" in src:
        lines.extend([
            "// ─── Store ───────────────────────────────────────────────",
            "// TODO: implement Redux store from .sjsx Store definition",
            f"export const {meta.domain}Store = createStore(rootReducer);",
            "",
        ])
    if "ThreadPool" in src:
        lines.append("// ─── Workers ─────────────────────────────────────────────")
        worker_names = [m.group(1) for m in re.finditer(r"const (\w+Worker)\s*=", src)]
        for name in worker_names:
            lines.extend([
                f"export function start{name}() {{",
                "  // TODO: implement from .sjsx definition",
                "  const pool = new ThreadPool({ threads: 4, cancelFlag: true });",
                "  // ...",
                "}",
                "",
            ])
    return "\n".join(lines)


def _scaffold_ui(meta, components: list[str], src: str, basename: str) -> str:
    skip = {"View", "Text", "FlatList", "TouchableOpacity", "Connect", "Store", "Checkbox"}
    sub_components = [c for c in components if c not in skip]
    lines = [
        f"// AUTO-SCAFFOLDED from {basename}",
        f"// domain: {meta.domain} | layer: ui",
        "",
        'import React from "react";',
        'import { View, Text, FlatList, TouchableOpacity } from "react-native";',
        'import { connect } from "react-redux";',
        f'import {{ {meta.domain}Store }} from "./{meta.domain.lower()}-system";',
        "",
    ]
    for name in sub_components:
        pad = max(0, 50 - len(name))
        lines.extend([
            f"// ─── {name} {'─' * pad}",
            f"function {name}(props) {{",
            "  // TODO: implement from .sjsx definition",
            "  return null;",
            "}",
            "",
        ])
    return "\n".join(lines)


def generate_scaffold(graph: SjsxGraph, source: str, basename: str, *, pending: list[str] | None = None) -> str:
    meta = graph.meta
    layer = meta.layer or detect_layer(source, meta)
    components = extract_components(source)
    pending = pending if pending is not None else graph.agreement.pending
    body = _scaffold_system(meta, components, source, basename) if layer == "system" else _scaffold_ui(meta, components, source, basename)
    if pending:
        todo_block = "\n".join(f"// TODO [ ] {item}" for item in pending)
        body = body.rstrip() + "\n\n" + todo_block + "\n"
    return body


def write_scaffold_file(design_path: Path, graph: SjsxGraph, source: str) -> Path:
    out_path = design_path.with_suffix(".scaffold.ts")
    content = generate_scaffold(graph, source, design_path.name)
    out_path.write_text(content, encoding="utf-8")
    return out_path
