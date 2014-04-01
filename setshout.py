import webapp2
import os
import json
from tag_svc import models
from google.appengine.ext import ndb

class ShoutSetter(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')
        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return
        else:
            user = user.lower()

        if set_shout(user):
            self.response.write(json.dumps({'shout': '1'}))
        else:
            self.response.write(json.dumps({'error': 'Not currently' +
                ' processing ' + user}))

app = webapp2.WSGIApplication([('/set_shout', ShoutSetter)], debug=True)

@ndb.transactional
def set_shout(user):
    bu_entity = models.BusyUser.get_by_id(user)
    if bu_entity is not None:
        if not bu_entity.shout:
            bu_entity.shout = True
            bu_entity.put()
        return True
    else:
        return False
