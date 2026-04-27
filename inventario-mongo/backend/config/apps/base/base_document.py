from datetime import datetime, timezone
import mongoengine as me


class BaseDocument(me.Document):
    """
    Documento base para todos los modelos MongoEngine.
    Incluye auditoría básica y soft delete.
    """

    created_at = me.DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = me.DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active = me.BooleanField(default=True)

    meta = {
        "abstract": True
    }

    def save(self, *args, **kwargs):
        from config.utils.transaction_manager import get_current_session
        self.updated_at = datetime.now(timezone.utc)
        
        session = get_current_session()
        if session and 'session' not in kwargs:
            kwargs['session'] = session
            
        return super().save(*args, **kwargs)

    def delete(self, hard=False, *args, **kwargs):
        """
        Soft delete por defecto, hard delete si se especifica.
        """
        from config.utils.transaction_manager import get_current_session
        session = get_current_session()
        if session and 'session' not in kwargs:
            kwargs['session'] = session

        if hard:
            return super().delete(*args, **kwargs)
            
        self.is_active = False
        return self.save(*args, **kwargs)