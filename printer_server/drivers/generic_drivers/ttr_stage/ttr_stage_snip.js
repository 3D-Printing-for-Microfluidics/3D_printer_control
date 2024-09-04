var disable_ttr_buttons = function () {
    $('.ttr button').prop('disabled', true);
}

var enable_ttr_buttons = function () {
    $('.ttr button').prop('disabled', false);
}

var update_ttr_positions = function (message) {
    for (let stage in manual_controls_data["ttr_stage"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`ttr-${stage}-state`).innerHTML = message[stage]["position"];
        }
    }
}

$(document).ready(function () {
    // Enable ttr control buttons when current ttr motion is complete
    socket.on("ttr_done", function (message) {
        update_ttr_positions(message)
        enable_ttr_buttons();
    });

    $("#ttr-home-btn").click(function () {
        disable_ttr_buttons();
        socket.emit("ttr_home");
    });

    for (let stage in manual_controls_data["ttr_stage"]) {
        // ttr stages text inputs for absolute positioning
        $(`.ttr-${stage}-cntrl-txt`).on('change', function () {
            disable_ttr_buttons();
            // Parse button content and construct message
            let distance = $(this).val();
            let axis = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "absolute", "distance": distance, "axis": axis, "log": true };
            socket.emit("ttr_move", message);
        });

        // ttr stages buttons for relative positioning
        $(`.ttr-${stage}-cntrl-btn`).click(function () {
            disable_ttr_buttons();
            // Parse button content and construct message
            let distance = $(this).text();
            let axis = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "relative", "distance": distance, "axis": axis, "log": true };
            socket.emit("ttr_move", message);
        });
    }
});