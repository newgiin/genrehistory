import webapp2
import logging
from models import User, TagGraph
from config import DS_VERSION
from tagservice import TagService


class TagGraphService(TagService):

    def build_response(self, user, request):
        tag_graph = {}
        user_entity = User.get_by_id(user, namespace=DS_VERSION)
        start = end = -1

        qry = TagGraph.query(ancestor=user_entity.key,
            namespace=DS_VERSION).order(
            TagGraph.start)

        # NOTE: 'from'/'to' are not exactly analagous to 'start'/'end'.
        # 'from' and 'to' both correspond to fragment 'start' properties
        # (as opposed to 'to' corresponsing to an 'end' value).
        # Since filter properties must be same as order property,
        # we filter only by fragment 'start' dates.
        if request.get('from') and request.get('from').isdigit():
            qry = qry.filter(TagGraph.start >= int(request.get('from')))

        if request.get('to') and request.get('to').isdigit():
            qry = qry.filter(TagGraph.start <= int(request.get('to')))

        fetch_results = qry.fetch()

        for graph_entity in fetch_results:
            # merge graph to aggregate graph
            sub_graph = graph_entity.tag_graph

            for tag in sub_graph:
                if tag in tag_graph:
                    tag_graph[tag]['plays'] += sub_graph[tag]['plays']
                    tag_graph[tag]['adj'] = tag_graph[tag]['adj'].union(
                        sub_graph[tag]['adj'])
                else:
                    tag_graph[tag] = sub_graph[tag]

        if fetch_results:
            start = fetch_results[0].start
            end = fetch_results[-1].end

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

        return {'user': user, 'tags': tag_objs, 'start': start, 'end': end}


app = webapp2.WSGIApplication([
    ('/tag_graph_data', TagGraphService)
], debug=True)
