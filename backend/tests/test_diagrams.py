"""tests/test_diagrams.py"""
import pytest


VALID_PUML = """\
@startuml
actor User
participant Server
User -> Server: request
Server --> User: response
@enduml"""


@pytest.mark.asyncio
async def test_generate_full_mock(auth_client):
    """generate-full with mock backend returns valid structure."""
    resp = await auth_client.post("/api/diagrams/generate-full", json={
        "description":  "User login with JWT tokens",
        "diagram_type": "sequence",
        "language":     "python",
        "save":         True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "@startuml" in data["plantuml_code"]
    assert "@enduml"   in data["plantuml_code"]
    assert "implementation" in data
    assert data["implementation"]["code"]
    assert data["saved_id"] is not None


@pytest.mark.asyncio
async def test_generate_invalid_diagram_type(auth_client):
    resp = await auth_client.post("/api/diagrams/generate-full", json={
        "description": "testing invalid type", "diagram_type": "banana", "language": "python",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_invalid_language(auth_client):
    resp = await auth_client.post("/api/diagrams/generate-full", json={
        "description": "testing invalid language", "diagram_type": "sequence", "language": "cobol",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_save_and_list_diagrams(auth_client):
    # Save
    resp = await auth_client.post("/api/diagrams", json={
        "title":         "My test diagram",
        "description":   "A test",
        "diagram_type":  "class",
        "plantuml_code": VALID_PUML,
        "impl_language": "python",
    })
    assert resp.status_code == 201
    diag_id = resp.json()["id"]

    # List
    resp2 = await auth_client.get("/api/diagrams")
    assert resp2.status_code == 200
    ids = [d["id"] for d in resp2.json()]
    assert diag_id in ids


@pytest.mark.asyncio
async def test_get_diagram(auth_client):
    resp = await auth_client.post("/api/diagrams", json={
        "title": "Get test", "description": "test", "diagram_type": "class",
        "plantuml_code": VALID_PUML,
    })
    diag_id = resp.json()["id"]

    resp2 = await auth_client.get(f"/api/diagrams/{diag_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == diag_id


@pytest.mark.asyncio
async def test_get_nonexistent_diagram(auth_client):
    resp = await auth_client.get("/api/diagrams/doesnotexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_diagram(auth_client):
    resp = await auth_client.post("/api/diagrams", json={
        "title": "Original", "description": "d", "diagram_type": "er",
        "plantuml_code": VALID_PUML,
    })
    diag_id = resp.json()["id"]

    resp2 = await auth_client.patch(f"/api/diagrams/{diag_id}",
                                     json={"title": "Updated", "is_public": True})
    assert resp2.status_code == 200
    assert resp2.json()["title"]     == "Updated"
    assert resp2.json()["is_public"] is True


@pytest.mark.asyncio
async def test_delete_diagram(auth_client):
    resp = await auth_client.post("/api/diagrams", json={
        "title": "Delete me", "description": "d", "diagram_type": "state",
        "plantuml_code": VALID_PUML,
    })
    diag_id = resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/diagrams/{diag_id}")
    assert del_resp.status_code == 204

    get_resp = await auth_client.get(f"/api/diagrams/{diag_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_other_user_cannot_see_diagram(auth_client, second_auth_client):
    resp = await auth_client.post("/api/diagrams", json={
        "title": "Private", "description": "d", "diagram_type": "sequence",
        "plantuml_code": VALID_PUML,
    })
    diag_id = resp.json()["id"]

    resp2 = await second_auth_client.get(f"/api/diagrams/{diag_id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_public_diagram_accessible_without_auth(auth_client, client):
    resp = await auth_client.post("/api/diagrams", json={
        "title": "Public", "description": "d", "diagram_type": "class",
        "plantuml_code": VALID_PUML, "is_public": True,
    })
    diag_id = resp.json()["id"]

    resp2 = await client.get(f"/api/diagrams/public/{diag_id}")
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_folder_filter(auth_client):
    await auth_client.post("/api/diagrams", json={
        "title": "In folder", "description": "d", "diagram_type": "sequence",
        "plantuml_code": VALID_PUML, "folder": "auth-system",
    })
    await auth_client.post("/api/diagrams", json={
        "title": "No folder", "description": "d", "diagram_type": "sequence",
        "plantuml_code": VALID_PUML,
    })

    resp = await auth_client.get("/api/diagrams?folder=auth-system")
    assert resp.status_code == 200
    titles = [d["title"] for d in resp.json()]
    assert "In folder" in titles
    assert "No folder" not in titles


@pytest.mark.asyncio
async def test_refine_diagram(auth_client):
    create = await auth_client.post("/api/diagrams/generate-full", json={
        "description": "simple login", "diagram_type": "sequence",
        "language": "python", "save": True,
    })
    diag_id = create.json()["saved_id"]

    resp = await auth_client.post("/api/diagrams/refine", json={
        "diagram_id":  diag_id,
        "instruction": "Add a rate limiter participant",
        "language":    "python",
    })
    assert resp.status_code == 200
    assert "@startuml" in resp.json()["plantuml_code"]


@pytest.mark.asyncio
async def test_generate_code_endpoint(auth_client):
    resp = await auth_client.post("/api/diagrams/generate-code", json={
        "plantuml_code": VALID_PUML,
        "diagram_type":  "sequence",
        "language":      "typescript",
    })
    assert resp.status_code == 200
    assert resp.json()["code"]
    assert resp.json()["language"] == "typescript"
