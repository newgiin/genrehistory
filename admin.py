import webapp2
import os
import jinja2
from tag_svc import config
from tag_svc import models
from tag_svc.lastfm import LastFm

from google.appengine.ext import ndb


JINJA_ENVIRONMENT = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
        extensions=['jinja2.ext.autoescape'])

class MainPage(webapp2.RequestHandler):
    def get(self):
        template_values = {'lfm_key': LastFm.API_KEY,
            'cb_url': self.request.path_url}

        if 'token' in self.request.params:
            token = self.request.params['token']
            lfm_api = LastFm()
            resp = lfm_api.auth_getsession(token)

            if 'error' in resp:
                template_values['auth_error'] = resp['error']
            else:
                template_values['auth_user'] = resp['session']['name']
                template_values['auth_session_key'] = resp['session']['key']
                session_entity = models.LastFmSession(id=LastFm.API_KEY,
                    user=resp['session']['name'],
                    session_key=resp['session']['key'], namespace='admin')
                session_entity.put()
        else:
            lfm_session = models.LastFmSession.get_by_id(LastFm.API_KEY,
                                                         namespace='admin')
            if lfm_session is not None:
                template_values['auth_user'] = lfm_session.user
                template_values['auth_session_key'] = lfm_session.session_key

        template = JINJA_ENVIRONMENT.get_template(
            'templates/admin.html')
        self.response.write(template.render(template_values))

app = webapp2.WSGIApplication([('/admin', MainPage)], debug=True)


class DeleteUserHandler(webapp2.RequestHandler):
    def post(self):
        if 'user' in self.request.params:
            user = self.request.params['user']
            user_entity = models.User.get_by_id(user,
                                                namespace=config.DS_VERSION)
            if user_entity:
                query = ndb.Query(ancestor=user_entity.key).iter(keys_only=True)
                ndb.delete_multi(query)
                self.response.write('Successfully delete user %s' % user)
            else:
                self.response.write('User %s does not exist.' % user)
        else:
            self.response.write('User param missing.')
        self.response.write('<br/><a href="%s">Back</a>' % self.request.referer)



delete_user = webapp2.WSGIApplication([('/delete_user', DeleteUserHandler)],
                                      debug=True)