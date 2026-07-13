import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import update

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.modules.catalog.infrastructure import LegalDocumentModel

TELEGRAPH_API_URL = "https://api.telegra.ph"

logger = logging.getLogger(__name__)


async def amain() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    docs_dir = Path(os.environ["LEGAL_DOCUMENTS_DIR"])
    access_token = await _access_token()
    container = create_container(get_settings())
    try:
        async with container.session_factory() as session:
            for path in sorted(docs_dir.glob("*.md")):
                document_type = path.stem
                title, content = _read_markdown(path)
                url = await _create_page(
                    access_token=access_token,
                    title=title,
                    content=content,
                )
                await session.execute(
                    update(LegalDocumentModel)
                    .where(
                        LegalDocumentModel.document_type == document_type,
                        LegalDocumentModel.is_active.is_(True),
                    )
                    .values(content_url=url),
                )
                logger.info(
                    "published legal document", extra={"document_type": document_type}
                )
            await session.commit()
    finally:
        await container.close()


async def _access_token() -> str:
    token = os.getenv("TELEGRAPH_ACCESS_TOKEN")
    if token:
        return token
    short_name = os.getenv("TELEGRAPH_SHORT_NAME", "we-are-close")
    author_name = os.getenv("TELEGRAPH_AUTHOR_NAME", "We Are Close")
    async with httpx.AsyncClient(base_url=TELEGRAPH_API_URL, timeout=10) as client:
        response = await client.post(
            "/createAccount",
            data={
                "short_name": short_name,
                "author_name": author_name,
            },
        )
    data = _telegraph_result(response)
    access_token = data.get("access_token")
    if not isinstance(access_token, str):
        raise RuntimeError("Telegraph did not return access token")
    logger.warning(
        "created Telegraph account; save TELEGRAPH_ACCESS_TOKEN before next run",
        extra={"short_name": short_name},
    )
    return access_token


async def _create_page(
    *,
    access_token: str,
    title: str,
    content: list[dict[str, Any] | str],
) -> str:
    async with httpx.AsyncClient(base_url=TELEGRAPH_API_URL, timeout=10) as client:
        response = await client.post(
            "/createPage",
            data={
                "access_token": access_token,
                "title": title,
                "author_name": os.getenv("TELEGRAPH_AUTHOR_NAME", "We Are Close"),
                "content": json.dumps(content, ensure_ascii=False),
                "return_content": "false",
            },
        )
    data = _telegraph_result(response)
    url = data.get("url")
    if not isinstance(url, str):
        raise RuntimeError("Telegraph did not return page URL")
    return url


def _telegraph_result(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("Telegraph request failed")
    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Telegraph response has no result")
    return result


def _read_markdown(path: Path) -> tuple[str, list[dict[str, Any] | str]]:
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    title = path.stem.replace("_", " ").title()
    content: list[dict[str, Any] | str] = []
    paragraph: list[str] = []
    for line in lines:
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            continue
        if line.startswith("## "):
            _flush_paragraph(content, paragraph)
            content.append(
                {"tag": "h3", "children": [line.removeprefix("## ").strip()]}
            )
            continue
        if not line:
            _flush_paragraph(content, paragraph)
            continue
        paragraph.append(line)
    _flush_paragraph(content, paragraph)
    if not content:
        content.append({"tag": "p", "children": [title]})
    return title, content


def _flush_paragraph(content: list[dict[str, Any] | str], paragraph: list[str]) -> None:
    if not paragraph:
        return
    content.append({"tag": "p", "children": [" ".join(paragraph)]})
    paragraph.clear()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
