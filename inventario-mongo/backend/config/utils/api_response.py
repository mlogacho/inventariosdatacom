from rest_framework.response import Response
from rest_framework import status

def api_response(data=None, message="", status_code=status.HTTP_200_OK, success=True):
    """
    Standardize API responses.
    """
    return Response(
        {
            "success": success,
            "message": message,
            "data": data,
        },
        status=status_code
    )
