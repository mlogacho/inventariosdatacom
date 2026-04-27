import threading
import logging
import mongoengine
from functools import wraps

logger = logging.getLogger(__name__)

# Almacenamiento local del hilo para la sesión actual de MongoDB
_thread_local = threading.local()

def get_current_session():
    """Retorna la sesión de MongoDB activa para el hilo actual, si existe."""
    return getattr(_thread_local, 'mongo_session', None)

class mongo_transaction:
    """
    Context manager y Decorador para transacciones de MongoDB.
    Requiere que MongoDB esté configurado como Replica Set.
    """
    def __init__(self, throw_on_no_replica=True):
        self.session = None
        self.throw_on_no_replica = throw_on_no_replica

    def __enter__(self):
        try:
            # Iniciamos sesión desde la conexión predeterminada de mongoengine
            connection = mongoengine.get_connection()
            self.session = connection.start_session()
            self.session.start_transaction()
            
            # Guardamos en el local del hilo para que BaseDocument lo encuentre
            _thread_local.mongo_session = self.session
            return self.session
        except Exception as e:
            if "replica set" in str(e).lower():
                logger.warning("No se pudo iniciar transacción: MongoDB no es un Replica Set. Procediendo sin transacción.")
                if self.throw_on_no_replica:
                    raise
            else:
                logger.error(f"Error al iniciar sesión de MongoDB: {e}")
                raise
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.session:
            return

        try:
            if exc_type is None:
                self.session.commit_transaction()
            else:
                logger.warning(f"Abortando transacción de MongoDB debido a error: {exc_val}")
                self.session.abort_transaction()
        except Exception as e:
            logger.error(f"Error al finalizar transacción de MongoDB: {e}")
        finally:
            self.session.end_session()
            _thread_local.mongo_session = None

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper
