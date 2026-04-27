from mongoengine.queryset.visitor import Q

class BaseRepository:
    model = None

    @classmethod
    def get_all(cls, session=None, **filters):
        qs = cls.model.objects.filter(**filters)
        if session:
            qs = qs.with_session(session)
        return qs

    @classmethod
    def get_by_id(cls, entity_id, session=None):
        qs = cls.model.objects(id=entity_id)
        if session:
            qs = qs.with_session(session)
        return qs.first()

    @classmethod
    def create(cls, session=None, **data):
        instance = cls.model(**data)
        instance.save(session=session)
        return instance

    @classmethod
    def update(cls, entity, session=None, **data):
        for key, value in data.items():
            setattr(entity, key, value)
        entity.save(session=session)
        return entity

    @classmethod
    def delete(cls, entity, session=None):
        entity.delete(session=session)
