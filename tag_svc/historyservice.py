import webapp2
import json
import logging
from models import User, TagHistory
import lastfm
import time
from config import DS_VERSION
from tagservice import TagService
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.api.urlfetch_errors import DeadlineExceededError

class HistoryService(TagService):
    def build_response(self, user, request):
        resp = {'user': user, 'weeks':[]}

        user_entity = User.get_by_id(user, namespace=DS_VERSION)
        qry = TagHistory.query(ancestor=user_entity.key,
            namespace=DS_VERSION).order(
            TagHistory.start)

        for hist_frag in qry.fetch():
            resp['weeks'] += hist_frag.tag_history['weeks']

        return resp


app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
