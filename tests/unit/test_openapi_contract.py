"""docs/openapi.yaml must describe the routes and the suggestion shape the app really serves."""

from pathlib import Path

import yaml

from copilot.adapters.inbound.http.app import AppDeps, create_app
from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM

DOC = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml").read_text("utf-8")
)


def _generated() -> dict:
    app = create_app(AppDeps(connect=lambda: None, llm=UnconfiguredLLM()))  # type: ignore[arg-type,return-value]
    return app.openapi()


def _operations(spec: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, item in spec["paths"].items() for method in item}


def test_documented_routes_match_the_app():
    assert _operations(DOC) == _operations(_generated())


# documented schema name -> name FastAPI generates for the served model
SCHEMAS = {
    "Suggestion": "SuggestionOut",
    "Step": "StepOut",
    "Citation": "CitationOut",
    "DecisionCreate": "DecisionCreate",
    "EventCreate": "EventCreate",
}


def test_schema_fields_match():
    generated = _generated()["components"]["schemas"]
    for documented_name, served_name in SCHEMAS.items():
        documented = set(DOC["components"]["schemas"][documented_name]["properties"])
        assert documented == set(generated[served_name]["properties"]), documented_name


def test_documented_status_enum_matches():
    documented = DOC["components"]["schemas"]["Suggestion"]["properties"]["status"]["enum"]
    served = _generated()["components"]["schemas"]["SuggestionOut"]["properties"]["status"]["enum"]
    assert set(documented) == set(served)


def test_screen_is_served_and_is_not_part_of_the_api_contract():
    from fastapi.testclient import TestClient

    app = create_app(AppDeps(connect=lambda: None, llm=UnconfiguredLLM()))  # type: ignore[arg-type,return-value]
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200 and "Grid Contingency Copilot" in page.text
    assert "innerHTML" not in page.text  # untrusted text must go through textContent
    assert "/" not in client.get("/openapi.json").json()["paths"]
