import webapp2
import json
import logging
import lastfm
import models
from google.appengine.ext import ndb, db
from google.appengine.api import memcache
import time

lfm_api = lastfm.LastFm('24836bd9d7043e3c0bc65aa801ba8821')
CACHE_PRD = 604800 # 1 week
AT_CACHE_NS = 'artist_tags'
TAGS_PER_ARTIST = 3
PLAY_THRESHOLD = 6
NUM_TOP_ARTISTS = 3
MAX_TPW = 10 # tags per week

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
    
    if 'error' in toptags_json:
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
        """
        Call 'f()' returning the result if the current number of requests 
        for this period is not over the request limit. Otherwise, sleep until
        the next_interval, reset the current number of requests to zero,
        and then call 'f()', incrementing quota_state.num_reqs by 'reqs_used'.
        """
        if quota_state.num_reqs >= _Quota.req_limit:
            now = time.time()
            logging.debug('Reached request limit, waiting: ' + 
                str(quota_state.next_interval - now) + 'seconds.')
            try:
                # To ensure next time.time() >= next_interval,
                # add half a second due to potential imprecisions
                # with time.sleep()
                time.sleep(quota_state.next_interval + 0.5 - now)    
            except IOError:
                # In the rare case request limit is hit
                # after next_interval is reached
                pass 

        if time.time() >= quota_state.next_interval:
            quota_state.num_reqs = 0
            quota_state.next_interval = time.time() + _Quota.period

        quota_state.num_reqs += reqs_used
        return f()

class _QuotaState:
    def __init__(self, num_reqs, next_interval):
        self.num_reqs = num_reqs
        self.next_interval = next_interval

def _process_user(user):
    start = time.time()
    quota_state = _QuotaState(0, time.time() + _Quota.period)

    hist_entity = models.TagHistory.get_by_id(user)
    graph_entity = models.TagGraph.get_by_id(user)

    tag_history = {'user': user, 'weeks': []}
    tag_graph = {} # { tag_name: { plays: num_plays, adj: set_of_related } }
    date_floor = None
    deadline_exceeded = False
    
    if hist_entity is None:
        user_data = lfm_api.user_getinfo(user)['user']
        date_floor = int(user_data['registered']['unixtime'])
    else:
        date_floor = hist_entity.last_updated
        tag_graph = graph_entity.tag_graph

    weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']

    try:

        for week in weeks:
            # We continue through a lot of useless weeks because we're populating
            # from oldest to newest, so that if we have to catch DeadlineExceededError
            # we can just write current data to datastore and continue
            # as from where we left off using same logic as handling returning user.
            if int(week['to']) <= date_floor:
                continue

            week_elem = {'from': week['from'], 
                'to': week['to'], 'tags':[]}
            tags = {}
            top_artists = {}

            artists = _Quota.run_with_quota(quota_state,
                lambda: _get_weeklyartists(user, week['from'], week['to']))

            for artist in artists:
                artist_name = artist['name']
                artist_plays = int(artist['playcount'])
                artist_tags = memcache.get(artist_name, 
                    namespace=AT_CACHE_NS)
                
                if artist_tags is None:
                    artist_tags = _Quota.run_with_quota(quota_state,
                        lambda: _get_artisttags(artist_name, artist['mbid'], 
                            TAGS_PER_ARTIST))
                    memcache.add(artist_name, artist_tags, CACHE_PRD,
                        namespace=AT_CACHE_NS)

                if artist_tags:
                    tag = artist_tags[0]
                    if tag in tags:
                        tags[tag] += artist_plays
                        if (len(top_artists[tag]) < NUM_TOP_ARTISTS):
                            top_artists[tag].append(artist_name)
                    else:
                        tags[tag] = artist_plays
                        top_artists[tag] = [artist_name]

                for tag in artist_tags:
                    if tag in tag_graph:
                        tag_graph[tag]['plays'] += artist_plays
                    else:
                        tag_graph[tag] = {'plays': artist_plays, \
                                                'adj': set()}

                    for syn_tag in artist_tags:
                        if syn_tag != tag:
                            tag_graph[tag]['adj'].add(syn_tag)

            week_elem['tags'] = [{'tag': k, 'plays': v, 
                                    'artists': top_artists[k]} \
                                    for k,v in tags.iteritems() \
                                    if v >= PLAY_THRESHOLD]
                                    
            week_elem['tags'].sort(key=lambda e: e['plays'], reverse=True)
            week_elem['tags'] = week_elem['tags'][:MAX_TPW]
            
            tag_history['weeks'].append(week_elem)

        # filter out tags from graph with plays below theshold
        lil_tags = set([tag for tag in tag_graph if 
                        tag_graph[tag]['plays'] < PLAY_THRESHOLD])
        tag_graph = {tag:v for tag,v in tag_graph.iteritems() 
            if tag_graph[tag]['plays'] >= PLAY_THRESHOLD}

        for tag in tag_graph:
            tag_graph[tag]['adj'] = {tag for tag in 
                                        tag_graph[tag]['adj'] if
                                        tag not in lil_tags}

    except google.appengine.runtime.DeadlineExceededError:
        # For the very small chance that it timed out after appending all the weeks, but
        # before we filtered out small tags from tag_graph, we may have
        # more tags in tag_graph than desired until next time we add a week for this
        # user.
        logging.error('Caught DeadlineExceededError while processing ' + user)
        deadline_exceeded = True

    if hist_entity is not None:
        # prepend new history to old history
        old_json = json.loads(hist_entity.history)
        tag_history['weeks'] = old_json['weeks'] + tag_history['weeks']
        
    json_result = json.dumps(tag_history, allow_nan=False)

    hist_entity = models.TagHistory(key=ndb.Key(models.TagHistory, user), 
        last_updated=int(tag_history['weeks'][-1]['to']),
        history=json_result)

    hist_entity.put()

    graph_entity = models.TagGraph(key=ndb.Key(models.TagGraph, user), 
        last_updated=int(tag_history['weeks'][-1]['to']),
        tag_graph=tag_graph)

    graph_entity.put()

    if deadline_exceeded:
        # send another request that will finish it
        try:
            taskqueue.add(url='/worker', 
                name=user + str(int(time.time())),
                params={'user': user})
        except taskqueue.InvalidTaskNameError:
            taskqueue.add(url='/worker', params={'user': user})
    else:        
        ndb.Key(models.BusyUser, user).delete()

    logging.info(user + ' took: ' + str(time.time() - start) + ' seconds.')


class TagWorker(webapp2.RequestHandler):
    def post(self):
        user = self.request.get('user')
        db.run_in_transaction(_process_user, user=user)


app = webapp2.WSGIApplication([
    ('/worker', TagWorker)
], debug=True)        
