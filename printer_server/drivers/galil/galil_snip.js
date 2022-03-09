var disable_galil_buttons = function () {
    // $('.galil button').prop('disabled', true);
}

var enable_galil_buttons = function () {
    $('.galil button').prop('disabled', false);
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");

    // Enable galil control buttons when current galil motion is complete
    socket.on("galil_done", function () {
        enable_galil_buttons();
    });

    // Galil control top button click function
    $("#galil-top-btn").click(function () {
        disable_galil_buttons();
        socket.emit("galil_go_to_top");
    });

    // Galil control bottom button click function
    $("#galil-bottom-btn").click(function () {
        disable_galil_buttons();
        socket.emit("galil_go_to_bottom");
    });

    $("#galil-home-btn").click(function () {
        socket.emit("galil_home");
    });
});