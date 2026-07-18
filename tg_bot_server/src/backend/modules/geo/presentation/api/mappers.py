from backend.modules.geo.application import AddressSuggestionDTO

from .schemas import AddressSuggestionResponse


def suggestion_response(suggestion: AddressSuggestionDTO) -> AddressSuggestionResponse:
    return AddressSuggestionResponse(
        value=suggestion.value,
        unrestricted_value=suggestion.unrestricted_value,
        fias_id=suggestion.fias_id,
        latitude=suggestion.latitude,
        longitude=suggestion.longitude,
        quality=suggestion.quality,
    )
