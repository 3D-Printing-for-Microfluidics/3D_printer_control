// helper function to update positions on sensors
var update_keyence_positions = function (message) {
    for (let sensor of hardware["keyence"]["sensors"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${sensor}-focus`).innerHTML = message["keyence_" + sensor];
        }
    }
}

$(document).ready(function () {
    socket.on("keyence_done", function (message) {
        update_keyence_positions(message);
    });

    for (let sensor of hardware["keyence"]["sensors"]) {
        $(`.${sensor}-cntrl-txt`).on('change', function () {
            let microns = $(this).val();
            let s = $(this).closest(".container").attr('aria-label');
            let message = { "sensor": s, "microns": microns, "mode": "absolute" };
            socket.emit("keyence_set_setpoint", message);
        });

        $(`.${sensor}-cntrl-btn`).click(function () {
            let microns = $(this).text();
            let s = $(this).closest(".container").attr('aria-label');
            let message = { "sensor": s, "microns": microns, "mode": "relative" };
            socket.emit("keyence_set_setpoint", message);
        });
    }

}); 