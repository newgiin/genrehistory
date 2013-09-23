#!/usr/bin/python
import webapp2
import lastfm
import json
import logging
from google.appengine.api import memcache, taskqueue
from google.appengine.ext import ndb, db
from time import sleep

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
CACHE_PRD = 86400 # 1 day
TAGS_PER_ARTIST = 3
PLAY_THRESHOLD = 5

def get_weeklyartists(user, start, end):
    weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
    artists = {}
    if 'error' in weekly_artists:
        logging.error('Error getting top artists for %s in week %s-%s' % 
            (user, start, end))
    elif 'artist' in weekly_artists['weeklyartistchart']:
        if isinstance(
                weekly_artists['weeklyartistchart']['artist'], list
            ):
            artists = weekly_artists['weeklyartistchart']['artist']
        else:
            artist = [weekly_artists['weeklyartistchart']['artist']]

    return artists

def get_artisttags(artist, mbid, limit=5):
    top_tags = memcache.get(artist)
    if top_tags is None:
        top_tags = []
        toptags_json = lfm_api.artist_gettoptags(artist, 
            mbid)

        if 'error' in toptags_json :
            logging.error('Error getting tag data for %s[%s]' 
                % (artist, mbid))
        elif 'tag' in toptags_json['toptags']:
            tags = toptags_json['toptags']['tag']
            if isinstance(tags, list):
                top_tags = [
                    e['name'] for e in 
                    tags[0:min(limit, len(tags))]
                ]
            else:
                top_tags = [tags['name']]

        memcache.add(artist, top_tags, CACHE_PRD)
        sleep(.2)

    return top_tags

class User(ndb.Model):
    name = ndb.StringProperty()
    last_updated = ndb.IntegerProperty()
    data = ndb.JsonProperty()
    
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
        
        user_entity = User.get_by_id(user)
        if (user_entity is not None 
                and user_entity.last_updated >= int(weeks[-1]['to'])):
            if self.request.get('max_tpw'):
                try:
                    # Trim number of genres per week
                    max_tpw = int(self.request.get('max_tpw'))
                    user_json = json.loads(user_entity.data) 
                    for week in user_json['weeks']:
                        week['tags'] = \
                            week['tags'][:min(len(week['tags']), max_tpw)]
                    self.response.write(json.dumps(user_json))
                except ValueError:
                    self.reponse.write(user_entity.data)
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

class GenreWorker(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')

        def txn():
            weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']
            user_entity = User.get_by_id(user)
            result = {'user': user, 'weeks': []}
            date_floor = None

            if user_entity is None:
                user_data = lfm_api.user_getinfo(user)['user']
                date_floor = int(user_data['registered']['unixtime'])
            else:
                date_floor = user_entity.last_updated
            
            for week in reversed(weeks):
                if int(week['to']) <= date_floor:
                    break
                    
                week_elem = {'from': week['from'], 
                    'to': week['to'], 'tags':[]}
                tags = {}
                artists = get_weeklyartists(user, week['from'], week['to'])

                for artist in artists:
                    artist_name = artist['name']

                    top_tags = get_artisttags(artist_name, artist['mbid'],
                       TAGS_PER_ARTIST)

                    for tag in top_tags:
                        if tag in tags:
                            tags[tag] += int(artist['playcount'])
                        else:
                            tags[tag] = int(artist['playcount'])

                week_elem['tags'] = [{'tag': k, 'plays': v} \
                                        for k,v in tags.items() \
                                        if v > PLAY_THRESHOLD]
                week_elem['tags'].sort(key=lambda e: e['plays'], reverse=True)

                result['weeks'].append(week_elem)
                sleep(.2)
            
            if user_entity is not None:
                # prepend new history to old history
                old_json = json.loads(user_entity.data)
                result['weeks'] += old_json['weeks']
                
            json_result = json.dumps(result, allow_nan=False)

            user_entity = User(key=ndb.Key(User, user), 
                name=user, 
                last_updated=int(weeks[-1]['to']),
                data=json_result)

            user_entity.put()
            
        db.run_in_transaction(txn)

app = webapp2.WSGIApplication([
    ('/data', GenreService),
    ('/worker', GenreWorker)
], debug=True)
