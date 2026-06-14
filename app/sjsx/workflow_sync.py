from __future__ import annotations

import os
from typing import Any


def sjsx_companion_path(json_path: str) -> str:
    if json_path.lower().endswith(".json"):
        return json_path[:-5] + ".sjsx"
    return json_path + ".sjsx"


def write_sjsx_companion_file(json_abs_path: str, workflow: dict[str, Any]) -> str | None:
    from app.sjsx.workflow import is_sjsx_workflow, workflow_to_sjsx_source
    from app.sjsx.workflow_normalize import normalize_sjsx_workflow

    if not is_sjsx_workflow(workflow):
        return None

    normalize_sjsx_workflow(workflow)

    sjsx_path = sjsx_companion_path(json_abs_path)
    parent = os.path.dirname(sjsx_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(sjsx_path, "w", encoding="utf-8") as handle:
        handle.write(workflow_to_sjsx_source(workflow))
    return sjsx_path
