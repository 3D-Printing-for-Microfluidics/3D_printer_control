var disable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', true);
}

var enable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', false);
}

var update_tip_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('tip-state').innerHTML = message.tip;
    }
}

var update_tilt_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('tilt-state').innerHTML = message.tilt;
    }
}

// helper function to update positions on all calibration axes
var update_positions = function (message) {
    update_tip_position(message);
    update_tilt_position(message);
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");

        // Enable calibration motor buttons and update position labels when current motion is complete
    socket.on("tiptilt_motor_move_complete", function (message) {
        update_positions(message);
        enable_tiptilt_motor_buttons();
    });

    // Calibration motor buttons for homing
    $(".tt-home-btn").click(function () {
        // Disable calibration motor buttons
        disable_tiptilt_motor_buttons();
        // Parse button content and construct message
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis };
        // Emit control message with parsed values
        socket.emit("tiptilt_motor_home", message);
    });

    // Calibration motor text inputs for absolute positioning
    $(".tt-cntrl-txt").on('change', function () {
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
    $(".tt-cntrl-btn").click(function () {
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

});