// helper function to update positions on sensors
var update_keyence_positions = function (message) {
    for (let sensor of manual_controls_data["keyence"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${sensor}-value`).innerHTML = message[sensor] + " um";
        }
    }
}

$(document).ready(function () {
    socket.on("keyence_update", function (message) {
        update_keyence_positions(message)
    });
}); 