from backend.common.domain import ValidationError

CARE_OBJECT_TYPES = frozenset(("child", "ward", "pet"))
AGE_GROUPS = frozenset(
    ("infant", "preschool", "school_age", "teenager", "adult", "senior", "unknown"),
)
PET_SIZES = frozenset(("small", "medium", "large", "unknown"))


def validate_care_object_fields(
    *,
    object_type: str,
    age_group: str,
    species: str | None,
    breed: str | None,
    pet_size: str | None,
    mobility_assistance_required: bool | None,
) -> None:
    if object_type not in CARE_OBJECT_TYPES:
        raise ValidationError("Unknown care object type")
    if age_group not in AGE_GROUPS:
        raise ValidationError("Unknown age group")
    if pet_size is not None and pet_size not in PET_SIZES:
        raise ValidationError("Unknown pet size")
    if object_type == "pet":
        if species is None or pet_size is None:
            raise ValidationError("Pet species and size are required")
        return
    if species is not None or breed is not None or pet_size is not None:
        raise ValidationError("Pet fields are allowed only for pets")
    if object_type == "ward":
        if mobility_assistance_required is None:
            raise ValidationError("Ward mobility assistance value is required")
        return
    if mobility_assistance_required is not None:
        raise ValidationError("Mobility assistance is allowed only for wards")


__all__ = [
    "AGE_GROUPS",
    "CARE_OBJECT_TYPES",
    "PET_SIZES",
    "validate_care_object_fields",
]
