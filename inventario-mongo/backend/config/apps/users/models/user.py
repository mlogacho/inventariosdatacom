import mongoengine as me
from django.contrib.auth.hashers import make_password, check_password

from config.apps.base.base_document import BaseDocument
from config.apps.users.permissions.roles import Roles


class User(BaseDocument):
    """
    Modelo de usuario del sistema.
    Autenticación basada en MongoEngine + JWT.
    """

    username = me.StringField(
        required=True,
        unique=True,
        min_length=3,
        max_length=50
    )

    password_hash = me.StringField(required=True)

    rol = me.StringField(
        required=True,
        choices=[role.value for role in Roles]
    )

    meta = {
        "collection": "usuarios",  # IMPORTANTE: no romper datos existentes
        "indexes": ["username"],
    }

    # =========================
    # PASSWORD MANAGEMENT
    # =========================
    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)

    # =========================
    # DJANGO COMPATIBILITY (DRF)
    # =========================
    @property
    def is_authenticated(self):
        """Requerido por DRF IsAuthenticated permission."""
        return True

    @property
    def is_anonymous(self):
        """Requerido por DRF authentication system."""
        return False

    @property
    def is_staff(self):
        """Requerido por algunos sistemas de permisos internos."""
        return self.rol == "admin"

    def __str__(self):
        return f"{self.username} ({self.rol})"
