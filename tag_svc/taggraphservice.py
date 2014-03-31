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

    def build_response(self, user, request):
        tag_graph = {}

        try:
            user_entity = models.User.get_by_id(user)
            qry = models.TagGraph.query(ancestor=user_entity.key).order(
                models.TagGraph.start)
            for graph_frag in qry.fetch():
                # merge graph to aggregate graph
                sub_graph = graph_frag.tag_graph
                for tag in sub_graph:
                    if tag in tag_graph:
                        tag_graph[tag]['plays'] += sub_graph[tag]['plays']
                        tag_graph[tag]['adj'] = tag_graph[tag]['adj'].union(
                            sub_graph[tag]['adj'])
                    else:
                        tag_graph[tag] = sub_graph[tag]
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            return {'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}

        # format JSON
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

        return {'user': user, 'tags':tag_objs}



        try:
            graph_entity = models.TagGraph.get_by_id(user)
        except apiproxy_errors.OverQuotaError as e:
            logging.error(e)
            return {'error': 'AppEngine error. Go tell ' + \
                    'atnguyen4@gmail.com to buy more Google resources.'}

        if graph_entity is not None:
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

app = webapp2.WSGIApplication([
    ('/tag_graph_data', TagGraphService)
], debug=True)
