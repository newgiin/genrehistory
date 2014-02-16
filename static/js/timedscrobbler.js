/**
* TimedScrobbler scrobbles songs after a certain amount of a song has
* been played, and has the option to scrobble long songs
* multiple times at regular intervals.
* By default, this will scrobble every 7 minutes or after 70% of
* the song has been played, whichever happens first.
*
* This is a simple scheduler. Client code handles the actual scrobbling
* via the scrobble function passed into add_time().
* Used by constructing a TimedScrobbler, calling set_song(),
* add adding add_time() at intervals of appropriate granularity.
*/

/*
* Takes in an options object with possible fields:
* scrobble_point(default=.70): A number between .50 and 1.
*                  Will scrobble once scrobble_point * song_length
*                  has been played.
* repeat_interval(default=420): Scrobble interval for long songs in seconds.
*                  Will scrobble every 'repeat_interval' seconds.
* is_repeat_scrobble(default=true): False to disable repeat scrobbling.
*/
function TimedScrobbler(opts) {
    if (!opts) {
        opts = {};
    }
    // defaults
    this.scrobble_point = 0.70;
    this.repeat_interval = 420;
    this.song = null;

    this._max_scrobbles = Number.POSITIVE_INFINITY;
    this._num_scrobbles = 0;
    this._time_played = 0;

    if (opts.is_repeat_scrobble === false) {
        this._max_scrobbles = 1;
    }

    if (opts.scrobble_point && opts.scrobble_point >= .50 &&
            opts.scrobble_point <= 1) {
        this.scrobble_point = opts.scrobble_point;
    }

    if (opts.repeat_interval) {
        this.repeat_interval = opts.repeat_interval;
    }
}

TimedScrobbler.prototype.set_song = function(artist, album, track, track_length) {
    this.song = new _Song(artist, album, track, track_length);
    this._time_played = 0;
    this._num_scrobbles = 0;
}

/**
* Add time to the currently played song. Will call 'scrobble_func'
* if enough of the song has been played.
* @param seconds Number of seconds to add
* @param scrobble_func Function with parameters
*        (artist, album, track, timestamp)
*/
TimedScrobbler.prototype.add_time = function(seconds, scrobble_func) {
    if (!this.song) {
        throw 'Cannot add time with no song defined.';
    }

    this._time_played += seconds;
    if ((this._time_played >= this.song.track_length * this.scrobble_point ||
                this._time_played >= this.repeat_interval) &&
                this._num_scrobbles < this._max_scrobbles) {

            scrobble_func(this.song.artist, this.song.album, this.song.track,
                Math.round(new Date().getTime() / 1000) - this._time_played);
            this._time_played = 0;
            this._num_scrobbles += 1;
    }
}

TimedScrobbler.prototype.has_song = function() {
    return this.song != null;
}

TimedScrobbler.prototype.clear_song = function() {
    this.song = null;
}

function _Song(artist, album, track, track_length) {
    this.artist = artist;
    this.album = album;
    this.track = track;
    this.track_length = track_length;
}