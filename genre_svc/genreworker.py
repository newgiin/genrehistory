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
AT_CACHE_NS = 'artist_tags'
TAGS_PER_ARTIST = 1
PLAY_THRESHOLD = 5
NUM_TOP_ARTISTS = 3

def _get_weeklyartists(user, start, end):
    weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
    artists = {}
    if 'error' in weekly_artists:
        logging.warning('Error getting top artists for %s in week %s-%s: %s' % 
            (user, start, end, weekly_artists['error']))
    elif 'artist' in weekly_artists['weeklyartistchart']:
        if isinstance(
                weekly_artists['weeklyartistchart']['artist'], list
            ):
            artists = weekly_artists['weeklyartistchart']['artist']
        else:
            artist = [weekly_artists['weeklyartistchart']['artist']]

    return artists

def _get_artisttags(artist, mbid, limit=5):
    top_tags = []
    toptags_json = lfm_api.artist_gettoptags(artist, 
        mbid)

    if 'error' in toptags_json :
        logging.warning('Error getting tag data for %s[%s]: %s' 
            % (artist, mbid, toptags_json['error']))
    elif 'tag' in toptags_json['toptags']:
        tags = toptags_json['toptags']['tag']
        if isinstance(tags, list):
            top_tags = [
                e['name'] for e in 
                tags[0:limit]
            ]
        else:
            top_tags = [tags['name']]

    return top_tags

class _Quota:
    period = 300
    req_limit = 1500

    @staticmethod
    def run_with_quota(quota_state, f, reqs_used=1):
        now = time.time()
        if (quota_state.num_reqs >= _Quota.req_limit 
                or now >= quota_state.next_interval):
            if quota_state.num_reqs >= _Quota.req_limit:
                logging.debug('Reached request limit, waiting: ' + 
                    str(quota_state.next_interval - now) + 'seconds.')
                time.sleep(quota_state.next_interval - now)    
            quota_state.num_reqs = 0
            quota_state.next_interval = time.time() + _Quota.period

        quota_state.num_reqs += reqs_used
        return f()

class _QuotaState:
    def __init__(self, num_reqs, next_interval):
        self.num_reqs = num_reqs
        self.next_interval = next_interval

class GenreWorker(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')

        def txn():
            start = time.time()
            quota_state = _QuotaState(0, time.time() + _Quota.period)

            user_entity = models.User.get_by_id(user)
            result = {'user': user, 'weeks': []}
            date_floor = None

            if user_entity is None:
                user_data = lfm_api.user_getinfo(user)['user']
                date_floor = int(user_data['registered']['unixtime'])
            else:
                date_floor = user_entity.last_updated
            
            weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']

            for week in reversed(weeks):
                if int(week['to']) <= date_floor:
                    break
                    
                week_elem = {'from': week['from'], 
                    'to': week['to'], 'tags':[]}
                tags = {}
                top_artists = {}

                artists = _Quota.run_with_quota(quota_state,
                    lambda: _get_weeklyartists(user, week['from'], week['to']))

                for artist in artists:
                    artist_name = artist['name']

                    artist_tags = memcache.get(artist_name, 
                        namespace=AT_CACHE_NS)
                    if artist_tags is None:
                        artist_tags = _Quota.run_with_quota(quota_state,
                            lambda: _get_artisttags(artist_name, artist['mbid'], 
                                TAGS_PER_ARTIST))
                        memcache.add(artist_name, artist_tags, CACHE_PRD,
                            namespace=AT_CACHE_NS)

                    for tag in artist_tags:
                        if tag in tags:
                            tags[tag] += int(artist['playcount'])
                            if (len(top_artists[tag]) < NUM_TOP_ARTISTS):
                                top_artists[tag].append(artist_name)
                        else:
                            tags[tag] = int(artist['playcount'])
                            top_artists[tag] = [artist_name]

                week_elem['tags'] = [{'tag': k, 'plays': v, 
                                        'artists': top_artists[k]} \
                                        for k,v in tags.iteritems() \
                                        if v > PLAY_THRESHOLD]
                week_elem['tags'].sort(key=lambda e: e['plays'], reverse=True)

                result['weeks'].append(week_elem)
            
            if user_entity is not None:
                # prepend new history to old history
                old_json = json.loads(user_entity.data)
                result['weeks'] += old_json['weeks']
                
            json_result = json.dumps(result, allow_nan=False)

            user_entity = models.User(key=ndb.Key(models.User, user), 
                last_updated=int(weeks[-1]['to']),
                data=json_result)

            user_entity.put()
            logging.info(user + ' took: ' + str(time.time() - start) + ' seconds.')
            
        db.run_in_transaction(txn)