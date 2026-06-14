import pytest
from pathlib import Path

from app.sjsx.parser import parse, extract_agreement, detect_layer
from app.sjsx.emitter import emit

DESIGN = Path(__file__).resolve().parents[2] / "design"


@pytest.mark.parametrize("filename", ["todo-ui.sjsx", "todo-system.sjsx"])
def test_roundtrip_definition_count(filename):
    source = (DESIGN / filename).read_text(encoding="utf-8")
    graph = parse(source)
    roundtrip = parse(emit(graph))
    assert len(graph.sections) == len(roundtrip.sections)
    names_a = [d.name for s in graph.sections for d in s.definitions]
    names_b = [d.name for s in roundtrip.sections for d in s.definitions]
    assert names_a == names_b


def test_todo_ui_agreement():
    source = (DESIGN / "todo-ui.sjsx").read_text(encoding="utf-8")
    agreement = extract_agreement(source)
    assert len(agreement.agreed) == 2
    assert len(agreement.pending) == 2
    assert agreement.percent == 50


def test_todo_ui_layer():
    source = (DESIGN / "todo-ui.sjsx").read_text(encoding="utf-8")
    graph = parse(source)
    assert graph.meta.layer == "ui"
    assert "View" in graph.components
    assert "FlatList" in graph.components


def test_todo_system_layer():
    source = (DESIGN / "todo-system.sjsx").read_text(encoding="utf-8")
    graph = parse(source)
    assert graph.meta.layer == "system"
    assert detect_layer(source) == "system"
    assert "ThreadPool" in graph.components
    assert "DbJob" in graph.components


def test_emit_preserves_header():
    source = (DESIGN / "todo-ui.sjsx").read_text(encoding="utf-8")
    graph = parse(source)
    out = emit(graph)
    assert "@sjsx" in out
    assert "domain: TodoApp" in out
