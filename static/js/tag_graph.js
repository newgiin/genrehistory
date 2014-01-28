var user = getParameterByName('user');
var tp = getParameterByName('tp');

$('#user_input').val(user);
$('#tp_input').val(tp);
$.getJSON('/tag_graph_data?tp=' + encodeURIComponent(tp) + '&user=' + encodeURIComponent(user)).done(render).fail(disp_error);

function render(data, status, jqXHR) {
    var status_div = document.getElementById('status');

    if (data.error) {
        status_div.innerHTML = data.error;
    } else if ('status' in data) {
        if (data.status == 1) {
            status_div.innerHTML = '';
            var status_text = document.createElement('div');
            status_text.innerHTML = 'Data still processing. First time could ' + 
                                        'take > 10 minutes.';

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
        var sys = arbor.ParticleSystem(100, 100, 0.5) // create the system with sensible repulsion/stiffness/friction
        sys.parameters({gravity:true}) // use center-gravity to make the graph settle nicely (ymmv)
        sys.renderer = Renderer("#viewport") // our newly created renderer will have its .init() method called shortly by sys...

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
    return results == null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}