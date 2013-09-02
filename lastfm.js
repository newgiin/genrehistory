/**
 * lastfm.js
 * Last.fm authorization and scrobbling XHR requests
 * Copyright (c) 2011 Alexey Savartsov <asavartsov@gmail.com>
 * Licensed under the MIT license
 */

/**
 * LastFM class constructor
 *
 * @param api_key Last.fm API key
 * @param api_secret Last.fm API secret
 */
function LastFM(api_key, api_secret) {
    this.API_KEY = api_key || "";
    this.API_SECRET = api_secret || "";
    this.API_ROOT = "http://ws.audioscrobbler.com/2.0/";
}

LastFM.prototype.get_user = function(user, callback) {
    var params = {
        'api_key': this.API_KEY,
        'user': user,
        'method': 'user.getinfo',
    };
    
    params.format = "json";
    
    this._xhr("GET", params, 
        function(result) {
            callback(result);
        });
};

LastFM.prototype.get_weeklycharts = function(user, callback) {
    var params = {
        'api_key': this.API_KEY,
        'method': 'user.getweeklychartlist',
        'user': user
    };
    
    params.format = "json";
    
    this._xhr("GET", params, 
        function(result) {
            callback(result);
        });    
}

LastFM.prototype.get_weeklyartistchart = function(user, 
        from, to, callback) {
    var params = {
        'api_key': this.API_KEY,
        'method': 'user.getweeklyartistchart',
        'user': user,
        'from': from,
        'to': to
    };
    
    params.format = "json";
    
    this._xhr("GET", params, 
        function(result) {
            callback(result);
        });      
}
/**
 * Performs an XMLHTTP request and expects JSON as reply
 *
 * @param method Request method (GET or POST)
 * @param params Hash with request values. All request fields will be
 *               automatically urlencoded
 * @param callback Callback function for the request. Sends a parameter with
 *                 reply decoded as JS object from JSON on null on error
 */
LastFM.prototype._xhr = function(method, params, callback) {
    var uri = this.API_ROOT;
    var _data = "";
    var _params = [];
    var xhr = new XMLHttpRequest();
    
    for(param in params) {
        _params.push(encodeURIComponent(param) + "="
            + encodeURIComponent(params[param]));
    }
    
    switch(method) {
        case "GET":
            uri += '?' + _params.join('&').replace(/%20/, '+');
            break;
        case "POST":
            _data = _params.join('&');
            break;
        default:
            return;
    }
    
    
    xhr.open(method, uri);
    
    // TODO: Better error handling
    xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
            var reply;
            
            try {
                reply = JSON.parse(xhr.responseText);
            }
            catch (e) {
                reply = null;
            }
            
            callback(reply);
        }
    };

    xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded; charset=UTF-8");
    // The cache is a lie!
    /*xhr.setRequestHeader("If-Modified-Since", new Date(0));
    xhr.setRequestHeader("Pragma", "no-cache");*/
    
    xhr.send(_data || null);
    // TODO remove this
    console.log(uri);
};
