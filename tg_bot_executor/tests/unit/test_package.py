import executor_bot


def test_executor_bot_package_imports() -> None:
    assert executor_bot.__all__ == []
