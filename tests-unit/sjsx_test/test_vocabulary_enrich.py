from app.sjsx.vocabulary import components_by_tag, enrich_component


def test_enrich_component_is_passthrough():
    component = {"tag": "Text", "can_have_children": True, "attrs": {}}
    assert enrich_component(component) is component
    assert "state_inputs" not in enrich_component(component)


def test_components_by_tag_has_no_state_inputs():
    by_tag = components_by_tag()
    for tag in ("Text", "View", "TextInput"):
        assert "state_inputs" not in by_tag[tag]
