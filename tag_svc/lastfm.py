#!/usr/bin/python
import urllib2
import urllib
import json
import logging
from google.appengine.api import urlfetch

class LastFm:
    def __init__(self, key, secret=''):
        self.API_ROOT = 'http://ws.audioscrobbler.com/2.0/'
        self.API_KEY = key
        self.API_SECRET = secret

    def user_getinfo(self, user):
        params = {
            'api_key': self.API_KEY,
            'user': user,
            'method': 'user.getinfo',
            'format': 'json'
        }

        return self.xhr(params)

    def user_getweekintervals(self, user):
        params = {
            'api_key': self.API_KEY,
            'method': 'user.getweeklychartlist',
            'user': user,
            'format': 'json'
        }

        return self.xhr(params)

    def user_getweeklyartists(self, user, start, end):
        params = {
            'api_key': self.API_KEY,
            'method': 'user.getweeklyartistchart',
            'user': user,
            'from': start,
            'to': end,
            'format': 'json'
        }
        
        return self.xhr(params)

    def artist_gettoptags(self, artist, mbid=None):
        params = {
            'api_key': self.API_KEY,
            'method': 'artist.gettoptags',
            'format': 'json',
            'artist': artist.encode('utf-8')
        }
        if mbid:
            params['mbid'] = mbid

        return self.xhr(params)

    def xhr(self, params):
        url = self.API_ROOT + '?' + urllib.urlencode(params)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        #logging.debug(url)

        result = urlfetch.fetch(url=url, 
             method=urlfetch.GET, headers=headers)

        if result.status_code != 200:
            return {'error': 'urlfetch error: ' + str(result.status_code)}

        result = json.loads(result.content)


        if 'error' in result:
            error_code = int(result['error'])
            if error_code == 29:
                logging.critical('Exceeded Last.fm rate limit')
                raise ExceedRateLimitError
            elif error_code == 26:
                logging.critical('Suspended Last.fm API key')
                raise SuspendedAPIKeyError
            elif error_code == 11:
                logging.error('Last.fm service offline')
                raise ServiceOfflineError
            elif error_code == 16:
                logging.warning('Temporary Last.fm error')
                raise TemporaryError

        return result

class ExceedRateLimitError(Exception):
    pass

class SuspendedAPIKeyError(Exception):
    pass

class ServiceOfflineError(Exception):
    pass

class TemporaryError(Exception):
    pass