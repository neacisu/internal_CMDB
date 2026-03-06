import json
import runpy

import pytest


def test_module_entrypoint_prints_health_payload(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_module("proiecteit", run_name="__main__")
    captured = capsys.readouterr()

    assert json.loads(captured.out) == {"status": "ok"}
