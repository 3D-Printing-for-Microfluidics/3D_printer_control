var disable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', true);
}

var enable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', false);
}

var update_position = function (message, axis) {
    if (!$.isEmptyObject(message)) {
        document.getElementById(`${axis}-state`).innerHTML = message[axis];
    }
}

// helper function to update positions on all calibration axes
var update_positions = function (message) {
    for (var a of axes) {
        a = a.toLowerCase()
        update_position(message, a);
    }
}

$(document).ready(function () {
    // Enable calibration motor buttons and update position labels when current motion is complete
    socket.on("tiptilt_motor_move_complete", function (message) {
        update_positions(message);
        enable_tiptilt_motor_buttons();
    });

    for (var a of axes) {
        a = a.toLowerCase();
        // Calibration motor buttons for homing
        $(`.${a}-home-btn`).click(function () {
            // Disable calibration motor buttons
            disable_tiptilt_motor_buttons();
            // Parse button content and construct message
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "axis": axis };
            // Emit control message with parsed values
            socket.emit("tiptilt_motor_home", message);
        });

        // Calibration motor text inputs for absolute positioning
        $(`.${a}-cntrl-txt`).on('change', function () {
            // Disable calibration motor buttons
            disable_tiptilt_motor_buttons();
            // Parse button content and construct message
            var microns = $(this).val();
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "axis": axis, "microns": microns, "mode": "absolute", "fast": false, "log": true };
            // Emit control message with parsed values
            socket.emit("tiptilt_motor_move", message);
        });

        // Calibration motor buttons for relative positioning
        $(`.${a}-cntrl-btn`).click(function () {
            // Disable calibration motor buttons
            disable_tiptilt_motor_buttons();
            // Parse button content and construct message
            var microns = $(this).text();
            var axis = $(this).closest(".container").attr('aria-label');
            var fast = document.getElementById("quick_move").checked;
            console.log(fast)
            var message = { "axis": axis, "microns": microns, "mode": "relative", "fast": fast, "log": true };
            // Emit control message with parsed values
            socket.emit("tiptilt_motor_move", message);
        });
    }

});