var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

var update_parameters = function (message) {
    for (let parameter in calibration_data) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${parameter.replace(' ', '-')}-state`).innerHTML = message[parameter];
        }
    }
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/calibration");

    socket.on("set_done", function (message) {
        update_parameters(message)
    });

    for (let parameter in calibration_data) {
        parameter = parameter.replace(' ', '-');
        // text inputs for absolute changes
        $(`.${parameter}-cntrl-txt`).on('change', function () {
            // Parse button content and construct message
            let distance = $(this).val();
            let p = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "absolute", "distance": distance, "parameter": p };
            socket.emit("set", message);
        });

        // buttons for relative changes
        $(`.${parameter}-cntrl-btn`).click(function () {
            // Parse button content and construct message
            let distance = $(this).text();
            let p = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "relative", "distance": distance, "parameter": p };
            socket.emit("set", message);
        });
    }

});
