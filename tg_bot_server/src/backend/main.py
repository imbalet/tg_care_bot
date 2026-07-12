import uvicorn


def main() -> None:
    uvicorn.run(
        "backend.bootstrap.api:app",
        host="0.0.0.0",  # noqa: S104 - container entrypoint must be externally reachable.
        port=8000,
        factory=False,
    )


if __name__ == "__main__":
    main()
