var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

var update_parameters = function (message) {
    if ($.isEmptyObject(message)) {
        return;
    }
    for (let i = 0; i < message.length; i++) {
        let item = message[i];
        let el = document.getElementById(`${item.machine_name}-state`);
        if (el) {
            el.innerHTML = item.value;
        }
    }
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/calibration");

    socket.on("set_done", function (message) {
        update_parameters(message)
    });

    socket.on("goto_done", function (message) {
        update_parameters(message)
        enable_all_buttons();
    });

    $("#goto").click(function () {
        disable_all_buttons();
        socket.emit("goto");
    });

    for (let i = 0; i < calibration_data.length; i++) {
        let item = calibration_data[i];
        let machine = item.machine_name;
        let group = item.group;
        // text inputs for absolute changes
        $(`.${machine}-cntrl-txt`).on('change', function () {
            // Parse button content and construct message
            let distance = $(this).val();
            let p = $(this).closest(".container").attr('aria-label');
            let g = $(this).closest(".container").data('group');
            let message = { "mode": "absolute", "distance": distance, "parameter": p, "group": g || group };
            socket.emit("set", message);
        });

        // buttons for relative changes
        $(`.${machine}-cntrl-btn`).click(function () {
            // Parse button content and construct message
            let distance = $(this).text();
            let p = $(this).closest(".container").attr('aria-label');
            let g = $(this).closest(".container").data('group');
            let message = { "mode": "relative", "distance": distance, "parameter": p, "group": g || group };
            socket.emit("set", message);
        });
    }

});
