import asyncio
import hashlib
from typing import Any
from uuid import UUID

import httpx
import pytest
from botocore.exceptions import ClientError

from tests.support.settings import TestSettings

_PNG = b"\x89PNG\r\n\x1a\nvalid-e2e-png"
_PDF = b"%PDF-1.7\nvalid-e2e-pdf"


async def _s3_object(
    s3_client: Any,
    *,
    bucket: str,
    key: str,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        s3_client.get_object,
        Bucket=bucket,
        Key=key,
    )


async def _assert_s3_object_missing(
    s3_client: Any,
    *,
    bucket: str,
    key: str,
) -> None:
    with pytest.raises(ClientError) as error:
        await asyncio.to_thread(
            s3_client.head_object,
            Bucket=bucket,
            Key=key,
        )
    assert error.value.response["Error"]["Code"] in {"404", "NoSuchKey"}


async def _file_row(
    e2e_db: Any,
    file_id: str,
) -> dict[str, Any]:
    row = await e2e_db.fetchrow(
        """
        SELECT id, bucket, storage_key, original_name, mime_type,
               size_bytes, checksum, status, deleted_at
        FROM files
        WHERE id = $1
        """,
        file_id,
    )
    assert row is not None
    return dict(row)


@pytest.mark.e2e
async def test_actor_file_upload_persists_metadata_and_content(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    e2e_s3_client: Any,
    customer_factory,
    test_settings: TestSettings,
) -> None:
    customer = await customer_factory()
    response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/files",
        files={"file": ("customer evidence.png", _PNG, "image/png")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    file_id = payload["id"]
    row = await _file_row(e2e_db, file_id)
    assert row["bucket"] == test_settings.s3_bucket
    assert row["storage_key"].startswith(f"uploads/customer/{customer.entity_id}/")
    assert "customer evidence.png" not in row["storage_key"]
    assert row["original_name"] == "customer evidence.png"
    assert row["mime_type"] == "image/png"
    assert row["size_bytes"] == len(_PNG)
    assert row["checksum"] == hashlib.sha256(_PNG).hexdigest()
    assert row["status"] == "uploaded"

    stored = await _s3_object(
        e2e_s3_client,
        bucket=row["bucket"],
        key=row["storage_key"],
    )
    assert stored["Body"].read() == _PNG
    assert stored["ContentType"] == "image/png"

    link_count = await e2e_db.fetchval(
        "SELECT count(*) FROM file_links WHERE file_id = $1",
        UUID(file_id),
    )
    assert link_count == 1


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_fragment"),
    [
        ("empty.png", b"", "image/png", "empty or too large"),
        ("wrong.txt", b"text", "text/plain", "not allowed"),
        ("mismatch.png", _PNG, "image/jpeg", "signature"),
        (
            "too-large.png",
            b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024),
            "image/png",
            "empty or too large",
        ),
    ],
)
async def test_actor_file_upload_rejects_invalid_file(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    customer_factory,
    filename: str,
    content: bytes,
    content_type: str,
    expected_fragment: str,
) -> None:
    customer = await customer_factory()
    response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/files",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == 422, response.text
    assert expected_fragment in response.json()["error"]["message"]
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM files WHERE original_name = $1",
            filename,
        )
        == 0
    )


@pytest.mark.e2e
async def test_avatar_replacement_and_deletion_clean_up_s3_and_database(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    e2e_s3_client: Any,
    performer_factory,
    test_settings: TestSettings,
) -> None:
    performer = await performer_factory()

    first_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/avatar",
        files={"file": ("first.png", _PNG, "image/png")},
    )
    assert first_response.status_code == 201, first_response.text
    first_id = first_response.json()["id"]
    first_row = await _file_row(e2e_db, first_id)

    second_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/avatar",
        files={"file": ("second.png", _PNG, "image/png")},
    )
    assert second_response.status_code == 201, second_response.text
    second_id = second_response.json()["id"]
    second_row = await _file_row(e2e_db, second_id)

    first_after_replace = await _file_row(e2e_db, first_id)
    assert first_after_replace["status"] == "deleted"
    assert first_after_replace["deleted_at"] is not None
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM file_links WHERE file_id = $1",
            UUID(first_id),
        )
        == 0
    )
    assert (
        await e2e_db.fetchval(
            """
            SELECT count(*)
            FROM file_links
            WHERE file_id = $1 AND entity_type = 'performer'
              AND entity_id = $2 AND purpose = 'avatar'
            """,
            UUID(second_id),
            UUID(performer.entity_id),
        )
        == 1
    )
    await _assert_s3_object_missing(
        e2e_s3_client,
        bucket=test_settings.s3_bucket,
        key=first_row["storage_key"],
    )

    delete_response = await e2e_client.delete(
        f"/api/performers/by-telegram/{performer.telegram_id}/avatar",
    )
    assert delete_response.status_code == 200, delete_response.text
    second_after_delete = await _file_row(e2e_db, second_id)
    assert second_after_delete["status"] == "deleted"
    assert second_after_delete["deleted_at"] is not None
    assert (
        await e2e_db.fetchval(
            "SELECT count(*) FROM file_links WHERE file_id = $1",
            UUID(second_id),
        )
        == 0
    )
    await _assert_s3_object_missing(
        e2e_s3_client,
        bucket=test_settings.s3_bucket,
        key=second_row["storage_key"],
    )


@pytest.mark.e2e
async def test_support_attachment_has_private_signed_url_and_owner_check(
    e2e_client: httpx.AsyncClient,
    e2e_s3_client: Any,
    customer_factory,
) -> None:
    owner = await customer_factory()
    other_customer = await customer_factory()
    upload_response = await e2e_client.post(
        f"/api/customers/by-telegram/{owner.telegram_id}/files",
        files={"file": ("attachment.pdf", _PDF, "application/pdf")},
    )
    assert upload_response.status_code == 201, upload_response.text
    file_id = upload_response.json()["id"]

    create_response = await e2e_client.post(
        f"/api/customers/by-telegram/{owner.telegram_id}/support-requests",
        json={
            "type": "technical",
            "text": "Attachment access test",
            "file_ids": [file_id],
        },
    )
    assert create_response.status_code == 201, create_response.text
    record_id = create_response.json()["id"]

    owner_response = await e2e_client.get(
        f"/api/customers/by-telegram/{owner.telegram_id}/support/{record_id}",
    )
    assert owner_response.status_code == 200, owner_response.text
    files = owner_response.json()["files"]
    assert len(files) == 1
    signed_url = files[0]["url"]
    assert signed_url

    async with httpx.AsyncClient() as public_client:
        signed_response = await public_client.get(signed_url)
    assert signed_response.status_code == 200
    assert signed_response.content == _PDF

    unauthorized_response = await e2e_client.get(
        f"/api/customers/by-telegram/{other_customer.telegram_id}/support/{record_id}",
    )
    assert unauthorized_response.status_code == 403, unauthorized_response.text

    parsed_url = httpx.URL(signed_url)
    direct_object_url = str(parsed_url.copy_with(query=None))
    async with httpx.AsyncClient() as public_client:
        private_response = await public_client.get(direct_object_url)
    assert private_response.status_code in {403, 404}
