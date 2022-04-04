var enable_visitech_start_stop_buttons = function () {
    $('#visitech-start-btn').prop('disabled', false);
    $('#visitech-stop-btn').prop('disabled', false);
}

var disable_visitech_start_stop_buttons = function () {
    $('#visitech-start-btn').prop('disabled', true);
    $('#visitech-stop-btn').prop('disabled', true);
}

$(document).ready(function () {
    // Handles to user inputs
    var VisitechLedPowerSliderElement = document.getElementById("visitech-led-power-slider");
    var VisitechLedPowerLabelElement = document.getElementById("visitech-led-power-label");
    var VisitechExposureElement = document.getElementById("visitech-exposure-txt");

    // Set initial LED power slider label value
    VisitechLedPowerLabelElement.innerHTML = VisitechLedPowerSliderElement.value; // Display the default slider value

    // Update the VisitechLedPowerLabelElement with the current slider value
    VisitechLedPowerSliderElement.oninput = function () {
        VisitechLedPowerLabelElement.innerHTML = this.value;
    }

    // Light engine control stop button click function
    $("#visitech-stop-btn").click(function () {
        socket.emit("visitech_stop");
    });

    // Exposure text input change function
    $('#visitech-exposure-txt').on('change', function () {
        exposure = VisitechExposureElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            VisitechExposureElement.classList.remove("is-invalid")
            enable_visitech_start_stop_buttons();
        } else {
            VisitechExposureElement.classList.add("is-invalid")
            disable_visitech_start_stop_buttons();
        }
    })

    $("#visitech-repeat-chkbx").click(function () {
        var repeatCheckboxElement = document.getElementById("visitech-repeat-chkbx");
        var repeat = Number(!repeatCheckboxElement.checked);
        if (repeat == 0) {
            VisitechExposureElement.classList.remove("is-invalid")
            $('#visitech-exposure-txt').prop('disabled', true);
        } else {
            $('#visitech-exposure-txt').prop('disabled', false);
        }
    });

    // Light engine control start button click function
    $("#visitech-start-btn").click(function () {
        var repeatCheckboxElement = document.getElementById("visitech-repeat-chkbx");
        var exposure = VisitechExposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = VisitechLedPowerSliderElement.value;

        if (!/^\d+$/.test(exposure) && !exposure > 0) {
            if (repeat == 1) {
                VisitechExposureElement.classList.add("is-invalid")
                return
            } else {
                exposure = 1
            }
        }
        socket.emit("visitech_start", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    socket.on("update_visitech_led_status", function (message) {
        var statusElement = document.getElementById("visitech-status");
        if (message == true) {
            statusElement.classList.remove("invisible")
        } else {
            statusElement.classList.add("invisible")
        }
        $('#visitech-status').prop('disabled', message);
    });

});