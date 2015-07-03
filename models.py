from google.appengine.ext import ndb

class _IntValueStore(ndb.Model):
    _UNIQUE_ID = 1
    value = ndb.IntegerProperty(required=True)

    @classmethod
    @ndb.tasklet
    def get(cls, default=None):
        result = yield ndb.Key(cls, _IntValueStore._UNIQUE_ID).get_async()
        result = default if result is None else result.value
        raise ndb.Return(result)

    @classmethod
    @ndb.tasklet
    def set(cls, int_value):
        yield cls(id=_IntValueStore._UNIQUE_ID, value=int_value).put_async()

class MaxItemId(_IntValueStore):
    pass

class LastRetrievedId(_IntValueStore):
    pass

class HNEntry(ndb.Model):
    retrieved_at = ndb.DateTimeProperty(auto_now_add=True)
    body = ndb.JsonProperty(compressed=True)
