import webapp2
import json
import logging
import models
import lastfm
import time
from tagworker import TagWorker
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import ndb
from google.appengine.api.urlfetch_errors import DeadlineExceededError


lfm_api = lastfm.LastFm()

class TagGraphService(webapp2.RequestHandler):
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

        try:
            graph_entity = models.TagGraph.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            self.response.write(
                json.dumps({'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}))
            return

        if (graph_entity is not None
                and graph_entity.last_updated >= int(weeks[-1]['to'])):
            tag_graph = graph_entity.tag_graph

            tag_objs = [{'tag': tag, 'plays': v['plays'], 'adj': list(v['adj'])}
                            for tag, v in tag_graph.iteritems()]
            tag_objs.sort(key=lambda e: e['plays'], reverse=True)

            if self.request.get('tp') and self.request.get('tp').isdigit():
                top_percent = int(self.request.get('tp')) / 100.0
                tag_objs = tag_objs[:int(len(tag_objs) * top_percent)]
                top_tags = set([obj['tag'] for obj in tag_objs])

                for obj in tag_objs:
                    adj = [syn_tag for syn_tag in obj['adj']
                            if syn_tag in top_tags]

                    obj['adj'] = adj

            self.response.write(json.dumps({'user': user, 'tags': tag_objs}))
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
            if graph_entity is not None:
                resp_data['last_updated'] = graph_entity.last_updated

            user_data = lfm_api.user_getinfo(user)['user']
            if int(weeks[-1]['to']) <= int(user_data['registered']['unixtime']):
                resp_data = {'error': 'Your account is too new for Last.fm to have data.'}

            self.response.write(json.dumps(resp_data))



app = webapp2.WSGIApplication([
    ('/tag_graph_data', TagGraphService)
], debug=True)
