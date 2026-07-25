from __future__ import annotations

import asyncpg
import httpx
import pytest


@pytest.mark.e2e
async def test_empty_geocoding_result_is_not_saved(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
) -> None:
    performer = await performer_factory()
    suggestions_response = await e2e_client.get(
        "/api/geocoding/address-suggestions",
        params={"city_id": performer.city_id, "query": "E2E_EMPTY"},
    )
    assert suggestions_response.status_code == 200, suggestions_response.text
    assert suggestions_response.json() == []

    before_count = await e2e_db.fetchval(
        """
        SELECT count(*)
        FROM addresses
        WHERE performer_id = $1 AND deleted_at IS NULL
        """,
        performer.entity_id,
    )
    create_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/addresses",
        json={"city_id": performer.city_id, "unrestricted_value": "E2E_EMPTY"},
    )
    assert create_response.status_code == 422, create_response.text
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM addresses
            WHERE performer_id = $1 AND deleted_at IS NULL
            """,
            performer.entity_id,
        )
        == before_count
    )


@pytest.mark.e2e
async def test_ambiguous_geocoding_result_is_not_saved(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
) -> None:
    performer = await performer_factory()
    suggestions_response = await e2e_client.get(
        "/api/geocoding/address-suggestions",
        params={"city_id": performer.city_id, "query": "E2E_AMBIGUOUS"},
    )
    assert suggestions_response.status_code == 200, suggestions_response.text
    assert len(suggestions_response.json()) == 2

    before_count = await e2e_db.fetchval(
        """
        SELECT count(*)
        FROM addresses
        WHERE performer_id = $1 AND deleted_at IS NULL
        """,
        performer.entity_id,
    )
    create_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/addresses",
        json={
            "city_id": performer.city_id,
            "unrestricted_value": "E2E_AMBIGUOUS",
        },
    )
    assert create_response.status_code == 422, create_response.text
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM addresses
            WHERE performer_id = $1 AND deleted_at IS NULL
            """,
            performer.entity_id,
        )
        == before_count
    )


@pytest.mark.e2e
@pytest.mark.parametrize("query", ["E2E_TIMEOUT", "E2E_5XX"])
async def test_geocoding_transport_errors_do_not_save_address(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    performer_factory,
    query: str,
) -> None:
    performer = await performer_factory()
    before_count = await e2e_db.fetchval(
        """
        SELECT count(*)
        FROM addresses
        WHERE performer_id = $1 AND deleted_at IS NULL
        """,
        performer.entity_id,
    )

    create_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/addresses",
        json={
            "city_id": performer.city_id,
            "unrestricted_value": query,
        },
    )
    assert create_response.status_code == 422, create_response.text
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM addresses
            WHERE performer_id = $1 AND deleted_at IS NULL
            """,
            performer.entity_id,
        )
        == before_count
    )
