import argparse
import asyncio

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.modules.admin.application import BootstrapAdminCommand


async def bootstrap_admin(email: str, full_name: str, password: str) -> None:
    settings = get_settings()
    container = create_container(settings)
    try:
        await container.services().bootstrap_admin(
            BootstrapAdminCommand(
                email=email,
                full_name=full_name,
                password=password,
            ),
        )
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap first admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(
        bootstrap_admin(
            email=args.email,
            full_name=args.full_name,
            password=args.password,
        ),
    )


if __name__ == "__main__":
    main()
