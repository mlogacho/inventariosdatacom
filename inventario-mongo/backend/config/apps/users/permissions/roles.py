from enum import Enum


class Roles(str, Enum):
    ADMIN = "admin"
    TECNICO = "tecnico"
    ADMINISTRATIVO = "administrativo"
