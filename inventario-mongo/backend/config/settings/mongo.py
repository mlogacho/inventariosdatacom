"""
Configuración de conexión a MongoDB (MongoEngine).

ISO 27001 A.12.1: Configuración controlada por variables de entorno.
V-01 Fix: Soporta MONGO_DB_HOST como URI completa o MONGO_HOST + MONGO_PORT.
"""
import os
from mongoengine import connect


def init_mongo():
    """
    Inicializa la conexión a MongoDB.
    Acepta MONGO_DB_HOST como URI completa (preferido para Docker)
    o construye la URI desde MONGO_HOST + MONGO_PORT.
    """
    # Intentar URI completa primero (Docker Compose usa MONGO_DB_HOST)
    mongo_uri = os.getenv("MONGO_DB_HOST")
    db_name = os.getenv("MONGO_DB_NAME", "inventario_db")

    if mongo_uri:
        # URI completa: mongodb://host:port/dbname
        connect(
            host=mongo_uri,
            alias="default",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
    else:
        # Fallback: construir desde variables individuales
        host = os.getenv("MONGO_HOST", "localhost")
        port = int(os.getenv("MONGO_PORT", 27017))
        connect(
            db=db_name,
            host=host,
            port=port,
            alias="default",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            directConnection=True,
        )
