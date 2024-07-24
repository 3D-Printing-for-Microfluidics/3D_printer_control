$(document).ready(function () {
    $("#film-relay :input").change(function () {
        socket.emit("gpio_switch_film_relay", $(this).parent().text());
    });
});