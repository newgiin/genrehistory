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
    def build_response(self, user, request):
        resp = {'user': user, 'weeks':[]}
        try:
            user_entity = models.User.get_by_id(user)
            qry = models.TagHistory.query(ancestor=user_entity.key).order(
                models.TagHistory.start)
            for hist_frag in qry.fetch():
                resp['weeks'] += hist_frag.tag_history['weeks']
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            return {'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}

        return resp


app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
