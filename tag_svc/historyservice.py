import webapp2
import logging
from models import User, TagHistory
from config import DS_VERSION
from tagservice import TagService

class HistoryService(TagService):
    def build_response(self, user, request):
        resp = {'user': user, 'weeks':[]}

        user_entity = User.get_by_id(user, namespace=DS_VERSION)
        qry = TagHistory.query(ancestor=user_entity.key,
            namespace=DS_VERSION).order(
            TagHistory.start)

        for hist_frag in qry.fetch():
            resp['weeks'] += hist_frag.tag_history['weeks']

        return resp


app = webapp2.WSGIApplication([
    ('/history_data', HistoryService)
], debug=True)
