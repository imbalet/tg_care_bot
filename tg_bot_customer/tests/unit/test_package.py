import customer_bot


def test_customer_bot_package_imports() -> None:
    assert customer_bot.__all__ == []
