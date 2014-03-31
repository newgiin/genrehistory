from google.appengine.ext import ndb

class User(ndb.Model):
    last_updated = ndb.IntegerProperty()
    worker_count = ndb.IntegerProperty()
    shout = ndb.BooleanProperty()

class DataFragment(ndb.Model):
    start = ndb.IntegerProperty()
    end = ndb.IntegerProperty()
    size = ndb.IntegerProperty()

class TagHistory(DataFragment):
    tag_history = ndb.JsonProperty()

class TagGraph(DataFragment):
    tag_graph = ndb.PickleProperty()

class LastFmSession(ndb.Model):
    user = ndb.StringProperty()
    session_key = ndb.StringProperty()