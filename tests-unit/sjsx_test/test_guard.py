from app.sjsx.guard import is_sjsx_queue_request, sjsx_queue_error


def test_sjsx_queue_blocked_by_extra_data():
    assert is_sjsx_queue_request({"extra_data": {"document_type": "sjsx"}, "prompt": {}})


def test_sjsx_queue_blocked_by_prompt_meta():
    assert is_sjsx_queue_request({"prompt": {"document_type": "sjsx", "1": {"class_type": "View"}}})


def test_comfyui_queue_allowed():
    assert not is_sjsx_queue_request({"prompt": {"1": {"class_type": "KSampler"}}})


def test_error_shape():
    err = sjsx_queue_error()
    assert err["type"] == "sjsx_queue_blocked"
