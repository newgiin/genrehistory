import webapp2
import json
import logging
import models
import lastfm
from genreworker import GenreWorker
from google.appengine.api import taskqueue

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
    
class GenreService(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
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
        
        user_entity = models.User.get_by_id(user)
        if (user_entity is not None 
                and user_entity.last_updated >= int(weeks[-1]['to'])):
            if self.request.get('max_tpw'):
                try:
                    # Trim number of tags per week
                    max_tpw = int(self.request.get('max_tpw'))
                    user_json = json.loads(user_entity.data) 
                    for week in user_json['weeks']:
                        week['tags'] = \
                            week['tags'][:min(len(week['tags']), max_tpw)]
                    self.response.write(json.dumps(user_json))
                except ValueError:
                    self.response.write(user_entity.data)
            else:
                self.response.write(user_entity.data)
        else:
            # TODO Check if task already in queue
            try:
                taskqueue.add(url='/worker', 
                    name=user + '-' + weeks[-1]['to'], 
                    params={'user': user})
            except taskqueue.TaskAlreadyExistsError:
                pass
            self.response.write(
                json.dumps({'status': 'Data still processing'}))



app = webapp2.WSGIApplication([
    ('/data', GenreService),
    ('/worker', GenreWorker)
], debug=True)
