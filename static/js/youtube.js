function Youtube(api_key) {
    this.API_KEY = api_key;
    this.API_ROOT = 'https://gdata.youtube.com/feeds/api/videos';
}

/**
* Returns 'max_results' videos matching 'query'.
*/
Youtube.prototype.search_videos = function(query, max_results, callback) {
    var params = {
        'q': query.replace('-',' ').replace('|', ' '), // ignore boolean operators
        'max-results': max_results,
        'v': 2,
        'fields': 'entry(media:group(yt:videoid,yt:duration))'
    };

    params.alt = 'json';
    this._xhr('GET', params,
        function(result) {
            callback(result);
        });
}

Youtube.prototype._xhr = function(method, params, callback) {
    var uri = this.API_ROOT;
    var _data = '';
    var _params = [];
    var xhr = new XMLHttpRequest();

    for(param in params) {
        _params.push(encodeURIComponent(param) + '='
            + encodeURIComponent(params[param]));
    }

    switch(method) {
        case 'GET':
            uri += '?' + _params.join('&');
            break;
        case 'POST':
            _data = _params.join('&');
            break;
        default:
            return;
    }

    xhr.open(method, uri);

    xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
            var reply;

            try {
                reply = JSON.parse(xhr.responseText);
            }
            catch (e) {
                console.error(e);
                reply = null;
            }

            callback(reply);
        }
    };

    xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded; charset=UTF-8');
    xhr.setRequestHeader('X-GData-Key', 'key=' + this.API_KEY);
    // The cache is a lie!
    /*xhr.setRequestHeader('If-Modified-Since', new Date(0));
    xhr.setRequestHeader('Pragma', 'no-cache');*/

    xhr.send(_data || null);
    console.log(uri);
};