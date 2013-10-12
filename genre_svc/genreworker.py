import webapp2
import json
import logging
import lastfm
import models
from google.appengine.ext import ndb, db
from google.appengine.api import memcache
import time

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
CACHE_PRD = 86400 # 1 day
TAGS_PER_ARTIST = 1
PLAY_THRESHOLD = 5

def _get_weeklyartists(user, start, end):
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

def _get_artisttags(artist, mbid, limit=5):
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
        time.sleep(.2)

    return top_tags

class GenreWorker(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')

        def txn():
            start = time.time()
            weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']
            user_entity = models.User.get_by_id(user)
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
                artists = _get_weeklyartists(user, week['from'], week['to'])

                for artist in artists:
                    artist_name = artist['name']

                    top_tags = _get_artisttags(artist_name, artist['mbid'],
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
                time.sleep(.2)
            
            if user_entity is not None:
                # prepend new history to old history
                old_json = json.loads(user_entity.data)
                result['weeks'] += old_json['weeks']
                
            json_result = json.dumps(result, allow_nan=False)

            user_entity = models.User(key=ndb.Key(models.User, user), 
                last_updated=int(weeks[-1]['to']),
                data=json_result)

            user_entity.put()
            logging.debug(user + ' took: ' + str(time.time() - start) + ' seconds.')
            
        db.run_in_transaction(txn)