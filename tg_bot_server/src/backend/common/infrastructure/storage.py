from asyncio import to_thread
from typing import Any

import boto3

from backend.common.application import StoredObject


class S3ObjectStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str,
        signed_url_ttl_seconds: int,
    ) -> None:
        self._bucket = bucket
        self._signed_url_ttl_seconds = signed_url_ttl_seconds
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            region_name=region,
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    async def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        await to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=storage_key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(
            bucket=self._bucket,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(content),
        )

    async def delete(self, storage_key: str) -> None:
        await to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=storage_key,
        )

    async def create_download_url(self, storage_key: str) -> str:
        return await to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=self._signed_url_ttl_seconds,
        )
