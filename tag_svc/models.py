from google.appengine.ext import ndb

class TagHistory(ndb.Model):
    last_updated = ndb.IntegerProperty()
    history = ndb.JsonProperty()

class TagGraph(ndb.Model):
    last_updated = ndb.IntegerProperty()
    tag_graph = ndb.PickleProperty()

class BusyUser(ndb.Model):
    pass