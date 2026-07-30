from uuid import uuid4

from customer_bot.application.dto import OrderMatchDTO
from customer_bot.presentation.ui.screens.orders.order_matches import Screen


def test_order_match_actions_are_on_one_row_per_response() -> None:
    screen = Screen(
        (
            OrderMatchDTO(
                id=uuid4(),
                order_id=uuid4(),
                performer_id=uuid4(),
                match_type="pool",
                status="active",
            ),
            OrderMatchDTO(
                id=uuid4(),
                order_id=uuid4(),
                performer_id=uuid4(),
                match_type="pool",
                status="active",
            ),
        ),
    ).build()

    action_rows = screen.reply_markup.inline_keyboard[:2]

    assert [len(row) for row in action_rows] == [3, 3]
    assert [button.text for button in action_rows[0]] == [
        "Выбрать #1",
        "Отклонить #1",
        "Открыть профиль",
    ]
    assert [button.text for button in action_rows[1]] == [
        "Выбрать #2",
        "Отклонить #2",
        "Открыть профиль",
    ]
