import pytest

from copilot.adapters.outbound.fakes.llm import EchoLLM
from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM
from copilot.adapters.outbound.postgres.audit import PostgresAudit

pytestmark = pytest.mark.integration

LINE_TRIP = {
    "type": "line_trip_by_protection",
    "element": "LT-FICT-230-04",
    "occurred_at": "2026-03-14T02:41:00-03:00",
    "attributes": {"protection": "distance", "zone": 1, "reclosing": "failed"},
    "reported_by": "tester",
}
UNKNOWN = {
    "type": "substation_fire",
    "element": "SE-FICT-01",
    "occurred_at": "2026-03-14T02:41:00-03:00",
    "attributes": {"note": "fire reported"},
    "reported_by": "tester",
}


@pytest.fixture
def client(make_client):
    return make_client(EchoLLM())


def _event(client, payload=LINE_TRIP) -> str:
    response = client.post("/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _suggestion(client, payload=LINE_TRIP) -> dict:
    response = client.post(f"/events/{_event(client, payload)}/suggestions")
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_event(client):
    event_id = _event(client)
    body = client.get(f"/events/{event_id}").json()
    assert body["element"] == "LT-FICT-230-04" and body["attributes"]["zone"] == 1


def test_suggestion_has_verified_citations_and_disclaimer(client):
    s = _suggestion(client)
    assert s["status"] == "pending_review" and s["refusal_reason"] is None
    assert s["steps"] and all(step["citations"] for step in s["steps"])
    cit = s["steps"][0]["citations"][0]
    assert cit["procedure_code"].startswith("PO-FICT-") and cit["quote"]
    assert "fictício" in s["disclaimer"].lower()
    assert client.get(f"/suggestions/{s['id']}").json() == s


def test_no_applicable_procedure_is_a_refusal_not_an_error(client):
    s = _suggestion(client, UNKNOWN)
    assert s["status"] == "refused"
    assert s["refusal_reason"] == "no_applicable_procedure"
    assert s["steps"] == []


def test_approve_flow_and_double_decision_conflict(client):
    s = _suggestion(client)
    body = {"outcome": "approve", "decided_by": "operador.teste"}
    ok = client.post(f"/suggestions/{s['id']}/decision", json=body)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    again = client.post(f"/suggestions/{s['id']}/decision", json=body)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "suggestion_not_pending"


def test_reject_requires_justification(client):
    s = _suggestion(client)
    url = f"/suggestions/{s['id']}/decision"
    bad = client.post(url, json={"outcome": "reject", "decided_by": "op"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "justification_required"
    blank = client.post(url, json={"outcome": "reject", "justification": "  ", "decided_by": "op"})
    assert blank.status_code == 422
    good = client.post(
        url,
        json={"outcome": "reject", "justification": "Passo 2 não se aplica.", "decided_by": "op"},
    )
    assert good.status_code == 200 and good.json()["status"] == "rejected"


def test_refused_suggestion_cannot_be_decided(client):
    s = _suggestion(client, UNKNOWN)
    response = client.post(
        f"/suggestions/{s['id']}/decision", json={"outcome": "approve", "decided_by": "op"}
    )
    assert response.status_code == 409


def test_audit_trail_is_ordered_and_chain_is_valid(client):
    s = _suggestion(client)
    client.post(f"/suggestions/{s['id']}/decision", json={"outcome": "approve", "decided_by": "op"})
    trail = client.get(f"/events/{s['event_id']}/audit").json()
    assert trail["chain_valid"] is True
    assert [e["kind"] for e in trail["entries"]] == [
        "EVENT_RECEIVED",
        "RETRIEVAL_DONE",
        "LLM_CALLED",
        "CITATIONS_VALIDATED",
        "SUGGESTION_CREATED",
        "DECISION_RECORDED",
    ]
    assert [e["seq"] for e in trail["entries"]] == sorted(e["seq"] for e in trail["entries"])


def test_tampering_with_an_audit_row_breaks_the_chain(client, db):
    s = _suggestion(client)
    # Only possible by disabling the guard trigger (table owner / superuser), which is the point:
    # the hash chain makes such an edit detectable.
    db.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update_delete")
    db.execute(
        'UPDATE audit_log SET payload = \'{"type": "adulterado"}\''
        " WHERE event_id = %s AND kind = 'EVENT_RECEIVED'",
        (s["event_id"],),
    )
    trail = client.get(f"/events/{s['event_id']}/audit").json()
    assert trail["chain_valid"] is False
    assert PostgresAudit(db).verify(s["event_id"]) is not None


def test_llm_unavailable_is_503_and_creates_no_suggestion(make_client, db):
    client = make_client(UnconfiguredLLM())
    event_id = _event(client)
    response = client.post(f"/events/{event_id}/suggestions")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_unavailable"
    assert db.execute("SELECT count(*) FROM suggestions").fetchone()[0] == 0


UNKNOWN_ID = "11111111-1111-1111-1111-111111111111"


def test_not_found_errors(client):
    assert client.get(f"/events/{UNKNOWN_ID}").json()["error"]["code"] == "event_not_found"
    assert client.get(f"/suggestions/{UNKNOWN_ID}").status_code == 404
    assert client.post(f"/events/{UNKNOWN_ID}/suggestions").status_code == 404
    assert client.get(f"/events/{UNKNOWN_ID}/audit").status_code == 404
    decision = client.post(
        f"/suggestions/{UNKNOWN_ID}/decision", json={"outcome": "approve", "decided_by": "op"}
    )
    assert decision.status_code == 404


def test_invalid_payloads_are_400_with_details(client):
    naive = {**LINE_TRIP, "occurred_at": "2026-03-14T02:41:00"}
    response = client.post("/events", json=naive)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_payload"
    assert response.json()["error"]["details"]["errors"]
    assert client.get("/events/not-a-uuid").status_code == 400
    bad_outcome = client.post(
        f"/suggestions/{UNKNOWN_ID}/decision", json={"outcome": "maybe", "decided_by": "op"}
    )
    assert bad_outcome.status_code == 400
