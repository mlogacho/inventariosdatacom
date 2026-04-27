from core.api_client import APIClient
from core.session import Session

# =========================
# INICIAR SESIÓN
# =========================
def login(username, password):
    """
    Realiza la autenticación contra el backend.
    Retorna (data, error).
    """
    data = {
        "username": username,
        "password": password
    }
    
    try:
        response_data = APIClient.post("users/login/", json=data)
        
        # El backend devuelve 'access_token' y 'user'
        if response_data and "access_token" in response_data:
            return response_data, None
            
        return None, {"detail": "Respuesta de servidor inválida"}
        
    except Exception as e:
        return None, {"detail": str(e)}
