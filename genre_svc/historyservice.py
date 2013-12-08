import webapp2
import json
import logging
import models
import lastfm
import time
from genreworker import GenreWorker
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.api import memcache

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
BU_CACHE_NS = 'busy_users'

class HistoryService(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
        user = self.request.get('user')

        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return
        
        gwi_json = lfm_api.user_getweekintervals(user)
        if 'error' in gwi_json:
            self.response.write(json.dumps({'error': 'User does not exist.'}))
            return
        weeks = gwi_json['weeklychartlist']['chart']
        
        try:
            user_entity = models.User.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            self.response.write(
                json.dumps({'status': 'Exceeded GAE read quota. ' + 
                    'Yell at atnguyen4@gmail.com'}))
            return

        if (user_entity is not None 
                and user_entity.last_updated >= int(weeks[-1]['to'])):
            if self.request.get('max_tpw'):
                try:
                    # Trim number of tags per week
                    max_tpw = int(self.request.get('max_tpw'))
                    user_json = json.loads(user_entity.history) 
                    for week in user_json['weeks']:
                        week['tags'] = \
                            week['tags'][:min(len(week['tags']), max_tpw)]
                    self.response.write(json.dumps(user_json))
                except ValueError: # for invalid tpw values
                    self.response.write(user_entity.history)
            else:
                self.response.write(user_entity.history)
        else:
            if memcache.get(user, namespace=BU_CACHE_NS) is None:
                taskqueue.add(url='/worker',
                    name=user + str(int(time.time())),
                    params={'user': user})
                memcache.add(user, True, time=86400, namespace=BU_CACHE_NS)
            self.response.write(
                json.dumps({'status': 'Data still processing'}))



app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
