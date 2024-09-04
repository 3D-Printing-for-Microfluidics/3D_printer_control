var disable_xy_buttons = function () {
    $('.xy button').prop('disabled', true);
}

var enable_xy_buttons = function () {
    $('.xy button').prop('disabled', false);
}

var update_xy_positions = function (message) {
    for (let stage in hardware["xy_stage"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`xy-${stage}-state`).innerHTML = message[stage]["position"];
        }
    }
}

$(document).ready(function () {
    // Enable xy control buttons when current xy motion is complete
    socket.on("xy_done", function (message) {
        update_xy_positions(message)
        enable_xy_buttons();
    });

    $("#xy-home-btn").click(function () {
        disable_xy_buttons();
        socket.emit("xy_home");
    });

    for (let stage in hardware["xy_stage"]) {
        // xy stages text inputs for absolute positioning
        $(`.xy-${stage}-cntrl-txt`).on('change', function () {
            disable_xy_buttons();
            // Parse button content and construct message
            let distance = $(this).val();
            let axis = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "absolute", "distance": distance, "axis": axis, "log": true };
            socket.emit("xy_move", message);
        });

        // xy stages buttons for relative positioning
        $(`.xy-${stage}-cntrl-btn`).click(function () {
            disable_xy_buttons();
            // Parse button content and construct message
            let distance = $(this).text();
            let axis = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "relative", "distance": distance, "axis": axis, "log": true };
            socket.emit("xy_move", message);
        });
    }
});