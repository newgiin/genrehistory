var user = getParameterByName('user');
var LFM_API_KEY = '24836bd9d7043e3c0bc65aa801ba8821';
var lfm_api = new LastFM(LFM_API_KEY);
var ytplayer = null;
var youtube_api = new Youtube('AI39si7jF5UfjKldRqlcQboZfiUb_t93M6YJ0nocNOwxisoHNQb7Ym54EzWadArRKF8BoEkc2AOAAddBI7t2xEcibrSeghbXyw');
var DEFAULT_VIDEO_ID = 'aYeIGnni5jU';
var tracks = [];
var played = [];
var week_chart = {}; // { week_from: [prev_from, next_from, curr_to]}
var curr_week = 0;
var FIRST_RANKS_TO_PLAY = 5;

$.getJSON('/history_data?user=' + encodeURIComponent(user)).done(render).fail(disp_error);

// setup Youtube player
var params = { allowScriptAccess: 'always' };
var atts = { id: 'ytplayer' };
swfobject.embedSWF('http://www.youtube.com/v/aYeIGnni5jU?enablejsapi=1&playerapiid=ytplayer' +
                    '&version=3&fs=0&iv_load_policy=0&rel=0',
                   'ytplayer', '300', '200', '8', null, null, params, atts);

$('#user_input').val(user);
$('#prev_btn').click(function() {
    set_week(week_chart[curr_week][0], true);
});
$('#shfle_btn').click(function() {
    play_song(true);
});
$('#next_btn').click(function() {
    set_week(week_chart[curr_week][1], true);
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

function init_week_chart(data, status) {
    if (!data.error) {
        var weeks = data.weeklychartlist.chart;
        week_chart[parseInt(weeks[0].from)] = [null, parseInt(weeks[1].from), 
            parseInt(weeks[0].to)];
        week_chart[parseInt(weeks[weeks.length-1].from)] = 
            [parseInt(weeks[weeks.length-2].from), null, 
            parseInt(weeks[weeks.length-1].to)];

        for (var i = 1; i < weeks.length-1; i++) {
            week_chart[parseInt(weeks[i].from)] = 
                [parseInt(weeks[i-1].from), parseInt(weeks[i+1].from), parseInt(weeks[i].to)];
        }

        curr_week = parseInt(weeks[weeks.length-1].from);
        set_week(curr_week, false);
    }
}

function render(data, status) {
    if (data.error) {
        document.getElementById('status').innerHTML = data.error;
    } else if ('status' in data) {
        var status_text = '';
        if (data.status == 1) {
             status_text = 'Data still processing. First time can take ' + 
                'around 10 minutes depending how much data you have.';
        } else {
            status_text = data.text;
        }
        document.getElementById('status').innerHTML = status_text;
    } else {
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
                // only add zero-play if last week's plays was not 0
                if (week_tags.indexOf(tag) < 0 &&
                        tags[tag][tags[tag].length-1].y != 0) {
                    tags[tag].push(
                        {x: parseInt(week.from) * 1000, y: 0, artists: ''}
                    )
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

        $(function () {
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
                            'Week from ' + Highcharts.dateFormat('%a, %b %e, %Y', this.x) + '<br/>' + 
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

        });
        $('#status').css('visibility', 'hidden');
        $('#app_wrapper').css('visibility', 'visible');
        $('#player_wrapper').css('display', 'block');
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
            week_chart[week_unix][2], 
                function(result) { set_player_songs(result, autoplay) });
    } else {
        $('#player_date').text('--');
        $('#player_song').text('--');
        ytplayer.loadVideoById(DEFAULT_VIDEO_ID);   
    }
}

function set_player_songs(result, autoplay) {
    if (result.weeklytrackchart && result.weeklytrackchart.track) {
        tracks = result.weeklytrackchart.track;

        to_play = []
        for (var i = 0; i < tracks.length; i++) {
            to_play.push(i);
        }

        play_song(autoplay);
    } else { 
        // no songs for this week
        tracks = [];
        $('#player_song').text('--');
        ytplayer.loadVideoById(DEFAULT_VIDEO_ID);
    }
}

function play_song(autoplay) {
    if (tracks.length > 0) {
        var track = get_song_to_play();

        $('#player_song').text(track.artist['#text'] + ' - ' + track.name);

        youtube_api.search_videos(track.artist['#text'] + ' ' + track.name, 1, 
            function(result) {
                if (result.feed.entry && result.feed.entry.length > 0) {
                    var videoId = result.feed.entry[0]['media$group']['yt$videoid']['$t'];
                    ytplayer.loadVideoById(videoId);
                    if (!autoplay) {
                        ytplayer.stopVideo();
                    }
                } else { // video not found, get next song to play
                    play_song(true);
                }                
            });
    } else {
        ytplayer.loadVideoById(DEFAULT_VIDEO_ID);
    }
}

/*
* Randomly choose a song, with priority given to songs with rank <= FIRST_RANKS_TO_PLAY,
* whenceforth the remaining songs are returned at random.
*/
function get_song_to_play() {
    var track = null;

    var last_toprank_i = -1;
    for (var i = 0; i < tracks.length; i++) {
        if (parseInt(tracks[i]['@attr'].rank) <= FIRST_RANKS_TO_PLAY) {
            last_toprank_i++;
        }
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
    $.getJSON('http://ws.audioscrobbler.com/2.0/?method=user.getweeklychartlist' + 
            '&user=' + user + '&api_key=' + LFM_API_KEY +
            '&format=json').done(init_week_chart).fail(disp_error);    
}

function onPlayerStateChange(newState) {
    if (newState === 0) { // video ended
        set_week(week_chart[curr_week][1], true);
    }
}

function disp_error(jqxhr, textStatus, error) {
    alert(textStatus + ': ' + error);
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