import webapp2
import logging
from models import User
from config import DS_VERSION
from tagservice import TagService

class UserFragmentService(TagService):
    def build_response(self, user, request):
        user_entity = User.get_by_id(user, namespace=DS_VERSION)

        frags = user_entity.fragments
        frags.sort(key=lambda x: x['start'])
        return {'user': user, 'fragments': frags}


app = webapp2.WSGIApplication([
    ('/fragment_chart', UserFragmentService)
], debug=True)
