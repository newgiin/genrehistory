var user = getParameterByName('user');
var tp = getParameterByName('tp');
var frag_chart = [];
var curr_frag = -1;
var sys = null;

var MAX_FONT = 60;
var MIN_FONT = 10;

$('#user_input').val(user);
$('#tp_input').val(tp);
$.getJSON('/tag_graph_data?tp=' + encodeURIComponent(tp) +
    '&user=' + encodeURIComponent(user)).done(render).fail(disp_error);

$.getJSON('/user_fragments?user=' + encodeURIComponent(user)).done(
    populate_frag_chart).fail(disp_error);

function render(data, status, jqXHR) {
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
    sys = arbor.ParticleSystem(100, 100, 0.5); // create the system with sensible repulsion/stiffness/friction
    sys.parameters({gravity:true}); // use center-gravity to make the graph settle nicely (ymmv)
    sys.renderer = Renderer("#viewport"); // our newly created renderer will have its .init() method called shortly by sys...

    var max_plays = 1;

    if (data.tags.length > 0) {
        max_plays = data.tags[0].plays;
    }

    for (var i = 0; i < data.tags.length; i++) {
        var tag = data.tags[i].tag;
        var fs = Math.max(MIN_FONT,
                        parseInt(MAX_FONT * data.tags[i].plays / max_plays));
        var node = sys.addNode(tag, {font_size: fs, color: '#3096FC'});

        for (var j = 0; j < data.tags[i].adj.length; j++) {
            var edge = data.tags[i].adj[j];
            var dst = sys.getNode(edge);
            // ensures existing font_sizes not overwritten
            if (!dst) {
                dst = edge;
            }
            sys.addEdge(node, dst);
        }
    }
    console.log(sys.getEdgesFrom('electronic').length);
    $('#viewport').css('display', 'block');
    $('#status').css('visibility', 'hidden');
}


function populate_frag_chart(data) {
    if ('fragments' in data) {
        frag_chart = data.fragments;
        $('#next_frag_btn').click(function() {
            if (curr_frag < frag_chart.length-1) {
                curr_frag++;
                if (curr_frag === 0) {
                    // clear graph
                    sys.eachNode(function(node) {
                        sys.pruneNode(node);
                    });
                }
                // graft
                $.getJSON('/tag_graph_data?tp=' + encodeURIComponent(tp) +
                    '&user=' + encodeURIComponent(user) +
                    '&to=' + frag_chart[curr_frag].start).done(
                    update_graph).fail(disp_error);
            }
        });
    }
}

function update_graph(data) {
    var max_plays = 1;

    if (data.tags.length > 0) {
        max_plays = data.tags[0].plays;
    }

    for (var i = 0; i < data.tags.length; i++) {
        var tag = data.tags[i].tag;
        var fs = Math.max(MIN_FONT,
                        parseInt(MAX_FONT * data.tags[i].plays / max_plays));
        var node = sys.getNode(tag);
        if (!node) {
            sys.addNode(tag, {font_size: fs, color: '#3096FC'});
        } else {
            sys.tweenNode(tag, 1, {font_size: fs});
        }
    }

    for (var i = 0; i < data.tags.length; i++) {
        var tag_obj = data.tags[i];
        for (var j = 0; j < tag_obj.adj.length; j++) {
            sys.addEdge(sys.getNode(tag_obj.tag),
                sys.getNode(tag_obj.adj[j]));
        }
    }
    $('#interval_txt').text('To: ' + timestampToDate(frag_chart[curr_frag].end));
    console.log(sys.getEdgesFrom('electronic').length);
    var edges = sys.getEdgesFrom('electronic');
    for (var i = 0; i < edges.length; i++) {
        console.log(edges[i].target.name);
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
