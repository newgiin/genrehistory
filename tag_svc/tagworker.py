import webapp2
import json
import logging
import lastfm
import models
from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue
from google.appengine.runtime import DeadlineExceededError
from google.appengine.api.urlfetch_errors import DeadlineExceededError as \
    UrlFetchDeadlineExceededError
import time
import urllib
from google.appengine.api import urlfetch

lfm_api = lastfm.LastFm()
CACHE_PRD = 604800 # 1 week
AT_CACHE_NS = 'artist_tags'
TAGS_PER_ARTIST = 3
PLAY_THRESHOLD = 6
NUM_TOP_ARTISTS = 3
MAX_TPW = 10 # tags per week
MAX_REQUEST_TIME = 600 # 10 minutes
DEADLINE_EXCEED_GRACE_PERIOD = 30


def _get_weeklyartists(user, start, end):
    weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
    artists = {}

    try:
        if 'error' in weekly_artists:
            logging.warning('Error getting top artists for %s in week %s-%s: %s',
                user, start, end, weekly_artists['error'])
        elif 'artist' in weekly_artists['weeklyartistchart']:
            if isinstance(
                    weekly_artists['weeklyartistchart']['artist'], list
                ):
                artists = weekly_artists['weeklyartistchart']['artist']
            else:
                artists = [weekly_artists['weeklyartistchart']['artist']]
    except TypeError:
        logging.warning('No data getting top artists for %s in week %s-%s',
            user, start, end)

    return artists

def _get_artisttags(artist, mbid, limit=5):
    top_tags = []
    toptags_json = lfm_api.artist_gettoptags(artist,
        mbid)

    if 'error' in toptags_json:
        logging.warning('Error getting tag data for %s[%s]: %s',
            artist, mbid, toptags_json['error'])
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
    def run_with_quota(start, quota_state, f, *args):
        """
        Call 'f(*args)' returning the result if the current number of requests
        for this period is not over the request limit. Otherwise, sleep until
        the next_interval, reset the current number of requests to zero,
        and then call 'f', incrementing quota_state.num_reqs by 1.
        """
        if quota_state.num_reqs >= _Quota.req_limit:
            now = time.time()
            try:
                # To ensure next time.time() >= next_interval,
                # add half a second due to potential imprecisions
                # with time.sleep()
                wake_time = quota_state.next_interval + 0.5
                if (wake_time > start +
                        MAX_REQUEST_TIME - DEADLINE_EXCEED_GRACE_PERIOD):
                    raise DeadlineExceededError

                logging.debug('Reached request limit, waiting: %f seconds.',
                    quota_state.next_interval - now)
                time.sleep(wake_time - now)
            except IOError:
                # In the rare case request limit is hit
                # after next_interval is reached
                pass
        if time.time() >= quota_state.next_interval:
            quota_state.num_reqs = 0
            quota_state.next_interval = time.time() + _Quota.period

        quota_state.num_reqs += 1
        return f(*args)

class _QuotaState:
    def __init__(self, num_reqs, next_interval):
        self.num_reqs = num_reqs
        self.next_interval = next_interval

