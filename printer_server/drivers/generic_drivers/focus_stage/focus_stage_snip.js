var disable_focus_buttons = function () {
    $('.focus button').prop('disabled', true);
}

var enable_focus_buttons = function () {
    $('.focus button').prop('disabled', false);
}

var update_focus_positions = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById(`focus-state`).innerHTML = message["position"];
    }
}

$(document).ready(function () {
    // Enable focus control buttons when current focus motion is complete
    socket.on("focus_done", function (message) {
        update_focus_positions(message)
        enable_focus_buttons();
    });

    $("#focus-home-btn").click(function () {
        disable_focus_buttons();
        socket.emit("focus_home");
    });

    // focus stages text inputs for absolute positioning
    $(`.focus-cntrl-txt`).on('change', function () {
        disable_focus_buttons();
        // Parse button content and construct message
        let distance = $(this).val();
        let message = { "mode": "absolute", "distance": distance, "log": true };
        socket.emit("focus_move", message);
    });

    // focus stages buttons for relative positioning
    $(`.focus-cntrl-btn`).click(function () {
        disable_focus_buttons();
        // Parse button content and construct message
        let distance = $(this).text();
        let message = { "mode": "relative", "distance": distance, "log": true };
        socket.emit("focus_move", message);
    });
});