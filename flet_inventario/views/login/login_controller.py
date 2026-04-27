from core.session import Session
from views.menu_view import menu_view
from services.auth_service import login


def handle_login(page, username, password, message):
    data, error = login(username, password)

    if error:
        message.value = error.get("detail", "Error de login")
        page.update()
        return

    # ✅ CLAVE
    Session.set(
        token=data["access_token"],
        user=data["user"]
    )

    # Limpiar UI de login y establecer Menu como base
    page.clean()
    page.add(menu_view(page))
