from rest_framework.views import exception_handler as drf_handler


def exception_handler(exc, context):
    """DRF errors as {"detail": "...", "errors": {...}} so the UI can show one message."""
    response = drf_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" not in data:
        first = next(iter(data.values()), "")
        msg = first[0] if isinstance(first, list) and first else first
        response.data = {"detail": str(msg) or "Invalid request.", "errors": data}
    elif isinstance(data, list):
        response.data = {"detail": str(data[0]) if data else "Invalid request."}
    return response
