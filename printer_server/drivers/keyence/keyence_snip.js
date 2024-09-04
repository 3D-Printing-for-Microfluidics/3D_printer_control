// helper function to update positions on sensors
var update_keyence_positions = function (message) {
    for (let sensor of manual_controls_data["keyence"]["sensors"]) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${sensor}-focus`).innerHTML = message["keyence_" + sensor];
        }
    }
}

$(document).ready(function () {

}); 