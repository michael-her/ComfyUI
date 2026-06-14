from __future__ import annotations

from app.sjsx.models import SjsxGraph


def emit(graph: SjsxGraph) -> str:
    parts: list[str] = []
    if graph.header:
        parts.append(graph.header.strip())
        parts.append("")
    for section in graph.sections:
        if section.comment:
            parts.append(section.comment)
            parts.append("")
        for definition in section.definitions:
            parts.append(f"const {definition.name} = {definition.body}")
            parts.append("")
    if not parts and graph.header:
        return graph.header.strip() + "\n"
    return "\n".join(parts).rstrip() + "\n"
