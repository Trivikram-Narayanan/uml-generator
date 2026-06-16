"""tests/test_auth.py"""
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/api/auth/register", json={
        "email": "new@example.com", "username": "newuser", "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token"  in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "username": "dupuser1", "password": "pass1234"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json={**payload, "username": "dupuser2"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post("/api/auth/register", json={
        "email": "a@example.com", "username": "sameuser", "password": "pass1234"})
    resp = await client.post("/api/auth/register", json={
        "email": "b@example.com", "username": "sameuser", "password": "pass1234"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/auth/register", json={
        "email": "login@example.com", "username": "loginuser", "password": "mypassword",
    })
    resp = await client.post("/api/auth/login",
        data={"username": "login@example.com", "password": "mypassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "wp@example.com", "username": "wpuser", "password": "correct",
    })
    resp = await client.post("/api/auth/login",
        data={"username": "wp@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]    == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    reg = await client.post("/api/auth/register", json={
        "email": "refresh@example.com", "username": "refreshuser", "password": "pass1234",
    })
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh",
        json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_invalid_token(client):
    resp = await client.post("/api/auth/refresh", json={"refresh_token": "not.a.token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_short_password_rejected(client):
    resp = await client.post("/api/auth/register", json={
        "email": "short@example.com", "username": "shortpw", "password": "abc",
    })
    assert resp.status_code == 422
