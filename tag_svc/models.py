from google.appengine.ext import ndb

class TagHistory(ndb.Model):
    last_updated = ndb.IntegerProperty()
    tag_history = ndb.JsonProperty()

class TagGraph(ndb.Model):
    last_updated = ndb.IntegerProperty()
    tag_graph = ndb.PickleProperty()

class BusyUser(ndb.Model):
    pass

class LastFmSession(ndb.Model):
    user = ndb.StringProperty()
    session_key = ndb.StringProperty()