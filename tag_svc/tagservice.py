import webapp2
import json
import logging
import models
import lastfm
import time
import webapp2
import bisect
import math
from config import FRAGMENT_SIZE
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import ndb
from google.appengine.api.urlfetch_errors import DeadlineExceededError

lfm_api = lastfm.LastFm()

"""
Boilerplate for generating tag data response
"""
class TagService(webapp2.RequestHandler):

    """
    Meant to be overriden by subclass.
    Returns JSON response in dict format with the current data in the datastore
    associated with the user.
    """
    def build_response(self, user, curr_week):
        raise NotImplementedError

    """
    Return integer UNIX timestamp of when the data
    for this user was last updated.
    """
    def get_last_updated(self, user):
        user_entity = models.User.get_by_id(user)
        if user_entity is not None and user_entity.last_updated > 0:
            return user_entity.last_updated
        return None

    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Cache-Control'] = \
            'no-transform,public,max-age=300,s-maxage=900'
        user = self.request.get('user')

        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return
        else:
            user = user.lower()

        gwi_json = {}

        try:
            gwi_json = lfm_api.user_getweekintervals(user)
        except lastfm.ExceedRateLimitError:
            gwi_json['error'] = 29
            gwi_json['message'] = 'Rate limit exceeded'
        except lastfm.SuspendedAPIKeyError:
            gwi_json['error'] = 26
            gwi_json['message'] = 'Suspended API key'
        except lastfm.ServiceOfflineError:
            gwi_json['error'] = 11
            gwi_json['message'] = 'Service temporarily offline. ' + \
                                        'Please try again later.'
        except lastfm.TemporaryError:
            gwi_json['error'] = 16
            gwi_json['message'] = 'There was a temporary error processing your ' + \
                                        'request. Please try again.'
        except DeadlineExceededError:
            self.response.write(json.dumps(
                {'error': 'Could not reach Last.fm. Please try again later.'}))
            return


        if 'error' in gwi_json:
            error_msg = ''
            if int(gwi_json['error']) == 6:
                error_msg = 'User does not exist'
            else:
                error_msg = 'Last.fm error: ' + gwi_json['message']

            self.response.write(json.dumps({'error': error_msg}))
            return

        weeks = [int(week['to']) for week in gwi_json['weeklychartlist']['chart']]

        user_entity = models.User.get_by_id(user)

        if (user_entity is not None and
                user_entity.last_updated >= weeks[-1]):
            self.response.write(json.dumps(
                self.build_response(user, self.request)))
        else:
            user_data = lfm_api.user_getinfo(user)['user']
            register_date = int(user_data['registered']['unixtime'])

            # ensure User entity exists before start building data
            # so each data fragment can use this entity as the parent
            if user_entity is None and register_date < weeks[-1]:
                user_entity = models.User(id=user)
                user_entity.put()

            bu_entity = models.BusyUser.get_by_id(user)
            if bu_entity is None:
                intervals = get_worker_intervals(user_entity,
                    register_date, weeks)

                if intervals:
                    bu_entity = models.BusyUser(id=user, shout=False,
                        worker_count=len(intervals))
                    bu_entity.put()

                for interval in intervals:
                    add_worker(user, interval[0], interval[1], append_to=interval[2])

            self.response.headers['Cache-Control'] = \
                'no-transform,public,max-age=30'

            resp_data = {'status': 1, 'text': 'Data still processing'}

            last_updated = self.get_last_updated(user)
            if last_updated is not None:
                resp_data['last_updated'] = last_updated

            if weeks[-1] <= register_date:
                resp_data = {'error': 'Your account is too new for Last.fm to have data.'}

            self.response.write(json.dumps(resp_data))

"""
Return list of week timestamp 3-tuples, where each 3-tuples specifies a job
to distribute to a worker in the form of (start, end, append_to).
"""
def get_worker_intervals(user_entity, register_date, weeks):
    date_floor = register_date
    result = []

    if user_entity.last_updated is not None:
        # get end of incomplete fragment as we must finish it
        last_frag = models.TagHistory.query(ancestor=user_entity.key).order(
            -models.TagHistory.start).get()
        date_floor = user_entity.last_updated

        frag_size = get_interval_size(weeks, last_frag.start, last_frag.end)

        if frag_size < FRAGMENT_SIZE:
            start_i = bisect.bisect_right(weeks, date_floor)

            for i in xrange(start_i, len(weeks)):
                frag_size += 1
                if frag_size == FRAGMENT_SIZE:
                    result.append((weeks[i + 1 - FRAGMENT_SIZE],
                        weeks[i], last_frag.key.id()))
                    date_floor = weeks[i]
                    break

    # get the first week after 'date_floor'
    start_i = bisect.bisect_right(weeks, date_floor)

    for i in xrange(start_i+FRAGMENT_SIZE-1,
            len(weeks), FRAGMENT_SIZE):
        result.append((weeks[i-FRAGMENT_SIZE+1], weeks[i], None))

    remainder = (len(weeks)-start_i) % FRAGMENT_SIZE
    if remainder > 0:
        # submit job for last fragment
        result.append((weeks[len(weeks)-remainder], weeks[-1], None))

    return result

def get_interval_size(weeks, start, end):
    return bisect.bisect_left(weeks, end) - bisect.bisect_left(weeks, start) + 1

@ndb.transactional
def add_worker(user, start, end, append_to=None):
    logging.debug('adding worker for %d-%d', start, end)
    params = {'user': user,  'start': start, 'end': end }
    if append_to is not None:
        params['append_to'] = append_to

    try:
        taskqueue.add(url='/worker',
            name='%s_%d_%d' % (user, int(time.time()), start),
            params=params
        )
    except taskqueue.InvalidTaskNameError:
        taskqueue.add(url='/worker',
            params=params
        )