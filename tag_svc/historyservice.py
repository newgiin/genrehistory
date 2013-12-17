import webapp2
import json
import logging
import models
import lastfm
from lastfm import ExceedRateLimitError, SuspendedAPIKeyError, \
                    ServiceOfflineError, TemporaryError
import time
from tagworker import TagWorker
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.api import memcache
from google.appengine.ext import ndb

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
BU_CACHE_NS = 'busy_users'

class HistoryService(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Cache-Control'] = \
            'no-transform,public,max-age=300,s-maxage=900'
        user = self.request.get('user')

        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return

        gwi_json = {}

        try:
            gwi_json = lfm_api.user_getweekintervals(user)
        except ExceedRateLimitError:
            gwi_json['error'] = 29
            gwi_json['message'] = 'Rate limit exceeded'
        except SuspendedAPIKeyError:
            gwi_json['error'] = 26
            gwi_json['message'] = 'Suspended API key'
        except ServiceOfflineError:
            gwi_json['error'] = 11
            gwi_json['message'] = 'Service temporarily offline. \
                                        Please try again later.'
        except TemporaryError:
            gwi_json['error'] = 16
            gwi_json['message'] = 'There was a temporary error processing your \
                                        request. Please try again'

        if 'error' in gwi_json:
            error_msg = ''
            if int(gwi_json['error']) == 6:
                error_msg = 'User does not exist'
            else:
                error_msg = 'Last.fm error: ' + gwi_json['message']

            self.response.write(json.dumps({'error': error_msg}))
            return

        weeks = gwi_json['weeklychartlist']['chart']
        
        try:
            user_entity = models.User.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            self.response.write(
                json.dumps({'error': 'AppEngine error. Go tell \
                    atnguyen4@gmail.com to buy more Google resources.'}))
            return

        if (user_entity is not None 
                and user_entity.last_updated >= int(weeks[-1]['to'])):
            self.response.write(user_entity.history)
        else:
            if models.BusyUser.get_by_id(user) is None:
                try:
                    taskqueue.add(url='/worker', 
                        name=user + str(int(time.time())),
                        params={'user': user})
                except taskqueue.InvalidTaskNameError:
                    taskqueue.add(url='/worker', params={'user': user})

                models.BusyUser(key=ndb.Key(models.BusyUser, user)).put()

            self.response.write(
                json.dumps({'status': 'Data still processing'}))



app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
