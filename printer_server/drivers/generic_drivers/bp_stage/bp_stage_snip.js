var disable_bp_buttons = function () {
    $('.bp button').prop('disabled', true);
}

var enable_bp_buttons = function () {
    $('.bp button').prop('disabled', false);
}

var update_bp_positions = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById(`bp-state`).innerHTML = message["position"];
    }
}

$(document).ready(function () {
    // Enable bp control buttons when current bp motion is complete
    socket.on("bp_done", function (message) {
        update_bp_positions(message)
        enable_bp_buttons();
    });

    // bp control top button click function
    $("#bp-top-btn").click(function () {
        disable_bp_buttons();
        socket.emit("bp_go_to_top");
    });

    $("#bp-home-btn").click(function () {
        disable_bp_buttons();
        socket.emit("bp_home");
    });

    // bp stages text inputs for absolute positioning
    $(`.bp-cntrl-txt`).on('change', function () {
        disable_bp_buttons();
        // Parse button content and construct message
        let distance = $(this).val();
        let axis = "Build Platform";
        let message = { "mode": "absolute", "distance": distance, "axis": axis, "log": true };
        socket.emit("bp_move", message);
    });

    // bp stages buttons for relative positioning
    $(`.bp-cntrl-btn`).click(function () {
        disable_bp_buttons();
        // Parse button content and construct message
        let distance = $(this).text();
        let axis = "Build Platform";
        let message = { "mode": "relative", "distance": distance, "axis": axis, "log": true };
        socket.emit("bp_move", message);
    });
});