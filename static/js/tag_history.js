var user = getParameterByName('user');
var LFM_API_KEY = '24836bd9d7043e3c0bc65aa801ba8821';
var LFM_SECRET = '0df4b7481888ab8feb8a967e9f1ddd3b';
var lfm_api = new LastFM(LFM_API_KEY, LFM_SECRET);

var youtube_api = new Youtube('AIzaSyAqijDaBOtDreE1fxMvhwUz2QsyopL-FHU');
var ytplayer = null;
var DEFAULT_VIDEO_ID = 'aYeIGnni5jU';

var tracks = [];
var played = [];
var FIRST_RANKS_TO_PLAY = 5;

var week_chart = {};
var curr_week = 0;

var scrobbler = new TimedScrobbler();
var SCROBBLE_POLL_INTERVAL = 5;
var scrobble_poll_id = null;

$.getJSON('/history_data?user=' + encodeURIComponent(user)).done(render).fail(disp_error);
$.getJSON('http://ws.audioscrobbler.com/2.0/?method=user.getweeklychartlist' +
        '&user=' + encodeURIComponent(user) + '&api_key=' + LFM_API_KEY +
        '&format=json').done(init_week_chart).fail(disp_error);

// setup Youtube player
var params = { allowScriptAccess: 'always' };
var atts = { id: 'ytplayer' };
swfobject.embedSWF('http://www.youtube.com/v/aYeIGnni5jU?enablejsapi=1&playerapiid=ytplayer' +
                    '&version=3&fs=0&iv_load_policy=0&rel=0',
                   'ytplayer', '300', '200', '8', null, null, params, atts);

// bindings
$('#user_input').val(user);
$('#prev_btn').click(function() {
    set_week(week_chart[curr_week].prev, true);
});
$('#shfle_btn').click(function() {
    play_song(true);
});
$('#next_btn').click(function() {
    set_week(week_chart[curr_week].next, true);
});
$('#mix_mode_toggle').change(function() {
   if ($(this).is(':checked')) {
      $('#mix_mode_interval').prop('disabled', false);
   } else {
      $('#mix_mode_interval').prop('disabled', true);
   }
});

// fix footer
if($(document.body).height() < $(window).height()){
    $('#footer').css({
        position: 'absolute',
        top:  ( $(window).scrollTop() + $(window).height()
              - $('#footer').height() ) + 'px',
        width: '100%'
    });
} else {
    $('#footer').css({
        position: 'static'
    });
}

/**
* Initialize the week chart containing weekly timestamps
* used for navigating history via the next/back buttons.
*/
function init_week_chart(data, status) {
    if (!data.error) {
        var weeks = data.weeklychartlist.chart;
        week_chart[parseInt(weeks[0].from)] = {
            prev: null,
            next: parseInt(weeks[1].from),
            to: parseInt(weeks[0].to)
        };

        week_chart[parseInt(weeks[weeks.length-1].from)] = {
            prev: parseInt(weeks[weeks.length-2].from),
            next: null,
            to: parseInt(weeks[weeks.length-1].to)
        };

        for (var i = 1; i < weeks.length-1; i++) {
            week_chart[parseInt(weeks[i].from)] = {
                prev: parseInt(weeks[i-1].from),
                next: parseInt(weeks[i+1].from),
                to: parseInt(weeks[i].to)
            };
        }
    }
}

/**
* Callback to render the page content based on response history data.
*/
function render(data, status) {
    var status_div = document.getElementById('status');

    if (data.error) {
        status_div.innerHTML = data.error;
    } else if ('status' in data) {
        if (data.status === 1) {
            status_div.innerHTML = '';
            var status_text = document.createElement('div');
            status_text.innerHTML = 'Data still processing. First time could ' +
                                        'take around 10 minutes.';

            var update_time = 'Never';
            if (data.last_updated) {
                update_time =  Highcharts.dateFormat('%b %e, %Y',
                    parseInt(data.last_updated) * 1000);
            }
            status_text.innerHTML += '<br/>Last updated: ' + update_time;

            var shoutBtn = document.createElement('button');
            shoutBtn.onclick = function () {
                $.post('/set_shout', {'user': encodeURIComponent(user)},
                    shout_callback, 'json').fail(disp_error);
            };
            shoutBtn.innerHTML = 'Shout on my Last.fm <br/> profile when done';
            status_div.appendChild(status_text);
            status_div.appendChild(shoutBtn);
        } else {
            status_div.innerHTML = data.text;
        }
    } else {
        on_data_ready(data);
    }
}

function on_data_ready(data) {
    render_chart(data);

    lfm_api.session.key = localStorage['session_key'] || null;
    lfm_api.session.name = localStorage['session_name'] || null;

    render_scrobble_link();

    if (lfm_api.session.key) {
        start_scrobble_poll();
    }

    $('#status').css('visibility', 'hidden');
    $('#app_wrapper').css('visibility', 'visible');
    $('#player_wrapper').css('display', 'block');
}

