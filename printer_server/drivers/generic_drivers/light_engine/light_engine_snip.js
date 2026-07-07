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

var highlight_button = function (id) {
    $(id).addClass('active');
}

var unhighlight_button = function (id) {
    $(id).removeClass('active');
}

$(document).ready(function () {
    // Once once upload is complete, re-enable upload controls
    socket.on("light_engine_image_uploaded", function (le) {
        let filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.remove("is-invalid")
        // enable_upload_button(le);
    });

    // If a bad file was uploaded, disable upload options
    socket.on("light_engine_image_bad", function (le) {
        let filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.add("is-invalid")
        enable_upload_button(le);
    });

    socket.on('light_engine_load', function(message) {
        for (let le in manual_controls_data["light_engines"]) {
            let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
            checkboxElement.checked = message[le];
        }
    });

    socket.on('light_engine_previews', function(message) {
        for (let le in manual_controls_data["light_engines"]) {
            var img = document.getElementById(`${le}-preview`);
            if (message[le]) {
                img.src = 'data:image/jpeg;base64,' + message[le];
            }
            img.style.display = 'inline';
        }
    });

    socket.on('light_engine_done', function(message) {
        for (const [le, data] of Object.entries(message)) {
            var img = document.getElementById(`${le}-preview`);
            if (data) {
                img.src = 'data:image/jpeg;base64,' + data;
            }
            img.style.display = 'inline';
        }
    });
    for (let le in manual_controls_data["light_engines"]) {
        disable_button(`#${le}-upload-btn`);

        // Fuction to get led index from led button group
        let get_led_index = function (le) {
            let activeButton = document.querySelector(
                `#${le}-led-group .active`
            );
            if (activeButton === null) {
                return 0;
            }
            return parseInt(activeButton.dataset.ledIndex, 10);
        }

        document.getElementById(`${le}-file-picker`).addEventListener('change', function (event) {
            filePickerElement = event.currentTarget
            const curFiles = filePickerElement.files;
            if (curFiles.length === 0) {
                disable_button(`#${le}-upload-btn`);
            } else {
                enable_button(`#${le}-upload-btn`);
            }
        });

        // Correction button click function
        $(`#${le}-correction-chkbx`).on("click", function (e) {
            let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            let led_index = get_led_index(le);

            socket.emit("light_engine_grayscale_correction", { "light_engine": le, "correction":  correction, "led": led_index });
        });

        let ledGroup = document.getElementById(`${le}-led-group`);
        if (ledGroup != null) {
            $(ledGroup).on("click", ".btn", function () {
                let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
                let correction = Number(checkboxElement.checked);

                setTimeout(function () {
                    socket.emit("light_engine_led_changed", {
                        "light_engine": le,
                        "correction": correction,
                        "led": get_led_index(le)
                    });
                }, 0);
            });
        }

        // Upload button click function
        $(`#${le}-upload-btn`).on("click", function (e) {
            let filePickerElement = document.getElementById(`${le}-file-picker`);
            let selectedFile = filePickerElement.files[0];
            if (typeof selectedFile !== 'undefined') { // if there is a file selected
                uploadFile(selectedFile, le);
                disable_button(`#${le}-upload-btn`);
                unhighlight_button(`#${le}-draw-btn`);
            }
        });

        // White button click function
        $(`#${le}-white-btn`).on("click", function (e) {
            let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            let led_index = get_led_index(le);

            socket.emit("light_engine_draw_white", { "light_engine": le, "correction": correction, "led": led_index });
            highlight_button(`#${le}-white-btn`);
            unhighlight_button(`#${le}-draw-btn`);
            unhighlight_button(`#${le}-black-btn`);
        });

        // Draw button click function
        $(`#${le}-draw-btn`).on("click", function (e) {
            let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            let led_index = get_led_index(le);

            socket.emit("light_engine_draw_image", { "light_engine": le, "correction": correction, "led": led_index });
            highlight_button(`#${le}-draw-btn`);
            unhighlight_button(`#${le}-white-btn`);
            unhighlight_button(`#${le}-black-btn`);
        });

        // Black button click function
        $(`#${le}-black-btn`).on("click", function (e) {
            let checkboxElement = document.getElementById(`${le}-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            let led_index = get_led_index(le);

            socket.emit("light_engine_draw_black", { "light_engine": le, "correction": correction, "led": led_index });
            highlight_button(`#${le}-black-btn`);
            unhighlight_button(`#${le}-white-btn`);
            unhighlight_button(`#${le}-draw-btn`);
        });


        // Handles to user inputs
        let LedPowerSliderElement = document.getElementById(`${le}-led-power-slider`);
        let LedPowerLabelElement = document.getElementById(`${le}-led-power-label`);
        let ExposureElement = document.getElementById(`${le}-exposure-txt`);

        // Set initial LED power slider label value
        LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

        // Update the LedPowerLabelElement with the current slider value
        LedPowerSliderElement.oninput = function () {
            LedPowerLabelElement.innerHTML = this.value;
        }

        // Light engine control stop button click function
        $(`#${le}-stop-btn`).click(function () {
            socket.emit("light_engine_stop", le);
        });

        // Exposure text input change function
        $(`#${le}-exposure-txt`).on('change', function () {
            exposure = ExposureElement.value;

            // Validate user input. Only allows positive integers > 0
            if (/^\d+$/.test(exposure) && exposure > 0) {
                ExposureElement.classList.remove("is-invalid")
                enable_button(`#${le}-start-btn`);
            } else {
                ExposureElement.classList.add("is-invalid")
                disable_button(`#${le}-start-btn`);
            }
        })

        $(`#${le}-repeat-chkbx`).click(function () {
            let repeatCheckboxElement = document.getElementById(`${le}-repeat-chkbx`);
            let repeat = Number(!repeatCheckboxElement.checked);
            if (repeat == 0) {
                ExposureElement.classList.remove("is-invalid")
                $(`#${le}-exposure-txt`).prop('disabled', true);
            } else {
                $(`#${le}-exposure-txt`).prop('disabled', false);
            }
        });

        // Light engine control start button click function
        $(`#${le}-start-btn`).click(function () {
            let correctionCheckboxElement = document.getElementById(`${le}-correction-chkbx`);
            let repeatCheckboxElement = document.getElementById(`${le}-repeat-chkbx`);
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

            let correction = Number(correctionCheckboxElement.checked);
            let led_index = get_led_index(le);

            console.log({ "repeat": repeat, "exposure": exposure, "ledPower": ledPower, "led": led_index, "correction": correction })
            socket.emit("light_engine_start", { "light_engine": le, "repeat": repeat, "exposure": exposure, "ledPower": ledPower, "led": led_index, "correction": correction});
        });
    }
    socket.on("light_engine_update_led_state", function (message) {
        let light_engine = message["light_engine"];
        let status = message["state"];
        let statusElement = document.getElementById(`${light_engine}-status`);
        if (status == true) {
            statusElement.classList.remove("invisible")
        } else {
            statusElement.classList.add("invisible")
        }
        $(`#${light_engine}-status`).prop('disabled', status);
    });
});

function uploadFile(image, le) {
    let fd = new FormData(); // Create form data
    fd.append("file", image); // Attach the image file
    fd.append("light_engine", le);
    console.log(le)
    $.ajax({ // Use ajax to compose and send the request
        url: "/light_engine_image_upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}