from __future__ import annotations

from typing import Any


def is_sjsx_queue_request(json_data: dict[str, Any]) -> bool:
    extra = json_data.get("extra_data") or {}
    if extra.get("document_type") == "sjsx":
        return True
    prompt = json_data.get("prompt")
    if isinstance(prompt, dict) and prompt.get("document_type") == "sjsx":
        return True
    return False


def sjsx_queue_error() -> dict[str, Any]:
    return {
        "type": "sjsx_queue_blocked",
        "message": "Semantic JSX designs cannot be queued for ComfyUI execution.",
        "details": "Use Emit or Scaffold for .sjsx documents. Set document_type to comfyui for diffusion workflows.",
        "extra_info": {},
    }
