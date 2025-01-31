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
});