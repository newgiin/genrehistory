import webapp2
import os
import json
from tag_svc import models

class ShoutSetter(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')
        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return
        else:
            user = user.lower()

        busy_user = models.BusyUser.get_by_id(user)
        if busy_user is not None:
            if not busy_user.shout:
                busy_user.shout = True
                busy_user.put()
            self.response.write(json.dumps({'shout': '1'}))
        else:
            self.response.write(json.dumps({'error': 'Not currently' +
                ' processing ' + user}))

app = webapp2.WSGIApplication([('/set_shout', ShoutSetter)], debug=True)
