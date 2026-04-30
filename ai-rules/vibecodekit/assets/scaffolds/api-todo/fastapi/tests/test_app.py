from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_empty_after_clear():
    # Reset state for isolation.
    from app import main

    main._DB.clear()
    r = client.get("/todos")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list():
    from app import main

    main._DB.clear()
    r = client.post("/todos", json={"title": "buy coffee"})
    assert r.status_code == 201
    assert r.json()["title"] == "buy coffee"
    assert client.get("/todos").json()[0]["title"] == "buy coffee"
