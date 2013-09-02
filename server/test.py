import lastfm
import json

lfm_api = lastfm.LastFm('39c795e91c62cf9d469392c7c2648c80')
o = lfm_api.get_user('andruun')
print json.dumps(o)
