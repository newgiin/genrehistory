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


lfm_api = lastfm.LastFm()

class TagGraphService(TagService):

    def build_response(self, user, curr_week, request):
        try:
            graph_entity = models.TagGraph.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            return {'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}

        if (graph_entity is not None
                and graph_entity.last_updated >= curr_week):
            tag_graph = graph_entity.tag_graph

            tag_objs = [{'tag': tag, 'plays': v['plays'], 'adj': list(v['adj'])}
                            for tag, v in tag_graph.iteritems()]
            tag_objs.sort(key=lambda e: e['plays'], reverse=True)

            if request.get('tp') and request.get('tp').isdigit():
                top_percent = int(request.get('tp')) / 100.0
                tag_objs = tag_objs[:int(len(tag_objs) * top_percent)]
                top_tags = set([obj['tag'] for obj in tag_objs])

                for obj in tag_objs:
                    adj = [syn_tag for syn_tag in obj['adj']
                            if syn_tag in top_tags]

                    obj['adj'] = adj

            return {'user': user, 'tags': tag_objs}
        return None

    def get_last_updated(self, user):
        graph_entity = models.TagGraph.get_by_id(user)
        if graph_entity is not None:
            return graph_entity.last_updated
        return None

app = webapp2.WSGIApplication([
    ('/tag_graph_data', TagGraphService)
], debug=True)
