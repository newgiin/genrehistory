import webapp2
import json
import logging
import lastfm
from models import TagHistory, TagGraph, User, BusyUser
from config import FRAGMENT_SIZE, DS_VERSION
from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue
from google.appengine.runtime import DeadlineExceededError
from google.appengine.api.urlfetch_errors import DeadlineExceededError as \
    UrlFetchDeadlineExceededError
import time
import urllib
import bisect
from google.appengine.api import urlfetch

lfm_api = lastfm.LastFm()
CACHE_PRD = 604800 # 1 week
NS_AT_CACHE = 'artist_tags'
TAGS_PER_ARTIST = 3
PLAY_THRESHOLD = 6
NUM_TOP_ARTISTS = 3
MAX_TPW = 10 # tags per week
MAX_REQUEST_TIME = 600 # 10 minutes
DEADLINE_EXCEED_GRACE_PERIOD = 30


def _get_weeklyartists(user, start, end):
    weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
    artists = []

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

def _process_user(request, user, start, end, append_to=None):
    p_start = time.time()

    quota_state = _QuotaState(0, time.time() + _Quota.period)

    tag_history = {'user': user, 'weeks': []}
    tag_graph = {} # { tag_name: { plays: num_plays, adj: set_of_related } }

    logging.info('Started processing %s for %d-%d', user, start, end)
    weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']


    start_i = bisect_left_f(weeks, start, f=lambda week: int(week['to']))
    end_i = bisect_left_f(weeks, end, f=lambda week: int(week['to']))

    for i in xrange(start_i, end_i+1):
        week = weeks[i]

        week_elem = {'from': week['from'],
            'to': week['to'], 'tags':[]}
        tags = {}
        top_artists = {}

        artists = _Quota.run_with_quota(p_start, quota_state,
            _get_weeklyartists, user, week['from'], week['to'])

        for artist in artists:
            artist_name = artist['name']
            artist_plays = int(artist['playcount'])
            artist_tags = memcache.get(artist_name,
                namespace=NS_AT_CACHE)

            if artist_tags is None:
                artist_tags = _Quota.run_with_quota(p_start, quota_state,
                    _get_artisttags, artist_name, artist['mbid'],
                    TAGS_PER_ARTIST)

                memcache.add(artist_name, artist_tags, CACHE_PRD,
                    namespace=NS_AT_CACHE)

            # build tag history data
            if artist_tags:
                tag = artist_tags[0]
                if tag in tags:
                    tags[tag] += artist_plays
                    if len(top_artists[tag]) < NUM_TOP_ARTISTS:
                        top_artists[tag].append(artist_name)
                else:
                    tags[tag] = artist_plays
                    top_artists[tag] = [artist_name]

            # build tag graph data
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

        if (time.time() - p_start >
                MAX_REQUEST_TIME - DEADLINE_EXCEED_GRACE_PERIOD):
            raise DeadlineExceededError

    # filter out tags from graph with plays below threshold
    # TODO use different PLAY_THRESHOLD now that tagworker uses fragments?
    lil_tags = set([tag for tag in tag_graph if
                    tag_graph[tag]['plays'] < PLAY_THRESHOLD])
    tag_graph = {tag:v for tag, v in tag_graph.iteritems()
                    if tag_graph[tag]['plays'] >= PLAY_THRESHOLD}

    for tag in tag_graph:
        tag_graph[tag]['adj'] = {tag for tag in
                                    tag_graph[tag]['adj'] if
                                    tag not in lil_tags}


    if store_user_data(user, tag_history, tag_graph, start, end, append_to):
        logging.debug('Successfully stored tag data for %s: %d', user, start)
        finish_process(request, user, int(weeks[-1]['to']))
    else:
        logging.error("Processed %s who wasn't registered as User.",
            user)

    logging.info('%s took: %f seconds.', user, time.time() - p_start)



@ndb.transactional(xg=True, retries=5)
def finish_process(request, user, last_updated):
    user_entity = User.get_by_id(user, namespace=DS_VERSION)
    bu_entity = BusyUser.get_by_id(user, namespace=DS_VERSION)

    if bu_entity is None:
        logging.error("Processing %s who wasn't registered as BusyUser", user)
    else:
        bu_entity.worker_count -= 1
        if bu_entity.worker_count == 0:
            user_entity.last_updated = last_updated
            user_entity.put()

            # do the shoutin'
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

            bu_entity.key.delete()

        else:
            bu_entity.put()

"""
bisect_left that takes in a conversion function applied
to each element being compared in the array sort that
it can be compared to number 'x'.
"""
def bisect_left_f(a, x, lo=0, hi=None, f=lambda y: y):
    lo = 0
    hi = len(a)
    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a)

    while lo < hi:
        mid = (lo+hi)//2
        if f(a[mid]) < x:
            lo = mid+1
        else:
            hi = mid
    return lo

@ndb.transactional
def store_user_data(user, tag_history, tag_graph, start, end, append_to):
    user_entity = User.get_by_id(user, namespace=DS_VERSION)
    if user_entity is None:
        return False

    if append_to is not None:
        # merge histories
        hist_frag = TagHistory.get_by_id(append_to,
                        parent=user_entity.key, namespace=DS_VERSION)

        hist_frag.tag_history['weeks'] += tag_history['weeks']
        hist_frag.end = end
        hist_frag.put()

        # merge graphs
        graph_frag = TagGraph.get_by_id(append_to,
                        parent=user_entity.key, namespace=DS_VERSION)

        old_graph = graph_frag.tag_graph

        for tag in tag_graph:
            if tag in old_graph:
                old_graph[tag]['plays'] += tag_graph[tag]['plays']
                old_graph[tag]['adj'] = old_graph[tag]['adj'].union(
                    tag_graph[tag]['adj'])
            else:
                old_graph[tag] = tag_graph[tag]
        graph_frag.end = end
        graph_frag.put()
    else:
        user_entity.fragments.append({'start': start, 'end': end})
        user_entity.put()

        if tag_history['weeks']:
            TagHistory(id=user+str(start), tag_history=tag_history,
                start=start, end=end,
                parent=user_entity.key, namespace=DS_VERSION).put_async()
            TagGraph(id=user+str(start), tag_graph=tag_graph,
                start=start, end=end,
                parent=user_entity.key, namespace=DS_VERSION).put_async()

    return True

class TagWorker(webapp2.RequestHandler):
    @ndb.toplevel
    def post(self):
        user = self.request.get('user')
        start = int(self.request.get('start'))
        end = int(self.request.get('end'))
        append_to = self.request.get('append_to')
        if not append_to:
            append_to = None
        user = user.lower()

        try:
            _process_user(self.request, user, start, end, append_to)
        except DeadlineExceededError:
            logging.debug(user + ' request deadline exceeded. Restarting...')
            self.error(500)
        except UrlFetchDeadlineExceededError as e:
            logging.warning(e)
            self.error(500)

app = webapp2.WSGIApplication([
    ('/worker', TagWorker)
], debug=True)
