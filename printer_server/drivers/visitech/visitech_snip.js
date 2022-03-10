var enable_le_buttons = function () {
    $('.light-engine button').prop('disabled', false);
}

var disable_le_buttons = function () {
    // $('.light-engine button').prop('disabled', true);
}

var disable_project_start_button = function () {
    // $('#le-start-btn').prop('disabled', true);
}

var enable_project_start_button = function () {
    $('#le-start-btn').prop('disabled', false);
}

var enable_project_start_stop_buttons = function () {
    $('#le-start-btn').prop('disabled', false);
    $('#le-stop-btn').prop('disabled', false);
}

var disable_project_start_stop_buttons = function () {
    // $('#le-start-btn').prop('disabled', true);
    // $('#le-stop-btn').prop('disabled', true);
}

$(document).ready(function () {
    // Handles to user inputs
    var LedPowerSliderElement = document.getElementById("led-power-slider");
    var LedPowerLabelElement = document.getElementById("led-power-label");
    var exposureElement = document.getElementById("exposure-txt");

    // Set initial LED power slider label value
    LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

    // Update the LedPowerLabelElement with the current slider value
    LedPowerSliderElement.oninput = function () {
        LedPowerLabelElement.innerHTML = this.value;
    }

    // Light engine control stop button click function
    $("#le-stop-btn").click(function () {
        socket.emit("light_engine_stop");
    });

    // Exposure text input change function
    $('#exposure-txt').on('change', function () {
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

    // Light engine control start button click function
    $("#le-start-btn").click(function () {
        var repeatCheckboxElement = document.getElementById("repeat-chkbx");
        var exposure = exposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = LedPowerSliderElement.value;
        socket.emit("light_engine_start", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    
});