function render_chart(data) {
    var tags = {} // tagName => [{x, y, artists}, ...]

    for (var w_i = 0; w_i < data.weeks.length; w_i++) {
        var week = data.weeks[w_i];
        for (var t_i = 0; t_i < week.tags.length; t_i++) {
            var tag_obj = week.tags[t_i];
            var data_point = {
                x: parseInt(week.from) * 1000,
                y: parseInt(tag_obj.plays),
                artists: tag_obj.artists.join(', ')
            }
            if (tags[tag_obj.tag]) {
                tags[tag_obj.tag].push(data_point)
            } else {
                tags[tag_obj.tag] = [data_point]
            }
        }
        // add zero-plays to tags we didn't touch this week so they don't persist
        // into next week
        var week_tags = $.map(week.tags, function(tag_obj) {
            return tag_obj.tag});
        for (var tag in tags) {
            // only add zero-play if last week's plays was not 0 for faster
            // point rendering
            if (week_tags.indexOf(tag) < 0 &&
                    tags[tag][tags[tag].length-1].y != 0) {
                tags[tag].push(
                    {x: parseInt(week.from) * 1000, y: 0, artists: ''}
                );
            }
        }
    }

    var series = [];
    for (var tag in tags) {
        series.push({
            name: tag,
            data: tags[tag],
            step: 'left'
        });
    }

    $('#chart').highcharts({
        title: {
            text: 'Tag History for <a href="http://www.last.fm/user/' +
                encodeURIComponent(user) + '" target="_blank">' + user + '</a>',
            useHTML: true
        },
        chart: {
            zoomType: 'x'
        },
        xAxis: {
            title: {
                text: 'week'
            },
            startOfWeek: 0,
            type: 'datetime',
            dateTimeLabelFormats: {
                week: '%e. %b'
            },
            minRange: 7 * 24 * 3600 * 1000
        },
        yAxis: {
            title: {
                text: 'plays'
            },
            min: 0
        },
        tooltip: {
            crosshairs: true,
            formatter: function() {
                return '<b>' + this.series.name + '</b><br/>' +
                    'Week from ' + Highcharts.dateFormat('%b %e, %Y', this.x) + '<br/>' +
                    this.series.name + ': ' + this.y + '<br/>' +
                    this.point.artists
            }
        },
        series: series,
        plotOptions: {
            series: {
                marker: {
                    enabled: false
                },
                point: {
                    events: {
                        click: function(event) {
                            set_week(this.x / 1000, true);
                        }
                    }
                }
            }
        }
    });

    $('#showall_btn').click(function() {
        var chart = $('#chart').highcharts();
        var series = chart.series;
        for (var i = 0; i < series.length; i++) {
            if (!series[i].visible) {
                series[i].show();
            }
        }
    });

    $('#hideall_btn').click(function() {
        var chart = $('#chart').highcharts();
        var series = chart.series;
        for (var i = 0; i < series.length; i++) {
            if (series[i].visible) {
                series[i].hide();
            }
        }
    });
}

function render_scrobble_link() {
    var default_text = '<a href="http://www.last.fm/api/auth?api_key=' +
                LFM_API_KEY + '&cb=' + getUrlRoot() + '/auth_callback.html">' +
                'Login to scrobble</a>';

    var login_elem = $('#lastfm_login');

    if (lfm_api.session.key == null || lfm_api.session.name == null) {
        login_elem.html(default_text);
    } else {
        login_elem.html('Scrobbling as ' + lfm_api.session.name + ' ');
        var logout_link = $('<a>')
        logout_link.click(function() {
            clear_session();
            clearInterval(scrobble_poll_id);
            login_elem.html(default_text);
        }).attr('href', 'javascript:void(0)').html('[x]');

        login_elem.append(logout_link);
    }
}

/*
* Retrieves weekly track information and plays a song.
* @param unix timestamp (in seconds) of the start of the week
*/
function set_week(week_unix, autoplay) {
    if (week_unix != null) {
        curr_week = week_unix;

        $('#player_date').text('Week from ' + Highcharts.dateFormat('%b %e, %Y',
            week_unix * 1000));
        $('#player_song').text('loading...');

        lfm_api.get_weeklytrackchart(user, week_unix,
            week_chart[week_unix].to,
                function(result) { set_player_songs(result, autoplay); });
    } else {
        $('#player_date').text('--');
        clear_song();
    }
}

function set_player_songs(result, autoplay) {
    if (result.weeklytrackchart && result.weeklytrackchart.track) {
        tracks = result.weeklytrackchart.track;
        play_song(autoplay);
    } else {
        // no songs for this week
        tracks = [];
        clear_song();
    }
}

function parseIsoDuration(iso_duration) {
    /**
    * Convert an ISO8601 duration to seconds.
    */
    var reptms = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/;
    var hours = 0, minutes = 0, seconds = 0, totalseconds;

    if (reptms.test(iso_duration)) {
        var matches = reptms.exec(iso_duration);
        if (matches[1])
            hours = Number(matches[1]);
        if (matches[2])
            minutes = Number(matches[2]);
        if (matches[3])
            seconds = Number(matches[3]);
        return hours*3600  + minutes*60 + seconds;
    }
}

