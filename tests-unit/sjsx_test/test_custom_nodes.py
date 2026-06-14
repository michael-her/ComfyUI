from custom_nodes.sjsx.nodes import build_sjsx_node_classes


def test_build_sjsx_node_classes_loads_without_defaults_state_inputs():
    classes = build_sjsx_node_classes()
    names = {cls.__name__ for cls in classes}
    assert "Sjsx_View" in names
    assert "Sjsx_Text" in names
    assert "Sjsx_TextInput" in names
