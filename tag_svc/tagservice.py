import webapp2
import json
import logging
import models
import lastfm
import time
import webapp2
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import ndb
from google.appengine.api.urlfetch_errors import DeadlineExceededError

lfm_api = lastfm.LastFm()

"""
Boilerplate for generating tag data response
"""
class TagService(webapp2.RequestHandler):

    """
    Meant to be overriden by subclass.
    Returns JSON response in dict format if data in datastore is
    ready and up-to-date, otherwise returns None if a tag worker
    process should be started to update the data.
    """
    def build_response(self, user, curr_week):
        raise NotImplementedError

    """
    Return integer UNIX timestamp of when the data
    for this user was last updated.
    """
    def get_last_updated(self, user):
        raise NotImplementedError

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
        except lastfm.ExceedRateLimitError:
            gwi_json['error'] = 29
            gwi_json['message'] = 'Rate limit exceeded'
        except lastfm.SuspendedAPIKeyError:
            gwi_json['error'] = 26
            gwi_json['message'] = 'Suspended API key'
        except lastfm.ServiceOfflineError:
            gwi_json['error'] = 11
            gwi_json['message'] = 'Service temporarily offline. ' + \
                                        'Please try again later.'
        except lastfm.TemporaryError:
            gwi_json['error'] = 16
            gwi_json['message'] = 'There was a temporary error processing your ' + \
                                        'request. Please try again.'
        except DeadlineExceededError:
            self.response.write(json.dumps(
                {'error': 'Could not reach Last.fm. Please try again later.'}))
            return


        if 'error' in gwi_json:
            error_msg = ''
            if int(gwi_json['error']) == 6:
                error_msg = 'User does not exist'
            else:
                error_msg = 'Last.fm error: ' + gwi_json['message']

            self.response.write(json.dumps({'error': error_msg}))
            return

        weeks = gwi_json['weeklychartlist']['chart']

        tag_data = self.build_response(user, int(weeks[-1]['to']), self.request)

        if tag_data is not None:
            self.response.write(json.dumps(tag_data))
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
                'no-transform,public,max-age=30'

            resp_data = {'status': 1, 'text': 'Data still processing'}

            last_updated = self.get_last_updated(user)
            if last_updated is not None:
                resp_data['last_updated'] = last_updated

            user_data = lfm_api.user_getinfo(user)['user']
            if int(weeks[-1]['to']) <= int(user_data['registered']['unixtime']):
                resp_data = {'error': 'Your account is too new for Last.fm to have data.'}

            self.response.write(json.dumps(resp_data))
