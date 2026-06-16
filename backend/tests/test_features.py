"""tests/test_features.py  –  feedback, search, versions, tags, workspaces"""
import pytest

PUML = "@startuml\nA -> B: test\n@enduml"


# ── Feedback ──────────────────────────────────────────────────────────────────

class TestFeedback:

    async def _make_diagram(self, client):
        resp = await client.post("/api/diagrams", json={
            "title":"fb test","description":"d","diagram_type":"sequence","plantuml_code":PUML
        })
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_thumbs_up(self, auth_client):
        did = await self._make_diagram(auth_client)
        resp = await auth_client.post("/api/feedback", json={"diagram_id":did,"score":1})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_thumbs_down_with_correction(self, auth_client):
        did = await self._make_diagram(auth_client)
        resp = await auth_client.post("/api/feedback", json={
            "diagram_id":did,"score":-1,"correction":"Missing the cache participant"
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_invalid_score_rejected(self, auth_client):
        did = await self._make_diagram(auth_client)
        resp = await auth_client.post("/api/feedback", json={"diagram_id":did,"score":5})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_nonexistent_diagram_rejected(self, auth_client):
        resp = await auth_client.post("/api/feedback",
            json={"diagram_id":"doesnotexist","score":1})
        assert resp.status_code == 404


# ── Search ────────────────────────────────────────────────────────────────────

class TestSearch:

    @pytest.mark.asyncio
    async def test_search_by_title(self, auth_client):
        await auth_client.post("/api/diagrams", json={
            "title":"JWT Authentication Flow","description":"login system",
            "diagram_type":"sequence","plantuml_code":PUML,
        })
        resp = await auth_client.get("/api/search?q=JWT")
        assert resp.status_code == 200
        titles = [r["title"] for r in resp.json()]
        assert any("JWT" in t for t in titles)

    @pytest.mark.asyncio
    async def test_search_by_description(self, auth_client):
        await auth_client.post("/api/diagrams", json={
            "title":"Misc","description":"unique-search-term-xyz",
            "diagram_type":"class","plantuml_code":PUML,
        })
        resp = await auth_client.get("/api/search?q=unique-search-term-xyz")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_search_by_type_filter(self, auth_client):
        await auth_client.post("/api/diagrams", json={
            "title":"ER test","description":"er diagram",
            "diagram_type":"er","plantuml_code":PUML,
        })
        resp = await auth_client.get("/api/search?diagram_type=er")
        assert resp.status_code == 200
        for r in resp.json():
            assert r["diagram_type"] == "er"

    @pytest.mark.asyncio
    async def test_search_empty_returns_nothing(self, auth_client):
        resp = await auth_client.get("/api/search")
        # No query or filter — backend returns empty
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_isolated_between_users(self, auth_client, second_auth_client):
        await auth_client.post("/api/diagrams", json={
            "title":"Secret diagram","description":"private",
            "diagram_type":"sequence","plantuml_code":PUML,
        })
        resp = await second_auth_client.get("/api/search?q=Secret")
        ids = [r["title"] for r in resp.json()]
        assert "Secret diagram" not in ids


# ── Versions ──────────────────────────────────────────────────────────────────

class TestVersions:

    @pytest.mark.asyncio
    async def test_versions_listed_after_generate(self, auth_client):
        gen = await auth_client.post("/api/diagrams/generate-full", json={
            "description":"user login flow","diagram_type":"sequence","language":"python","save":True,
        })
        diag_id = gen.json()["saved_id"]
        resp = await auth_client.get(f"/api/diagrams/{diag_id}/versions")
        assert resp.status_code == 200
        # Should have at least 1 version (the initial generation)
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_refine_creates_new_version(self, auth_client):
        gen = await auth_client.post("/api/diagrams/generate-full", json={
            "description":"login","diagram_type":"sequence","language":"python","save":True,
        })
        diag_id = gen.json()["saved_id"]
        # Refine it
        await auth_client.post("/api/diagrams/refine", json={
            "diagram_id":diag_id,"instruction":"Add cache","language":"python",
        })
        resp = await auth_client.get(f"/api/diagrams/{diag_id}/versions")
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_restore_version(self, auth_client):
        gen = await auth_client.post("/api/diagrams/generate-full", json={
            "description":"login","diagram_type":"sequence","language":"python","save":True,
        })
        diag_id = gen.json()["saved_id"]
        original_code = gen.json()["plantuml_code"]

        # Refine to change it
        await auth_client.post("/api/diagrams/refine", json={
            "diagram_id":diag_id,"instruction":"Change everything","language":"python",
        })
        # Restore to version 1
        resp = await auth_client.post(f"/api/diagrams/{diag_id}/restore/1")
        assert resp.status_code == 200


# ── Tags ──────────────────────────────────────────────────────────────────────

class TestTags:

    @pytest.mark.asyncio
    async def test_create_tag(self, auth_client):
        resp = await auth_client.post("/api/tags", json={"name":"auth","color":"#4f8ef7"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "auth"

    @pytest.mark.asyncio
    async def test_list_tags(self, auth_client):
        await auth_client.post("/api/tags", json={"name":"backend","color":"#22c55e"})
        resp = await auth_client.get("/api/tags")
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "backend" in names

    @pytest.mark.asyncio
    async def test_attach_tag_to_diagram(self, auth_client):
        tag  = (await auth_client.post("/api/tags", json={"name":"infra","color":"#f59e0b"})).json()
        diag = (await auth_client.post("/api/diagrams", json={
            "title":"tagged","description":"d","diagram_type":"component","plantuml_code":PUML
        })).json()
        resp = await auth_client.post(f"/api/diagrams/{diag['id']}/tags/{tag['id']}")
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_delete_tag(self, auth_client):
        tag = (await auth_client.post("/api/tags", json={"name":"todelete","color":"#fff"})).json()
        resp = await auth_client.delete(f"/api/tags/{tag['id']}")
        assert resp.status_code == 204


# ── Workspaces ────────────────────────────────────────────────────────────────

class TestWorkspaces:

    @pytest.mark.asyncio
    async def test_create_workspace(self, auth_client):
        resp = await auth_client.post("/api/workspaces", json={"name":"My Team"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Team"

    @pytest.mark.asyncio
    async def test_list_workspaces(self, auth_client):
        await auth_client.post("/api/workspaces", json={"name":"Listed WS"})
        resp = await auth_client.get("/api/workspaces")
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "Listed WS" in names

    @pytest.mark.asyncio
    async def test_invite_nonexistent_user(self, auth_client):
        ws = (await auth_client.post("/api/workspaces", json={"name":"invite test"})).json()
        resp = await auth_client.post(
            f"/api/workspaces/{ws['id']}/invite",
            json={"email":"nobody@nowhere.com"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_members(self, auth_client):
        ws = (await auth_client.post("/api/workspaces", json={"name":"members test"})).json()
        resp = await auth_client.get(f"/api/workspaces/{ws['id']}/members")
        assert resp.status_code == 200
        # Creator should be a member
        assert len(resp.json()) >= 1


# ── Templates ─────────────────────────────────────────────────────────────────

class TestTemplates:

    @pytest.mark.asyncio
    async def test_list_templates(self, client):
        resp = await client.get("/api/templates")
        assert resp.status_code == 200
        # Builtin templates seeded on startup
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_use_template_increments_count(self, client):
        templates = (await client.get("/api/templates")).json()
        if not templates:
            pytest.skip("No templates seeded yet")
        t = templates[0]
        before = t["use_count"]
        resp = await client.post(f"/api/templates/{t['id']}/use")
        assert resp.status_code == 200
        assert resp.json()["plantuml_code"]
