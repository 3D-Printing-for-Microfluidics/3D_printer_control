var disable_acs_buttons = function () {
    $('.acs button').prop('disabled', true);
}

var enable_acs_buttons = function () {
    $('.acs button').prop('disabled', false);
}

var update_acs_positions = function (message) {
    for (var stage in hardware["acs"]["stages"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`acs-${stage}-state`).innerHTML = message[stage];
        }
    }
}

$(document).ready(function () {
    // Enable acs control buttons when current acs motion is complete
    socket.on("acs_done", function (message) {
        update_acs_positions(message)
        enable_acs_buttons();
    });

    // ACS control top button click function
    $("#acs-top-btn").click(function () {
        disable_acs_buttons();
        socket.emit("acs_go_to_top");
    });

    // ACS control bottom button click function
    $("#acs-bottom-btn").click(function () {
        disable_acs_buttons();
        socket.emit("acs_go_to_bottom");
    });

    $("#acs-home-btn").click(function () {
        disable_acs_buttons();
        socket.emit("acs_home");
    });

    for (var stage in hardware["acs"]["stages"]) {
        // ACS stages text inputs for absolute positioning
        $(`.acs-${stage}-cntrl-txt`).on('change', function () {
            disable_acs_buttons();
            // Parse button content and construct message
            var distance = $(this).val();
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "mode": "absolute", "distance": distance, "axis": axis, "log": true };
            socket.emit("acs_move", message);
        });

        // ACS stages buttons for relative positioning
        $(`.acs-${stage}-cntrl-btn`).click(function () {
            disable_acs_buttons();
            // Parse button content and construct message
            var distance = $(this).text();
            var axis = $(this).closest(".container").attr('aria-label');
            var message = { "mode": "relative", "distance": distance, "axis": axis, "log": true };
            socket.emit("acs_move", message);
        });
    }
});