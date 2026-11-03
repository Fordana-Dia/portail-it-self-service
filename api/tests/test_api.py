import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_documentation_api():
    assert client.get("/docs").status_code == 200


def test_mauvais_identifiants_refuses():
    r = client.post("/auth/login", data={"username": "inconnu", "password": "mauvais"})
    assert r.status_code in (400, 401, 403, 429)
