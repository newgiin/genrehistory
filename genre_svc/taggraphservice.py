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
from google.appengine.ext import ndb

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
BU_CACHE_NS = 'busy_users'

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
            tag_graph = user_entity.tag_graph

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

            self.response.write(json.dumps({'tags': tag_objs}))
        else:
            if models.BusyUser.get_by_id(user) is None:
                taskqueue.add(url='/worker',
                    params={'user': user})
                models.BusyUser(key=ndb.Key(models.BusyUser, user)).put()

            self.response.write(
                json.dumps({'status': 'Data still processing'}))



app = webapp2.WSGIApplication([
    ('/tag_graph_data', TagGraphService)
], debug=True)
