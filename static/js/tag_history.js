var user = getParameterByName('user');

$('#user_input').val(user);
$('#user_link').attr('href', 'http://last.fm/user/' + encodeURIComponent(user)).text(user);

$.getJSON('/history_data?user=' + encodeURIComponent(user)).done(render).fail(disp_error);

function render(data, status, jqXHR) {
    if (data.error) {
        document.getElementById('chart').innerHTML = data.error;
    } else if (data.status) {
        document.getElementById('chart').innerHTML = data.status;
    } else {
        var tags = {} // # tagName => [{x, y, artists}, ...]
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
            // add zero plays to tags we didn't touch this week
            var week_tags = $.map(week.tags, function(tag_obj) { 
                return tag_obj.tag});
            for (var tag in tags) {
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
    }
}

function disp_error(jqxhr, textStatus, error) {
    alert(textStatus + ': ' + error);
}

function unix2localtime(time) {
    time = parseInt(time, 10);
    var date = new Date(time * 1000);
    return date.toLocaleString();
}

function getParameterByName(name) {
    name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        results = regex.exec(location.search);
    return results == null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}