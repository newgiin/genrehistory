#!/usr/bin/python
import webapp2
import lastfm
import json
import logging
from google.appengine.api import memcache
from google.appengine.ext import ndb
from time import sleep

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')

class User(ndb.Model):
    name = ndb.StringProperty()
    last_updated = ndb.IntegerProperty()
    data = ndb.JsonProperty()
    
class GenreService(webapp2.RequestHandler):
    TAGS_PER_ARTIST = 3
    CACHE_PRD = 86400 # 1 day
    PLAY_THRESHOLD = 2

    def get_weeklyartists(self, user, start, end):
        weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
        artists = {}
        if 'error' in weekly_artists:
            logging.error('Error getting top artists for %s in week %s-%s' % 
                (user, start, end))
        elif 'artist' in weekly_artists['weeklyartistchart']:
            artists = weekly_artists['weeklyartistchart']['artist']
        return artists

    def get_artisttags(self, artist, mbid, limit=5):
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

            memcache.add(artist, top_tags, self.CACHE_PRD)
            sleep(.2)

        return top_tags

    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
        user = self.request.get('user')
        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return
            
        weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']
        
        user_entity = User.get_by_id(user)
        if (user_entity is not None 
                and user_entity.last_updated >= int(weeks[-1]['to'])):
            logging.debug('Got from datastore!')
            self.response.write(user_entity.data)
        else:
            result = { 'weeks': [] }
            date_floor = None
            if user_entity is None:
                user_data = lfm_api.user_getinfo(user)['user']
                date_floor = int(user_data['registered']['unixtime'])
                result['user'] = user
            else:
                date_floor = user_entity.last_updated
            
            for week in reversed(weeks):
                if int(week['to']) <= date_floor:
                    break
                    
                week_elem = {'from': week['from'], 
                    'to': week['to'], 'tags':{}}

                artists = self.get_weeklyartists(user, week['from'], week['to'])

                for artist in artists:
                    artist_name = artist['name']

                    top_tags = self.get_artisttags(artist_name, artist['mbid'],
                       self.TAGS_PER_ARTIST)

                    for tag in top_tags:
                        if tag in week_elem['tags']:
                            week_elem['tags'][tag] += int(artist['playcount'])
                        else:
                            week_elem['tags'][tag] = int(artist['playcount'])

                week_elem['tags'] = \
                    {k:v for k,v in week_elem['tags'].items() 
                        if v > self.PLAY_THRESHOLD}

                result['weeks'].append(week_elem)
                #break
                sleep(.2)
            
            if user_entity is not None:
                # prepend new history to old history
                old_json = json.loads(user_entity.data)
                old_json['weeks'] = result['weeks'] + old_json['weeks']
                result = old_json
                
            json_result = json.dumps(result, allow_nan=False)
            # Store user in database
            user_entity = User(key=ndb.Key(User, user), 
                name=user, 
                last_updated=int(weeks[-1]['to']),
                data=json_result)
            user_entity.put()
            
            self.response.write(json_result)

application = webapp2.WSGIApplication([
    ('/', GenreService),
], debug=True)