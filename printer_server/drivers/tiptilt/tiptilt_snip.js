var disable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', true);
}

var enable_tiptilt_motor_buttons = function () {
    $('.tiptilt-controls button').prop('disabled', false);
}

// helper function to update positions on all calibration axes
var update_tiptilt_positions = function (message) {
    for (let axis of axes) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${axis}-state`).innerHTML = message[axis];
        }
    }
}

$(document).ready(function () {
    // Enable calibration motor buttons and update position labels when current motion is complete
    socket.on("tiptilt_done", function (message) {
        update_tiptilt_positions(message);
        enable_tiptilt_motor_buttons();
    });

    // Calibration motor buttons for homing
    $(".tt-home-btn").click(function () {
        // Disable calibration motor buttons
        disable_tiptilt_motor_buttons();
        // Emit control message with parsed values
        socket.emit("tiptilt_motor_home");
    });

    for (let a of axes) {
        // Calibration motor text inputs for absolute positioning
        $(`.${a}-cntrl-txt`).on('change', function () {
            // Disable calibration motor buttons
            disable_tiptilt_motor_buttons();
            // Parse button content and construct message
            let mrad = $(this).val();
            let axis = $(this).closest(".container").attr('aria-label');
            let fast = document.getElementById(`${axis}_quick_move`).classList.contains("active");
            console.log(fast)
            let message = { "axis": axis, "mrad": mrad, "mode": "absolute", "fast": fast, "log": true };
            // Emit control message with parsed values
            socket.emit("tiptilt_motor_move", message);
        });

        // Calibration motor buttons for relative positioning
        $(`.${a}-cntrl-btn`).click(function () {
            // Disable calibration motor buttons
            disable_tiptilt_motor_buttons();
            // Parse button content and construct message
            let mrad = $(this).text();
            let axis = $(this).closest(".container").attr('aria-label');
            let fast = document.getElementById(`${axis}_quick_move`).classList.contains("active");
            console.log(fast)
            console.log(document.getElementById(`${axis}_quick_move`).classList.contains("active"))
            let message = { "axis": axis, "mrad": mrad, "mode": "relative", "fast": fast, "log": true };
            // Emit control message with parsed values
            socket.emit("tiptilt_motor_move", message);
        });
    }

});