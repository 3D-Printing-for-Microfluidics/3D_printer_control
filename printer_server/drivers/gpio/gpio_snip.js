$(document).ready(function () {
    $("#film-relay :input").change(function () {
        socket.emit("film_relay_mode", $(this).parent().text());
    });
});