#!/usr/bin/python
import urllib2
import urllib
import json
import logging
import hashlib
import models
from google.appengine.api import urlfetch

class LastFm:
    API_KEY = '24836bd9d7043e3c0bc65aa801ba8821'
    API_SECRET = '0df4b7481888ab8feb8a967e9f1ddd3b'

    def __init__(self, key=API_KEY, secret=API_SECRET, session_key=None):
        self.API_ROOT = 'http://ws.audioscrobbler.com/2.0/'
        self.api_key = key
        self.api_secret = secret
        if session_key is None:
            sk_entity = models.LastFmSession.get_by_id(key, namespace='admin')
            if sk_entity is None:
                logging.error('Server side session key has not been set.')
                self.session_key = ''
            else:
                self.session_key = sk_entity.session_key
        else:
            self.session_key = session_key

    def user_getinfo(self, user):
        params = {
            'api_key': self.api_key,
            'user': user,
            'method': 'user.getinfo',
            'format': 'json'
        }

        return self.xhr(params)

    def user_getweekintervals(self, user):
        params = {
            'api_key': self.api_key,
            'method': 'user.getweeklychartlist',
            'user': user,
            'format': 'json'
        }
        # result = self.xhr(params)
        # result['weeklychartlist']['chart'] = result['weeklychartlist']['chart'][450:]

        return self.xhr(params)

    def user_getweeklyartists(self, user, start, end):
        params = {
            'api_key': self.api_key,
            'method': 'user.getweeklyartistchart',
            'user': user,
            'from': start,
            'to': end,
            'format': 'json'
        }

        return self.xhr(params)

    def artist_gettoptags(self, artist, mbid=None):
        params = {
            'api_key': self.api_key,
            'method': 'artist.gettoptags',
            'format': 'json',
            'artist': artist.encode('utf-8')
        }
        if mbid:
            params['mbid'] = mbid

        return self.xhr(params)

    def user_shout(self, user, message):
        params = {
            'method': 'user.shout',
            'user': user,
            'message': message,
            'api_key': self.api_key,
            'sk': self.session_key
        }

        params['api_sig'] = self._get_signature(params)
        params['format'] = 'json'

        return self.xhr(params, urlfetch.POST)

    def auth_getsession(self, token):
        params = {
            'method': 'auth.getSession',
            'api_key': self.api_key,
            'token': token
        }

        params['api_sig'] = self._get_signature(params)
        params['format'] = 'json'

        return self.xhr(params)

    def _get_signature(self, params):
        m = hashlib.md5()

        for param in sorted(params.keys()):
            m.update(param + params[param].encode('utf-8'))

        m.update(self.api_secret)

        return m.hexdigest()

    def xhr(self, params, method=urlfetch.GET):
        url = self.API_ROOT + '?' + urllib.urlencode(params)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        #logging.debug(url)

        result = urlfetch.fetch(url=url,
             method=method, headers=headers)

        if result.status_code != 200:
            return {'error': 'urlfetch error: ' + str(result.status_code)}

        result = json.loads(result.content)

        if 'error' in result:
            error_code = int(result['error'])
            if error_code == 9:
                logging.error('Invalid Last.fm session key')
                raise InvalidSessionError

            elif error_code == 11:
                logging.error('Last.fm service offline')
                raise ServiceOfflineError

            elif error_code == 16:
                logging.warning('Temporary Last.fm error')
                raise TemporaryError

            elif error_code == 29:
                logging.critical('Exceeded Last.fm rate limit')
                raise ExceedRateLimitError

            elif error_code == 26:
                logging.critical('Suspended Last.fm API key')
                raise SuspendedAPIKeyError

        return result

class InvalidSessionError(Exception):
    pass

class ExceedRateLimitError(Exception):
    pass

class SuspendedAPIKeyError(Exception):
    pass

class ServiceOfflineError(Exception):
    pass

class TemporaryError(Exception):
    pass