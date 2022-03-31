var enable_le_buttons = function () {
    $('.visitech button').prop('disabled', false);
}

var disable_le_buttons = function () {
    // $('.visitech button').prop('disabled', true);
}

var disable_project_start_button = function () {
    // $('#visitech-start-btn').prop('disabled', true);
}

var enable_project_start_button = function () {
    $('#visitech-start-btn').prop('disabled', false);
}

var enable_project_start_stop_buttons = function () {
    $('#visitech-start-btn').prop('disabled', false);
    $('#visitech-stop-btn').prop('disabled', false);
}

var disable_project_start_stop_buttons = function () {
    // $('#visitech-start-btn').prop('disabled', true);
    // $('#visitech-stop-btn').prop('disabled', true);
}

$(document).ready(function () {
    // Handles to user inputs
    var LedPowerSliderElement = document.getElementById("visitech-led-power-slider");
    var LedPowerLabelElement = document.getElementById("visitech-led-power-label");
    var exposureElement = document.getElementById("visitech-exposure-txt");

    // Set initial LED power slider label value
    LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

    // Update the LedPowerLabelElement with the current slider value
    LedPowerSliderElement.oninput = function () {
        LedPowerLabelElement.innerHTML = this.value;
    }

    // Light engine control stop button click function
    $("#visitech-stop-btn").click(function () {
        socket.emit("visitech_stop");
    });

    // Exposure text input change function
    $('#visitech-exposure-txt').on('change', function () {
        exposure = exposureElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            exposureElement.classList.remove("is-invalid")
            enable_project_start_stop_buttons();
        } else {
            exposureElement.classList.add("is-invalid")
            disable_project_start_stop_buttons();
        }
    })

    $("#visitech-repeat-chkbx").click(function () {
        var repeatCheckboxElement = document.getElementById("visitech-repeat-chkbx");
        var repeat = Number(!repeatCheckboxElement.checked);
        if (repeat == 0) {
            exposureElement.classList.remove("is-invalid")
            $('#visitech-exposure-txt').prop('disabled', true);
        } else {
            $('#visitech-exposure-txt').prop('disabled', false);
        }
    });

    // Light engine control start button click function
    $("#visitech-start-btn").click(function () {
        var repeatCheckboxElement = document.getElementById("visitech-repeat-chkbx");
        var exposure = exposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = LedPowerSliderElement.value;

        if (!/^\d+$/.test(exposure) && !exposure > 0) {
            if (repeat == 1) {
                exposureElement.classList.add("is-invalid")
                return
            } else {
                exposure = 1
            }
        }
        socket.emit("visitech_start", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    socket.on("update_led_status", function (message) {
        var statusElement = document.getElementById("visitech-status");
        if (message == true) {
            statusElement.classList.remove("invisible")
        } else {
            statusElement.classList.add("invisible")
        }
        $('#visitech-status').prop('disabled', message);
    });

});