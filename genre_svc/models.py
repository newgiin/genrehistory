from google.appengine.ext import ndb

class User(ndb.Model):
    last_updated = ndb.IntegerProperty()
    data = ndb.JsonProperty()