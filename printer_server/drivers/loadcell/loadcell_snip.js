$(document).ready(function () {
    $("#loadcell_graph_mode :input").change(function () {
        socket.emit("loadcell_set_graph_mode", $(this).parent().text());
    });

    $("#loadcell_graph_autoscale :input").change(function () {
        socket.emit("loadcell_set_graph_autoscale", $(this).parent().text());
    });

});