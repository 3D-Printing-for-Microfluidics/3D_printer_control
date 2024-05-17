var disable_galil_buttons = function () {
    $('.galil button').prop('disabled', true);
}

var enable_galil_buttons = function () {
    $('.galil button').prop('disabled', false);
}

var update_galil_positions = function (message) {
    for (var stage in hardware["galil"]["stages"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`galil-${stage}-state`).innerHTML = message[stage];
        }
    }
}

$(document).ready(function () {
    // Enable galil control buttons when current galil motion is complete
    socket.on("galil_done", function (message) {
        update_galil_positions(message)
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
        disable_galil_buttons();
        socket.emit("galil_home");
    });

    for (var stage in hardware["galil"]["stages"]) {
        // Galil stages text inputs for absolute positioning
        $(`.galil-${stage}-cntrl-txt`).on('change', function () {
            disable_galil_buttons();
            // Parse button content and construct message
            var distance = $(this).val();
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "mode": "absolute", "distance": distance, "axis": axis, "log": true };
            socket.emit("galil_move", message);
        });

        // Galil stages buttons for relative positioning
        $(`.galil-${stage}-cntrl-btn`).click(function () {
            disable_galil_buttons();
            // Parse button content and construct message
            var distance = $(this).text();
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "mode": "relative", "distance": distance, "axis": axis, "log": true };
            socket.emit("galil_move", message);
        });
    }
});