import os
import tempfile
from datetime import date, timedelta

os.environ["DATA_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        yield c


def signup(c, email="asha@example.com", name="Asha"):
    r = c.post("/api/register", json={"email": email, "password": "password123", "name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_auth(client):
    signup(client, "a@b.com")
    assert client.post("/api/register", json={"email": "a@b.com", "password": "password123"}).status_code == 409
    assert client.post("/api/register", json={"email": "bad", "password": "password123"}).status_code == 422
    assert client.post("/api/login", json={"email": "a@b.com", "password": "wrong-pass1"}).status_code == 401
    assert client.post("/api/login", json={"email": "a@b.com", "password": "password123"}).status_code == 200
    assert client.get("/api/applications").status_code == 401


def test_applications_crud_and_isolation(client):
    h = signup(client, "one@x.com")
    h2 = signup(client, "two@x.com")
    r = client.post("/api/applications", headers=h, json={"company": "Zoho", "role": "MTS", "status": "applied",
                                                           "ctc_lpa": 8, "next_date": "2026-10-20", "link": "https://zoho.com/jobs"})
    assert r.status_code == 201
    aid = r.json()["id"]
    assert client.post("/api/applications", headers=h, json={"company": "X", "link": "javascript:alert(1)"}).status_code == 422
    assert client.patch(f"/api/applications/{aid}/status", headers=h, json={"status": "interview"}).status_code == 200
    got = client.get("/api/applications", headers=h).json()
    assert got[0]["status"] == "interview" and got[0]["ctc_lpa"] == 8
    assert client.get("/api/applications", headers=h2).json() == []
    assert client.put(f"/api/applications/{aid}", headers=h2, json={"company": "Hack"}).status_code == 404
    assert client.delete(f"/api/applications/{aid}", headers=h2).status_code == 404
    assert client.delete(f"/api/applications/{aid}", headers=h).status_code == 204


def test_problem_spaced_repetition(client):
    h = signup(client, "dsa@x.com")
    today = main.today()
    pid = client.post("/api/problems", headers=h, json={"title": "Two Sum", "topic": "Arrays", "status": "solved",
                                                          "confidence": 5}).json()["id"]
    p = client.get("/api/problems", headers=h).json()[0]
    assert p["solved_on"] == today.isoformat()
    assert p["next_review"] == (today + timedelta(days=30)).isoformat()

    todo = client.post("/api/problems", headers=h, json={"title": "Word Break"}).json()["id"]
    assert [x for x in client.get("/api/problems", headers=h).json() if x["id"] == todo][0]["next_review"] is None

    r = client.post(f"/api/problems/{pid}/review", headers=h, json={"confidence": 1}).json()
    assert r["next_review"] == (today + timedelta(days=1)).isoformat()
    p = [x for x in client.get("/api/problems", headers=h).json() if x["id"] == pid][0]
    assert p["status"] == "revisit" and p["review_count"] == 1

    # marking a todo item solved through edit sets dates
    client.put(f"/api/problems/{todo}", headers=h, json={"title": "Word Break", "status": "solved", "confidence": 3})
    p = [x for x in client.get("/api/problems", headers=h).json() if x["id"] == todo][0]
    assert p["next_review"] == (today + timedelta(days=7)).isoformat()


def test_mocks_validation(client):
    h = signup(client, "mock@x.com")
    assert client.post("/api/mocks", headers=h, json={"title": "t", "score": 30, "max_score": 25, "taken_on": "2026-10-01"}).status_code == 422
    assert client.post("/api/mocks", headers=h, json={"title": "Quant", "score": 18, "max_score": 25, "taken_on": "2026-10-01"}).status_code == 201
    assert len(client.get("/api/mocks", headers=h).json()) == 1


def test_dashboard_demo_and_export(client):
    h = signup(client, "dash@x.com", "Dev")
    empty = client.get("/api/dashboard", headers=h).json()
    assert empty["totals"]["applications"] == 0 and empty["totals"]["streak"] == 0

    assert client.post("/api/demo", headers=h).status_code == 201
    assert client.post("/api/demo", headers=h).status_code == 409
    d = client.get("/api/dashboard", headers=h).json()
    assert d["user"]["name"] == "Dev"
    assert d["totals"]["applications"] == 6 and d["totals"]["offers"] == 1
    assert d["totals"]["streak"] >= 5 and d["totals"]["solved"] == 9
    assert d["totals"]["due"] >= 1 and d["upcoming"] and d["topics"] and d["mocks"]
    assert sum(d["pipeline"].values()) == 6

    csv_text = client.get("/api/export/applications.csv", headers=h).text
    assert csv_text.splitlines()[0].startswith("company,role,status") and "Zoho" in csv_text
    assert client.get("/api/export/users.csv", headers=h).status_code == 404

    assert client.delete("/api/data", headers=h).status_code == 204
    assert client.get("/api/dashboard", headers=h).json()["totals"]["problems"] == 0


def test_csv_formula_guard(client):
    h = signup(client, "csv@x.com")
    client.post("/api/applications", headers=h, json={"company": "=HYPERLINK(\"http://evil\")"})
    assert "'=HYPERLINK" in client.get("/api/export/applications.csv", headers=h).text


def test_seed_account(client):
    import seed
    seed.main()
    r = client.post("/api/login", json={"email": seed.EMAIL, "password": seed.PASSWORD})
    assert r.status_code == 200 and r.json()["name"] == "Dev Shah"
    h = {"Authorization": "Bearer " + r.json()["token"]}
    d = client.get("/api/dashboard", headers=h).json()
    assert d["totals"]["applications"] == 12 and d["totals"]["problems"] == 33
    assert d["totals"]["streak"] >= 9 and d["totals"]["due"] >= 3 and len(d["mocks"]) == 10
    seed.main()  # idempotent: re-running resets instead of duplicating
    assert client.get("/api/dashboard", headers=h).json()["totals"]["applications"] == 12
