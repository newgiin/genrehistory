var Renderer = function(canvas){
  var canvas = $(canvas).get(0)
  var gfx = arbor.Graphics(canvas);
  var ctx = canvas.getContext("2d");
  var particleSystem

  var that = {
    init:function(system){
      particleSystem = system
      particleSystem.screenSize(canvas.width, canvas.height) 
      particleSystem.screenPadding(80)
      
      that.initMouseHandling()
    },
    
    redraw:function(){
      ctx.fillStyle = "white"
      ctx.fillRect(0,0, canvas.width, canvas.height)
      
      var nodeBoxes = {}
      particleSystem.eachNode(function(node, pt){
        // node: {mass:#, p:{x,y}, name:"", data:{}}
        // pt:   {x:#, y:#}  node position in screen coords

        // determine the box size and round off the coords if we'll be 
        // drawing a text label (awful alignment jitter otherwise...)
        var label = node.name
        var font_size = 10
        if (node.data.font_size) {
          font_size = node.data.font_size;
        }

        // draw the text
        if (label){
          ctx.font = font_size + "px Helvetica"
          ctx.textAlign = "center"
          ctx.fillStyle = '#333333'
          ctx.fillText(label||"", pt.x, pt.y+4)
          ctx.fillText(label||"", pt.x, pt.y+4)
        }

        var w = ctx.measureText(""+label).width + 10

        var h = parseInt(font_size * 1.2)
        // draw a rectangle centered at pt
        if (node.data.color) 
          ctx.fillStyle = node.data.color
        else 
          ctx.fillStyle = "rgba(0,0,0,.2)"

        if (node.data.color=='none') 
          ctx.fillStyle = "white"

        var box_origin = {x: pt.x-w/2, y: pt.y-parseInt(h*.7)}
        gfx.rect(box_origin.x, box_origin.y, w, h, 4, {fill:ctx.fillStyle})
        nodeBoxes[node.name] = [box_origin.x, box_origin.y, w, h]

        // draw the text
        if (label){
          ctx.font = font_size + "px Helvetica"
          ctx.textAlign = "center"
          ctx.fillStyle = '#333'
          ctx.fillText(label||"", pt.x, pt.y+4)
          ctx.fillText(label||"", pt.x, pt.y+4)
        }
      })  

      particleSystem.eachEdge(function(edge, pt1, pt2){
        var weight = edge.data.weight
        var color = edge.data.color

        if (!color || (""+color).match(/^[ \t]*$/)) color = null

        // find the start point
        var tail = intersect_line_box(pt1, pt2, nodeBoxes[edge.source.name])
        var head = intersect_line_box(tail, pt2, nodeBoxes[edge.target.name])

        ctx.save() 
          ctx.beginPath()
          ctx.lineWidth = (!isNaN(weight)) ? parseFloat(weight) : 1
          ctx.strokeStyle = (color) ? color : "#ccc"
          ctx.fillStyle = null

          ctx.moveTo(tail.x, tail.y)
          ctx.lineTo(head.x, head.y)
          ctx.stroke()
        ctx.restore()
      })        
    },
    
    initMouseHandling:function(){
      // no-nonsense drag and drop (thanks springy.js)
      var dragged = null;

      // set up a handler object that will initially listen for mousedowns then
      // for moves and mouseups while dragging
      var handler = {
        clicked:function(e){
          var pos = $(canvas).offset();
          _mouseP = arbor.Point(e.pageX-pos.left, e.pageY-pos.top)
          dragged = particleSystem.nearest(_mouseP);

          if (dragged && dragged.node !== null){
            // while we're dragging, don't let physics move the node
            dragged.node.fixed = true
          }

          $(canvas).bind('mousemove', handler.dragged)
          $(window).bind('mouseup', handler.dropped)

          return false
        },
        dragged:function(e){
          var pos = $(canvas).offset();
          var s = arbor.Point(e.pageX-pos.left, e.pageY-pos.top)

          if (dragged && dragged.node !== null){
            var p = particleSystem.fromScreen(s)
            dragged.node.p = p
          }

          return false
        },

        dropped:function(e){
          if (dragged===null || dragged.node===undefined) return
          if (dragged.node !== null) dragged.node.fixed = false
          dragged.node.tempMass = 1000
          dragged = null
          $(canvas).unbind('mousemove', handler.dragged)
          $(window).unbind('mouseup', handler.dropped)
          _mouseP = null
          return false
        }
      }
      
      // start listening
      $(canvas).mousedown(handler.clicked);

    },
    
  }

  // helpers for figuring out where to draw arrows (thanks springy.js)
  var intersect_line_line = function(p1, p2, p3, p4)
  {
    var denom = ((p4.y - p3.y)*(p2.x - p1.x) - (p4.x - p3.x)*(p2.y - p1.y));
    if (denom === 0) return false // lines are parallel
    var ua = ((p4.x - p3.x)*(p1.y - p3.y) - (p4.y - p3.y)*(p1.x - p3.x)) / denom;
    var ub = ((p2.x - p1.x)*(p1.y - p3.y) - (p2.y - p1.y)*(p1.x - p3.x)) / denom;

    if (ua < 0 || ua > 1 || ub < 0 || ub > 1)  return false
    return arbor.Point(p1.x + ua * (p2.x - p1.x), p1.y + ua * (p2.y - p1.y));
  }

  var intersect_line_box = function(p1, p2, boxTuple)
  {
    var p3 = {x:boxTuple[0], y:boxTuple[1]},
        w = boxTuple[2],
        h = boxTuple[3]

    var tl = {x: p3.x, y: p3.y};
    var tr = {x: p3.x + w, y: p3.y};
    var bl = {x: p3.x, y: p3.y + h};
    var br = {x: p3.x + w, y: p3.y + h};

    return intersect_line_line(p1, p2, tl, tr) ||
          intersect_line_line(p1, p2, tr, br) ||
          intersect_line_line(p1, p2, br, bl) ||
          intersect_line_line(p1, p2, bl, tl) ||
          false
  }

  return that
}