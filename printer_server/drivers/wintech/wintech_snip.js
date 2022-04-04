var enable_wintech_start_stop_buttons = function () {
    $('#wintech-start-btn').prop('disabled', false);
    $('#wintech-stop-btn').prop('disabled', false);
}

var disable_wintech_start_stop_buttons = function () {
    $('#wintech-start-btn').prop('disabled', true);
    $('#wintech-stop-btn').prop('disabled', true);
}

$(document).ready(function () {
    // Handles to user inputs
    var WintechLedPowerSliderElement = document.getElementById("wintech-led-power-slider");
    var WintechLedPowerLabelElement = document.getElementById("wintech-led-power-label");
    var WintechExposureElement = document.getElementById("wintech-exposure-txt");

    // Set initial LED power slider label value
    WintechLedPowerLabelElement.innerHTML = WintechLedPowerSliderElement.value; // Display the default slider value

    // Update the WintechLedPowerLabelElement with the current slider value
    WintechLedPowerSliderElement.oninput = function () {
        WintechLedPowerLabelElement.innerHTML = this.value;
    }

    // Light engine control stop button click function
    $("#wintech-stop-btn").click(function () {
        socket.emit("wintech_stop");
    });

    // Exposure text input change function
    $('#wintech-exposure-txt').on('change', function () {
        exposure = WintechExposureElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            WintechExposureElement.classList.remove("is-invalid")
            enable_wintech_start_stop_buttons();
        } else {
            WintechExposureElement.classList.add("is-invalid")
            disable_wintech_start_stop_buttons();
        }
    })

    $("#wintech-repeat-chkbx").click(function () {
        var repeatCheckboxElement = document.getElementById("wintech-repeat-chkbx");
        var repeat = Number(!repeatCheckboxElement.checked);
        if (repeat == 0) {
            WintechExposureElement.classList.remove("is-invalid")
            $('#wintech-exposure-txt').prop('disabled', true);
        } else {
            $('#wintech-exposure-txt').prop('disabled', false);
        }
    });

    // Light engine control start button click function
    $("#wintech-start-btn").click(function () {
        var repeatCheckboxElement = document.getElementById("wintech-repeat-chkbx");
        var exposure = WintechExposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = WintechLedPowerSliderElement.value;

        if (!/^\d+$/.test(exposure) && !exposure > 0) {
            if (repeat == 1) {
                WintechExposureElement.classList.add("is-invalid")
                return
            } else {
                exposure = 1
            }
        }
        socket.emit("wintech_start", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    socket.on("update_wintech_led_status", function (message) {
        var statusElement = document.getElementById("wintech-status");
        if (message == true) {
            statusElement.classList.remove("invisible")
        } else {
            statusElement.classList.add("invisible")
        }
        $('#wintech-status').prop('disabled', message);
    });

});