def _process_user(request, user):
    start = time.time()

    quota_state = _QuotaState(0, time.time() + _Quota.period)

    hist_entity = models.TagHistory.get_by_id(user)
    graph_entity = models.TagGraph.get_by_id(user)

    tag_history = {'user': user, 'weeks': []}
    tag_graph = {} # { tag_name: { plays: num_plays, adj: set_of_related } }
    date_floor = None

    if hist_entity is None:
        user_data = lfm_api.user_getinfo(user)['user']
        date_floor = int(user_data['registered']['unixtime'])
    else:
        date_floor = hist_entity.last_updated
        tag_graph = graph_entity.tag_graph
        tag_history = hist_entity.tag_history

    logging.info('Started processing %s from week %d', user, date_floor)
    weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']

    try:
        for week in weeks:
            # From oldest to newest
            if int(week['to']) <= date_floor:
                continue

            week_elem = {'from': week['from'],
                'to': week['to'], 'tags':[]}
            tags = {}
            top_artists = {}

            artists = _Quota.run_with_quota(start, quota_state,
                _get_weeklyartists, user, week['from'], week['to'])

            for artist in artists:
                artist_name = artist['name']
                artist_plays = int(artist['playcount'])
                artist_tags = memcache.get(artist_name,
                    namespace=AT_CACHE_NS)

                if artist_tags is None:
                    artist_tags = _Quota.run_with_quota(start, quota_state,
                        _get_artisttags, artist_name, artist['mbid'],
                            TAGS_PER_ARTIST)
                    memcache.add(artist_name, artist_tags, CACHE_PRD,
                        namespace=AT_CACHE_NS)

                if artist_tags:
                    tag = artist_tags[0]
                    if tag in tags:
                        tags[tag] += artist_plays
                        if len(top_artists[tag]) < NUM_TOP_ARTISTS:
                            top_artists[tag].append(artist_name)
                    else:
                        tags[tag] = artist_plays
                        top_artists[tag] = [artist_name]

                for tag in artist_tags:
                    if tag in tag_graph:
                        tag_graph[tag]['plays'] += artist_plays
                    else:
                        tag_graph[tag] = {'plays': artist_plays,
                                                'adj': set()}

                    for syn_tag in artist_tags:
                        if syn_tag != tag:
                            tag_graph[tag]['adj'].add(syn_tag)

            week_elem['tags'] = [{'tag': k, 'plays': v,
                                    'artists': top_artists[k]}
                                    for k, v in tags.iteritems()
                                    if v >= PLAY_THRESHOLD]

            week_elem['tags'].sort(key=lambda e: e['plays'], reverse=True)
            week_elem['tags'] = week_elem['tags'][:MAX_TPW]

            tag_history['weeks'].append(week_elem)

            if (time.time() - start >
                    MAX_REQUEST_TIME - DEADLINE_EXCEED_GRACE_PERIOD):
                raise DeadlineExceededError

        # filter out tags from graph with plays below theshold
        lil_tags = set([tag for tag in tag_graph if
                        tag_graph[tag]['plays'] < PLAY_THRESHOLD])
        tag_graph = {tag:v for tag, v in tag_graph.iteritems()
                        if tag_graph[tag]['plays'] >= PLAY_THRESHOLD}

        for tag in tag_graph:
            tag_graph[tag]['adj'] = {tag for tag in
                                        tag_graph[tag]['adj'] if
                                        tag not in lil_tags}

        bu_key = ndb.Key(models.BusyUser, user)
        bu_entity = bu_key.get()
        if bu_entity is None:
            logging.error("Processed %s who wasn't registered as BusyUser.",
                user)
        else:
            if bu_entity.shout:
                msg = ('Your tag visualizations are ready at %s/history?user=%s'
                        ' and %s/tag_graph?tp=20&user=%s'
                        % (request.host_url, urllib.quote(user),
                            request.host_url, urllib.quote(user)))

                try:
                    shout_resp = lfm_api.user_shout(user, msg)
                    if 'status' in shout_resp and shout_resp['status'] == 'ok':
                        logging.info('Shouted to ' + user)
                    else:
                        logging.error('Error shouting to %s: %s',
                            user, shout_resp)
                except lastfm.InvalidSessionError:
                    logging.error('Could not shout. Last.fm session invalid.')

            bu_key.delete_async()

        logging.info('%s took: %f seconds.', user, time.time() - start)
    finally:
        #
        # Always store what we have, so in case of error
        # we can pickup where we leftoff on retry
        #
        store_user_data(user, tag_history, tag_graph)
        logging.debug('Successfully stored tag data for ' + user)


@ndb.transactional(xg=True)
def store_user_data(user, tag_history, tag_graph):
    hist_entity = models.TagHistory(id=user,
        last_updated=int(tag_history['weeks'][-1]['to']),
        tag_history=tag_history)

    hist_entity.put_async()

    graph_entity = models.TagGraph(id=user,
        last_updated=int(tag_history['weeks'][-1]['to']),
        tag_graph=tag_graph)

    graph_entity.put_async()

class TagWorker(webapp2.RequestHandler):
    @ndb.toplevel
    def post(self):
        user = self.request.get('user')
        user = user.lower()

        try:
            _process_user(self.request, user)
        except DeadlineExceededError:
            logging.debug(user + ' request deadline exceeded. Restarting...')
            self.error(500)
        except UrlFetchDeadlineExceededError as e:
            logging.warning(e)
            self.error(500)

app = webapp2.WSGIApplication([
    ('/worker', TagWorker)
], debug=True)
