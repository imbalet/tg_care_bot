from typing import cast

from fastapi import Request

from backend.bootstrap.container import Container


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)
