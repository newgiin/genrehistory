var user = getParameterByName('user');
var tp = getParameterByName('tp');
var from = getParameterByName('from');
var to = getParameterByName('to');

$('#user_input').val(user);
$('#tp_input').val(tp);
$.getJSON('/tag_graph_data?tp=' + encodeURIComponent(tp) +
    '&user=' + encodeURIComponent(user) +
    '&from=' + encodeURIComponent(from) +
    '&to=' + encodeURIComponent(to)).done(render).fail(disp_error);

$.getJSON('/user_fragments?user=' + encodeURIComponent(user)).done(
    fill_date_select).fail(disp_error);

function render(data, status, jqXHR) {
    var status_div = document.getElementById('status');

    if (data.error) {
        status_div.innerHTML = data.error;
    } else if ('status' in data) {
        if (data.status === 1) {
            status_div.innerHTML = '';
            var status_text = document.createElement('div');
            status_text.innerHTML = 'Data still processing. First time could ' +
                                        'take 10 minutes.';

            var update_time = 'Never';
            if (data.last_updated) {
                update_time = timestampToDate(parseInt(data.last_updated));
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
        render_graph(data);
    }
}


function render_graph(data) {
    var sys = arbor.ParticleSystem(100, 100, 0.5); // create the system with sensible repulsion/stiffness/friction
    sys.parameters({gravity:true}); // use center-gravity to make the graph settle nicely (ymmv)
    sys.renderer = Renderer("#viewport"); // our newly created renderer will have its .init() method called shortly by sys...

    var MAX_FONT = 60;
    var MIN_FONT = 10;
    var MAX_PLAYS = 1;

    if (data.tags.length > 0) {
        MAX_PLAYS = data.tags[0].plays;
    }

    for (var i = 0; i < data.tags.length; i++) {
        var tag = data.tags[i].tag;
        var fs = Math.max(MIN_FONT,
                        parseInt(data.tags[i].plays*MAX_FONT / MAX_PLAYS));
        sys.addNode(tag, {font_size: fs, color: '#3096FC'});

        for (var j = 0; j < data.tags[i].adj.length; j++) {
            var edge = data.tags[i].adj[j];
            var dst = sys.getNode(edge);
            // ensures existing font_sizes not overwritten
            if (!dst) {
                dst = edge;
            }
            sys.addEdge(sys.getNode(tag), dst);
        }
    }

    $('#viewport').css('display', 'block');
    $('#status').css('visibility', 'hidden');
}


function fill_date_select(data) {
    if ('fragments' in data) {
        if (data.fragments.length > 0) {
            $('#from_input').empty();
            $('#to_input').empty();
        }

        for (var i = 0; i < data.fragments.length; i++) {
            var frag = data.fragments[i];

            var option = $('<option value="' + frag.start + '">' +
                timestampToDate(frag.start) + '</option>');
            if (frag.start == from) {
                option.attr('selected', 'selected');
            }
            $('#from_input').append(option);

            /* Use start timestamp as value since
            service uses start dates to uniquely identify fragments.
            technically using 'frag.end' as the value would also
            get the same result, but we use the 'start' timestamp
            for consistency. */
            option = $('<option value="' + frag.start + '">' +
                timestampToDate(frag.end) + '</option>');
            if (frag.start == to) {
                option.attr('selected', 'selected');
            }
            $('#to_input').append(option);
        }
    }
}

function shout_callback(data) {
    if (data.error) {
        alert(data.error);
    } else {
        alert('A shout will be left on your Last.fm profile once the data ' +
            'is ready!');
    }
}

function disp_error(jqxhr, textStatus, error) {
    alert(textStatus + ': ' + error);
}

function getParameterByName(name) {
    name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        results = regex.exec(location.search);
    return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}

function timestampToDate(timestamp) {
    var a = new Date(timestamp * 1000);
    var months = ['Jan','Feb','Mar','Apr','May','Jun',
        'Jul','Aug','Sep','Oct','Nov','Dec'];
    var year = a.getFullYear();
    var month = months[a.getMonth()];
    var date = a.getDate();
    var time = month + ' ' + date + ', ' + year;

    return time;
 }
