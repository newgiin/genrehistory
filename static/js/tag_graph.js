var user = getParameterByName('user');
var tp = getParameterByName('tp');

$('#user_input').val(user);
$('#tp_input').val(tp);
$.getJSON('/tag_graph_data?tp=' + encodeURIComponent(tp) + '&user=' + encodeURIComponent(user)).done(render).fail(disp_error);

function render(data, status, jqXHR) {
    if (data.error) {
        document.getElementById('status').innerHTML = data.error;
    } else if (data.status) {
        document.getElementById('status').innerHTML = data.status;
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
            sys.addNode(tag, {font_size: fs});

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

function disp_error(jqxhr, textStatus, error) {
    alert(textStatus + ': ' + error);
}

function getParameterByName(name) {
    name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        results = regex.exec(location.search);
    return results == null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}