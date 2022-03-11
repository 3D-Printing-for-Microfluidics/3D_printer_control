var disable_kdc_motor_buttons = function () {
    $('.kdc-controls button').prop('disabled', true);
}

var enable_kdc_motor_buttons = function () {
    $('.kdc-controls button').prop('disabled', false);
}

var update_dist_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('dist-state').innerHTML = message.distance;
    }
}

// helper function to update positions on all calibration axes
var update_kdc_positions = function (message) {
    update_dist_position(message);
}

$(document).ready(function () {
    // Enable calibration motor buttons and update position labels when current motion is complete
    socket.on("kdc_motor_move_complete", function (message) {
        update_kdc_positions(message);
        enable_kdc_motor_buttons();
    });

    // Calibration motor buttons for homing
    $(".kdc-home-btn").click(function () {
        // Disable calibration motor buttons
        disable_kdc_motor_buttons();
        // Parse button content and construct message
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis };
        // Emit control message with parsed values
        socket.emit("kdc_motor_home", message);
    });

    // Calibration motor text inputs for absolute positioning
    $(".kdc-cntrl-txt").on('change', function () {
        // Disable calibration motor buttons
        disable_kdc_motor_buttons();
        // Parse button content and construct message
        var microns = $(this).val();
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis, "microns": microns, "mode": "absolute", "fast": false, "log": true };
        // Emit control message with parsed values
        socket.emit("kdc_motor_move", message);
    });

    // Calibration motor buttons for relative positioning
    $(".kdc-cntrl-btn").click(function () {
        // Disable calibration motor buttons
        disable_kdc_motor_buttons();
        // Parse button content and construct message
        var microns = $(this).text();
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis, "microns": microns, "mode": "relative", "fast": false, "log": true };
        // Emit control message with parsed values
        socket.emit("kdc_motor_move", message);
    });
});