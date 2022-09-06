$(document).ready(function () {
    $("#fan-relay :input").change(function () {
        socket.emit("fan_relay_mode", $(this).parent().text());
    });
    $("#film-relay :input").change(function () {
        socket.emit("film_relay_mode", $(this).parent().text());
    });
});