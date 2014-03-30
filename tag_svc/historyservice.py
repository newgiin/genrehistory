import webapp2
import json
import logging
import models
import lastfm
import time
from tagservice import TagService
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import ndb
from google.appengine.api.urlfetch_errors import DeadlineExceededError

class HistoryService(TagService):
    def build_response(self, user, curr_week, request):
        try:
            hist_entity = models.TagHistory.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            return {'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}

        if (hist_entity is not None
                and hist_entity.last_updated >= curr_week):
            return hist_entity.tag_history
        return None

    def get_last_updated(self, user):
        hist_entity = models.TagHistory.get_by_id(user)
        if hist_entity is not None:
            return hist_entity.last_updated
        return None


app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
