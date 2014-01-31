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
from google.appengine.ext import ndb

lfm_api = lastfm.LastFm()

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
        else:
            user = user.lower()

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
            gwi_json['message'] = 'Service temporarily offline. ' + \
                                        'Please try again later.'
        except TemporaryError:
            gwi_json['error'] = 16
            gwi_json['message'] = 'There was a temporary error processing your ' + \
                                        'request. Please try again.'

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
            hist_entity = models.TagHistory.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            self.response.write(
                json.dumps({'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}))
            return

        if (hist_entity is not None 
                and hist_entity.last_updated >= int(weeks[-1]['to'])):
            self.response.write(json.dumps(hist_entity.tag_history))
        else:
            if models.BusyUser.get_by_id(user) is None:
                try:
                    taskqueue.add(url='/worker', 
                        name=user + str(int(time.time())),
                        params={'user': user})
                except taskqueue.InvalidTaskNameError:
                    taskqueue.add(url='/worker', params={'user': user})

                models.BusyUser(id=user, shout=False).put()

            self.response.headers['Cache-Control'] = \
                'no-transform,public,max-age=60'
            
            resp_data = {'status': 1, 'text': 'Data still processing'}
            if hist_entity is not None:
                resp_data['last_updated'] = hist_entity.last_updated
                
            self.response.write(json.dumps(resp_data))



app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
