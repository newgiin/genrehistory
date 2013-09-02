#!/usr/bin/python
import webapp2
import lastfm
import json
from time import sleep

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')

class GenreService(webapp2.RequestHandler):
    MAX_TAGS = 3

    def get_weeklyartists(self, user, start, end):
        weekly_artists = lfm_api.user_getweeklyartists(user, start, end)
        artists = {}
        if 'artist' in weekly_artists['weeklyartistchart']:
            artists = weekly_artists['weeklyartistchart']['artist']
        return artists

    def get_artisttags(self, artist, mbid, cache, limit=5):
        top_tags = []
        if artist in cache:
            top_tags = cache[artist]
        else:
            toptags_json = lfm_api.artist_gettoptags(artist, 
                mbid)
            if 'tag' in toptags_json['toptags']:
                tags = toptags_json['toptags']['tag']
                if isinstance(tags, list):
                    top_tags = [
                        e['name'] for e in 
                        tags[0:min(limit, len(tags))]
                    ]
                else:
                    top_tags = [tags['name']]
            cache[artist] = top_tags
            sleep(.2)

        return top_tags

    def get(self):
        artist_cache = {}

        result = { 'weeks': [] }
        self.response.headers['Content-Type'] = 'application/json'
        
        
        user = self.request.get('user')
        if not user:
            self.response.write(
                json.dumps({'error': 'No user specified.'}))
            return

        user_data = lfm_api.user_getinfo(user)['user']
        register_date = int(user_data['registered']['unixtime'])

        weeks = lfm_api.user_getweekintervals(user)['weeklychartlist']['chart']
        for week in reversed(weeks):
            if int(week['to']) < register_date:
                break

            week_elem = {'from': week['from'], 
                'to': week['to'], 'tags':{}}

            artists = self.get_weeklyartists(user, week['from'], week['to'])

            for artist in artists:
                artist_name = artist['name']

                top_tags = self.get_artisttags(artist_name, artist['mbid'],
                    artist_cache, self.MAX_TAGS)

                for tag in top_tags:
                    if tag in week_elem['tags']:
                        week_elem['tags'][tag] += int(artist['playcount'])
                    else:
                        week_elem['tags'][tag] = int(artist['playcount'])

            week_elem['tags'] = \
                {k:v for k,v in week_elem['tags'].items() if v > 1}

            result['weeks'].append(week_elem)
            #break
            sleep(.2)
            print 'NUM ARTISTS: ' + str(len(artist_cache))

        self.response.write(json.dumps(result))

application = webapp2.WSGIApplication([
    ('/', GenreService),
], debug=True)