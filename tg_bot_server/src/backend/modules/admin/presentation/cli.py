import argparse
import asyncio

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.modules.admin.application import (
    BootstrapAdminCommand,
    BootstrapAdminUseCase,
)
from backend.modules.admin.infrastructure import (
    Argon2PasswordHasher,
    SqlAlchemyAdminRepository,
)


async def bootstrap_admin(email: str, full_name: str, password: str) -> None:
    settings = get_settings()
    container = create_container(settings)
    try:
        async with container.session_factory() as session:
            use_case = BootstrapAdminUseCase(
                repository=SqlAlchemyAdminRepository(session),
                password_hasher=Argon2PasswordHasher(),
            )
            await use_case.execute(
                BootstrapAdminCommand(
                    email=email,
                    full_name=full_name,
                    password=password,
                ),
            )
            await session.commit()
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


__all__ = ["bootstrap_admin", "main"]
