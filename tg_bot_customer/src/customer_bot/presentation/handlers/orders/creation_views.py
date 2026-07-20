from customer_bot.presentation.view_models import ServiceOptionView, ServiceView


def service_view(item: dict[str, object]) -> ServiceView:
    raw_options = item.get("options")
    options = raw_options if isinstance(raw_options, list) else []
    return ServiceView(
        id=str(item["id"]),
        name=str(item["name"]),
        category_code=str(item["category_code"]),
        category_name=str(item["category_name"]),
        care_object_type=str(item["care_object_type"]),
        max_objects_per_order=int(str(item["max_objects_per_order"])),
        price_type=str(item["price_type"]),
        allows_multiday=item["allows_multiday"] is True,
        min_duration_minutes=(
            int(str(item["min_duration_minutes"]))
            if isinstance(item.get("min_duration_minutes"), int)
            else None
        ),
        max_duration_minutes=(
            int(str(item["max_duration_minutes"]))
            if isinstance(item.get("max_duration_minutes"), int)
            else None
        ),
        duration_step_minutes=(
            int(str(item["duration_step_minutes"]))
            if isinstance(item.get("duration_step_minutes"), int)
            else None
        ),
        location_policy=str(item["location_policy"]),
        photo_policy=str(item["photo_policy"]),
        options=tuple(
            ServiceOptionView(
                id=str(option["id"]),
                name=str(option["name"]),
            )
            for option in options
            if isinstance(option, dict)
        ),
    )
