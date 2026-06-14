from __future__ import annotations

import re

from app.sjsx.models import SjsxAgreement, SjsxGraph
from app.sjsx.parser import parse
from app.sjsx.emitter import emit

AGREED_LINE_RE = re.compile(r"^(\s*\[x\]\s*)(.+)$", re.MULTILINE)
PENDING_LINE_RE = re.compile(r"^(\s*\[ \]\s*)(.+)$", re.MULTILINE)


def agreement_status(graph: SjsxGraph) -> dict:
    a = graph.agreement
    return {
        "agreed": a.agreed,
        "pending": a.pending,
        "agreed_count": len(a.agreed),
        "pending_count": len(a.pending),
        "total": a.total,
        "percent": a.percent,
    }


def patch_agreement(source: str, *, agree: list[str] | None = None, reopen: list[str] | None = None) -> str:
    graph = parse(source)
    agreed = set(graph.agreement.agreed)
    pending = set(graph.agreement.pending)

    for item in agree or []:
        pending.discard(item)
        agreed.add(item)
    for item in reopen or []:
        agreed.discard(item)
        pending.add(item)

    graph.agreement = SjsxAgreement(agreed=sorted(agreed), pending=sorted(pending))
    header = graph.header
    if not header:
        return emit(graph)

    lines = header.splitlines()
    out: list[str] = []
    in_agreement = False
    agreement_written = False
    for line in lines:
        if re.search(r"Agreement items:|합의 항목:", line):
            in_agreement = True
            out.append(line)
            for item in graph.agreement.agreed:
                out.append(f" * [x] {item}")
            for item in graph.agreement.pending:
                out.append(f" * [ ] {item}")
            agreement_written = True
            continue
        if in_agreement and (line.strip().startswith("[x]") or line.strip().startswith("[ ]") or line.strip().startswith("* [")):
            continue
        if in_agreement and line.strip().startswith("*") and ("[x]" in line or "[ ]" in line):
            continue
        if in_agreement and agreement_written and line.strip() == "":
            in_agreement = False
        if in_agreement and (line.strip().startswith("[x]") or line.strip().startswith("[ ]")):
            continue
        out.append(line)

    if not agreement_written:
        out.append(" *")
        out.append(" * Agreement items:")
        for item in graph.agreement.agreed:
            out.append(f" * [x] {item}")
        for item in graph.agreement.pending:
            out.append(f" * [ ] {item}")

    graph.header = "\n".join(out)
    return emit(graph)


def patch_agreement_in_graph(graph: SjsxGraph, *, agree: list[str] | None = None, reopen: list[str] | None = None) -> SjsxGraph:
    text = patch_agreement(emit(graph), agree=agree, reopen=reopen)
    return parse(text)
