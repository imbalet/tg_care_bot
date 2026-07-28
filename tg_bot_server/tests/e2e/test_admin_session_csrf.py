from typing import Any

import httpx
import pytest


@pytest.mark.e2e
async def test_admin_login_cookie_session_and_logout(
    e2e_client: httpx.AsyncClient,
    test_settings: Any,
) -> None:
    login_response = await e2e_client.post(
        "/admin/login",
        json={
            "email": test_settings.default_admin_email,
            "password": test_settings.default_admin_password,
        },
    )

    assert login_response.status_code == 200, login_response.text
    set_cookie = login_response.headers["set-cookie"]
    assert "admin_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/admin" in set_cookie
    csrf_token = login_response.json()["csrf_token"]
    assert csrf_token

    me_response = await e2e_client.get("/admin/me")
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == test_settings.default_admin_email

    missing_csrf_response = await e2e_client.post("/admin/logout")
    assert missing_csrf_response.status_code == 403, missing_csrf_response.text

    invalid_csrf_response = await e2e_client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": "invalid-csrf-token"},
    )
    assert invalid_csrf_response.status_code == 403, invalid_csrf_response.text

    logout_response = await e2e_client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_response.status_code == 204, logout_response.text

    after_logout_response = await e2e_client.get("/admin/me")
    assert after_logout_response.status_code == 401, after_logout_response.text


@pytest.mark.e2e
async def test_admin_session_rejects_reused_csrf_request_after_logout(
    e2e_client: httpx.AsyncClient,
    test_settings: Any,
) -> None:
    login_response = await e2e_client.post(
        "/admin/login",
        json={
            "email": test_settings.default_admin_email,
            "password": test_settings.default_admin_password,
        },
    )
    assert login_response.status_code == 200, login_response.text
    csrf_token = login_response.json()["csrf_token"]

    logout_response = await e2e_client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_response.status_code == 204, logout_response.text

    reused_csrf_response = await e2e_client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert reused_csrf_response.status_code == 401, reused_csrf_response.text


@pytest.mark.e2e
async def test_admin_login_rejects_invalid_credentials_without_session(
    e2e_client: httpx.AsyncClient,
    test_settings: Any,
) -> None:
    response = await e2e_client.post(
        "/admin/login",
        json={
            "email": test_settings.default_admin_email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401, response.text
    assert "admin_session" not in response.headers.get("set-cookie", "")