function play_song(autoplay) {
    if (tracks.length > 0) {
        var track = get_song_to_play();

        $('#player_song').text(track.artist['#text'] + ' - ' +
                                    track.name);

        youtube_api.search_videos(track.artist['#text'] + ' ' + track.name, 1,
            function(result) {
                if (result.items.length > 0) {
                    var video_id = result.items[0].id.videoId;

                    if (!document.getElementById('mix_mode_toggle').checked) {
                        ytplayer.loadVideoById(video_id);
                    }

                    if (document.getElementById('mix_mode_toggle').checked ||
                            lfm_api.session.key != null) {
                        youtube_api.video_details(video_id,
                            function(result) {
                                var duration = parseIsoDuration(result.items[0].contentDetails.duration);
                                scrobbler.set_song(track.artist['#text'], null,
                                    track.name, duration);                                
                                if (document.getElementById('mix_mode_toggle').checked) {
                                        var play_time = 60;
                                        var pt_txt = $('#mix_mode_interval').val();
                                        if ($.isNumeric(pt_txt) &&
                                                parseInt(pt_txt) > 0) {
                                            play_time = parseInt(pt_txt);
                                        }

                                        var start_time = duration*(Math.random()*0.40 + 0.30);
                                        ytplayer.loadVideoById({videoId: video_id,
                                            startSeconds: start_time,
                                            endSeconds: start_time + play_time});
                                }
                            }
                        );
                    }
                    // TODO this doesn't always stop the video
                    if (!autoplay) {
                        ytplayer.stopVideo();
                    }
                } else {
                    // video not found, get next song to play from this week
                    play_song(true);
                }
            });
    } else {
        clear_song();
    }
}

/*
* Randomly choose a song, with priority given to songs with rank <= FIRST_RANKS_TO_PLAY,
* whenceforth the remaining songs are returned at random.
*/
function get_song_to_play() {
    var track = null;

    var last_toprank_i = -1;
    for (var i = 0; i < tracks.length &&
            parseInt(tracks[i]['@attr'].rank) <= FIRST_RANKS_TO_PLAY;
            i++) {
        last_toprank_i++;
    }

    // play random one of the top songs if we can
    if (last_toprank_i > -1) {
        track = tracks.splice(getRandomInt(0, last_toprank_i + 1), 1)[0];
    } else {
        track = tracks.splice(getRandomInt(0, tracks.length), 1)[0];
    }
    played.push(track);

    if (tracks.length == 0) {
        tracks = played;
        played = [];
    }

    return track;
}

function onYouTubePlayerReady(playerId) {
    ytplayer = document.getElementById('ytplayer');
    ytplayer.addEventListener('onStateChange', 'onPlayerStateChange');
}

function onPlayerStateChange(newState) {
    if (newState === 0) { // video ended
        var direction = parseInt(
            $('#options_form input[name=song_end_action]:checked').val());
        if (direction < 0) {
            set_week(week_chart[curr_week].prev, true);
        } else if (direction > 0) {
            set_week(week_chart[curr_week].next, true);
        } else {
            play_song(true);
        }
    }
}

function disp_error(jqxhr, textStatus, error) {
    alert(textStatus + ': ' + error);
}

function clear_song() {
    $('#player_song').text('--');
    scrobbler.clear_song();
    ytplayer.loadVideoById(DEFAULT_VIDEO_ID);
}

function start_scrobble_poll() {
    scrobble_poll_id = setInterval(function() {
        if (ytplayer.getPlayerState() === 1 && scrobbler.has_song()) {
            var song = scrobbler.song;

            scrobbler.add_time(SCROBBLE_POLL_INTERVAL, scrobble_song);
            lfm_api.now_playing(song.artist, song.album, song.track,
                function(resp) {});
        }
    }, SCROBBLE_POLL_INTERVAL * 1000);
}

function scrobble_song(artist, album, title, time) {
    lfm_api.scrobble(artist, album, title, time,
        function(response) {
            if (response.error) {
                if (response.error == 9) {
                    // Session expired
                    clear_session();
                }
            }
        });
}

function clear_session() {
    lfm_api.session = {};
    localStorage.removeItem('session_key');
    localStorage.removeItem('session_name');
}

function shout_callback(data) {
    if (data.error) {
        alert(data.error);
    } else {
        alert('A shout will be left on your Last.fm profile once the data ' +
            'is ready!');
    }
}

/*
* returns integer in [min, max)
*/
function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min) + min);
}

function getParameterByName(name) {
    name = name.replace(/[\[]/, '\\\[').replace(/[\]]/, '\\\]');
    var regex = new RegExp('[\\?&]' + name + '=([^&#]*)'),
        results = regex.exec(location.search);
    return results == null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
}

function getUrlRoot() {
    return location.protocol + '//' +
        location.hostname + (location.port ? ':' + location.port: '');
}
