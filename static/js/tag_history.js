var user = getParameterByName('user');
var lfm_api = new LastFM('24836bd9d7043e3c0bc65aa801ba8821');
var ytplayer = null;
var youtube_api = new Youtube('AI39si7jF5UfjKldRqlcQboZfiUb_t93M6YJ0nocNOwxisoHNQb7Ym54EzWadArRKF8BoEkc2AOAAddBI7t2xEcibrSeghbXyw');

var tracks = null;

$('#user_input').val(user);
$('#user_link').attr('href', 'http://last.fm/user/' + encodeURIComponent(user)).text(user);
$('#shfle_btn').click(function() {
    play_random();
});

$.getJSON('/history_data?user=' + encodeURIComponent(user)).done(render).fail(disp_error);

function render(data, status, jqXHR) {
    if (data.error) {
        document.getElementById('chart').innerHTML = data.error;
    } else if (data.status) {
        document.getElementById('chart').innerHTML = data.status;
    } else {
        var tags = {} // tagName => [{x, y, artists}, ...]
        for (var w_i = data.weeks.length-1; w_i >= 0; w_i--) {
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
                step: 'left',
                pointInterval: 7 * 24 * 3600 * 1000
            });
        }

        $(function () {
            $('#chart').highcharts({
                title: {
                    text: 'Tag History for ' + user
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
                    maxZoom: 7 * 24 * 3600 * 1000
                },
                yAxis: {
                    title: {
                        text: 'plays' 
                    },
                    min: 0
                },
                tooltip: {
                    useHTML: true,
                    crosshairs: true,
                    formatter: function() {
                        return '<b>' + this.series.name + '</b><br/>' +
                            'Week of ' + Highcharts.dateFormat('%a, %b %e, %Y', this.x) + '<br/>' + 
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
                                    lfm_api.get_weeklytrackchart(user, this.x/1000, 
                                        this.x/1000 + 7*24*3600, set_player_songs);
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

    // Setup Youtube player
    var params = { allowScriptAccess: "always" };
    var atts = { id: "ytplayer" };
    swfobject.embedSWF("http://www.youtube.com/v/u6xMzltep_8?enablejsapi=1&playerapiid=ytplayer&version=3",
                       "ytplayer", "300", "200", "8", null, null, params, atts, on_player_load);
    }
}

function set_player_songs(result) {
    if (result.weeklytrackchart && result.weeklytrackchart.track) {
        tracks = result.weeklytrackchart.track;
        $('#player_date').text(Highcharts.dateFormat('%b %e, %Y', 
            parseInt(result.weeklytrackchart['@attr'].from) * 1000));
        play_random();
    } else {
        tracks = null;
        $('#player_date').text('--');
        $('#player_song').text('--');
        // TODO set video to static
    }
}

function play_random() {
    if (tracks) {
        var track = tracks[getRandomInt(0, tracks.length)];
        $('#player_song').text(track.artist['#text'] + ' - ' + track.name);

        youtube_api.search_videos(track.artist['#text'] + ' ' + track.name, 1, set_video);
    } else {
        // TODO set video to static
    }
}

function set_video(result) {
    if (result.feed.entry && result.feed.entry.length > 0) {
        var videoId = result.feed.entry[0]['media$group']['yt$videoid']['$t'];
        ytplayer.loadVideoById(videoId);
    }
}

function on_player_load(e) {
    if (!e.success) {
        document.getElementById("#ytplayer").innerHTML = 
            "You need Flash player 8+ and JavaScript enabled to view this video.";
    } else {
        ytplayer = e.ref;
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
    name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        results = regex.exec(location.search);
    return results == null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}