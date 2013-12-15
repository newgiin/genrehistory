from google.appengine.ext import ndb

class User(ndb.Model):
    last_updated = ndb.IntegerProperty()
    history = ndb.JsonProperty()
    tag_graph = ndb.PickleProperty()

class BusyUser(ndb.Model):
    pass