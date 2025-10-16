$(document).ready(function () {
    socket.on("gpio_film_relay_state", function (message) {
        if(message == true){
            $(`#film-on`).prop('checked', true).closest('label').addClass('active');
            $(`#film-off`).prop('checked', false).closest('label').removeClass('active');
        }
        else{
            $(`#film-on`).prop('checked', false).closest('label').removeClass('active');
            $(`#film-off`).prop('checked', true).closest('label').addClass('active');
        }
    });

    $("#film-relay :input").change(function () {
        socket.emit("gpio_switch_film_relay", $(this).parent().text());
    });

    socket.on("gpio_wintech_fan_relay_state", function (message) {
        if(message == true){
            $(`#w-fan-on`).prop('checked', true).closest('label').addClass('active');
            $(`#w-fan-off`).prop('checked', false).closest('label').removeClass('active');
        }
        else{
            $(`#w-fan-on`).prop('checked', false).closest('label').removeClass('active');
            $(`#w-fan-off`).prop('checked', true).closest('label').addClass('active');
        }
    });

    $("#w-fan-relay :input").change(function () {
        socket.emit("gpio_switch_wintech_fan_relay", $(this).parent().text());
    });
});