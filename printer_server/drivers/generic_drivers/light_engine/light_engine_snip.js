var enable_button = function (id) {
    $(id).prop('disabled', false);
    $(id).addClass('btn-outline-info');
    $(id).removeClass('btn-outline-secondary');
}

var disable_button = function (id) {
    $(id).prop('disabled', true);
    $(id).removeClass('btn-outline-info');
    $(id).addClass('btn-outline-secondary');
}

$(document).ready(function () {
    for (let light_engine in manual_controls_data["light_engines"]) {
        // Handles to user inputs
        let LedPowerSliderElement = document.getElementById(`${light_engine}-led-power-slider`);
        let LedPowerLabelElement = document.getElementById(`${light_engine}-led-power-label`);
        let ExposureElement = document.getElementById(`${light_engine}-exposure-txt`);

        // Set initial LED power slider label value
        LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

        // Update the LedPowerLabelElement with the current slider value
        LedPowerSliderElement.oninput = function () {
            LedPowerLabelElement.innerHTML = this.value;
        }

        // Light engine control stop button click function
        $(`#${light_engine}-stop-btn`).click(function () {
            socket.emit("light_engine_stop", light_engine);
        });

        // Exposure text input change function
        $(`#${light_engine}-exposure-txt`).on('change', function () {
            exposure = ExposureElement.value;

            // Validate user input. Only allows positive integers > 0
            if (/^\d+$/.test(exposure) && exposure > 0) {
                ExposureElement.classList.remove("is-invalid")
                enable_button(`#${light_engine}-start-btn`);
            } else {
                ExposureElement.classList.add("is-invalid")
                disable_button(`#${light_engine}-start-btn`);
            }
        })

        $(`#${light_engine}-repeat-chkbx`).click(function () {
            let repeatCheckboxElement = document.getElementById(`${light_engine}-repeat-chkbx`);
            let repeat = Number(!repeatCheckboxElement.checked);
            if (repeat == 0) {
                ExposureElement.classList.remove("is-invalid")
                $(`#${light_engine}-exposure-txt`).prop('disabled', true);
            } else {
                $(`#${light_engine}-exposure-txt`).prop('disabled', false);
            }
        });

        // Light engine control start button click function
        $(`#${light_engine}-start-btn`).click(function () {
            let repeatCheckboxElement = document.getElementById(`${light_engine}-repeat-chkbx`);
            let exposure = ExposureElement.value;
            let repeat = Number(!repeatCheckboxElement.checked);
            let ledPower = LedPowerSliderElement.value;

            if (!/^\d+$/.test(exposure) && !exposure > 0) {
                if (repeat == 1) {
                    ExposureElement.classList.add("is-invalid")
                    return
                } else {
                    exposure = 1
                }
            }

            let led_1_element = document.getElementById(`led_1`);
            let led_1_checked = false;
            if (led_1_element != null) {
                led_1_checked = led_1_element.classList.contains("active");
            }

            console.log({ "repeat": repeat, "exposure": exposure, "ledPower": ledPower, "led": led_1_checked })
            socket.emit("light_engine_start", { "light_engine": light_engine, "repeat": repeat, "exposure": exposure, "ledPower": ledPower, "led": led_1_checked });
        });
    }
    socket.on("light_engine_update_led_state", function (message) {
        let light_engine = message["light_engine"];
        let status = message["status"];
        let statusElement = document.getElementById(`${light_engine}-status`);
        if (status == true) {
            statusElement.classList.remove("invisible")
        } else {
            statusElement.classList.add("invisible")
        }
        $(`#${light_engine}-status`).prop('disabled', status);
    });
});