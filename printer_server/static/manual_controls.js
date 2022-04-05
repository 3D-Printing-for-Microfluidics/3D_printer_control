var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

var disable_calibration_motor_buttons = function () {
    $('.motor-controls button').prop('disabled', true);
}

var enable_calibration_motor_buttons = function () {
    $('.motor-controls button').prop('disabled', false);
}

var disable_galil_buttons = function () {
    // $('.galil button').prop('disabled', true);
}

var enable_galil_buttons = function () {
    $('.galil button').prop('disabled', false);
}

// var enable_upload_buttons = function () {
//     $('.light-engine button').prop('disabled', false);
// }

var disable_upload_buttons = function () {
    // $('.light-engine button').prop('disabled', true);
}

var enable_upload_button = function () {
    $('#upload-btn').prop('disabled', false);
}

// var disable_upload_button = function () {
//     // $('#upload-btn').prop('disabled', true);
// }

// var disable_project_start_button = function () {
//     // $('#le-start-btn').prop('disabled', true);
// }

// var enable_project_start_button = function () {
//     $('#le-start-btn').prop('disabled', false);
// }

var enable_project_start_stop_buttons = function () {
    $('#le-start-btn').prop('disabled', false);
    $('#le-stop-btn').prop('disabled', false);
}

var disable_project_start_stop_buttons = function () {
    // $('#le-start-btn').prop('disabled', true);
    // $('#le-stop-btn').prop('disabled', true);
}

var update_tip_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('tip-state').innerHTML = message.tip;
    }
}

var update_tilt_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('tilt-state').innerHTML = message.tilt;
    }
}

var update_dist_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('dist-state').innerHTML = message.distance;
    }
}

// helper function to update positions on all calibration axes
var update_positions = function (message) {
    update_tip_position(message);
    update_tilt_position(message);
    update_dist_position(message);
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");

    // Handles to user inputs
    var LedPowerSliderElement = document.getElementById("led-power-slider");
    var LedPowerLabelElement = document.getElementById("led-power-label");
    var exposureElement = document.getElementById("exposure-txt");
    var LedPowerSliderElementWintech = document.getElementById("led-power-slider-wintech");
    var LedPowerLabelElementWintech = document.getElementById("led-power-label-wintech");
    var exposureElementWintech = document.getElementById("exposure-txt-wintech");
    var distanceElement = document.getElementById("distance-txt");
    var tipElement = document.getElementById("tip-txt");
    var tiltElement = document.getElementById("tilt-txt");
    var filePickerElement = document.getElementById("file-picker");
    var filePickerElementWintech = document.getElementById("file-picker-wintech");


    // Set initial LED power slider label value
    LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value
    LedPowerLabelElementWintech.innerHTML = LedPowerSliderElementWintech.value; // Display the default slider value

    // Update the LedPowerLabelElement with the current slider value
    LedPowerSliderElement.oninput = function () {
        LedPowerLabelElement.innerHTML = this.value;
    }
    LedPowerSliderElementWintech.oninput = function () {
        LedPowerLabelElementWintech.innerHTML = this.value;
    }

    // Enable calibration motor buttons and update position labels when current motion is complete
    socket.on("calibration_motor_move_complete", function (message) {
        update_positions(message);
        enable_calibration_motor_buttons();
    });

    // Enable galil control buttons when current galil motion is complete
    socket.on("galil_done", function () {
        enable_galil_buttons();
    });

    // Once once upload is complete, re-enable upload controls
    socket.on("calibration_image_uploaded", function () {
        filePickerElement.classList.remove("is-invalid")
        enable_upload_button()

        var exposure = exposureElement.value;
        // Validate user input for exposure. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            enable_project_start_stop_buttons();    // input was good
        } else {
            disable_project_start_stop_buttons();   // input was bad
        }
    });

    // Once once upload is complete, re-enable upload controls
    socket.on("calibration_image_uploaded_wintech", function () {
        console.log("uploaded Wintech")
        filePickerElementWintech.classList.remove("is-invalid")
        enable_upload_button()

        var exposure = exposureElementWintech.value;
        // Validate user input for exposure. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            enable_project_start_stop_buttons();    // input was good
        } else {
            disable_project_start_stop_buttons();   // input was bad
        }
    });

    // If a bad file was uploaded, disable upload options
    socket.on("calibration_image_bad", function () {
        filePickerElement.classList.add("is-invalid")
        disable_upload_buttons();
    });

    // If a bad file was uploaded, disable upload options
    socket.on("calibration_image_bad_wintech", function () {
        console.log("bad image Wintech")
        filePickerElementWintech.classList.add("is-invalid")
        disable_upload_buttons();
    });

    // Enable upload button when a file is chosen
    $("#file-picker").on("click", function (e) {
        enable_upload_button();
    });

    // Enable upload button when a file is chosen
    $("#file-picker-wintech").on("click", function (e) {
        console.log("filepick Wintech")
        enable_upload_button();
    });

    // Reset button click function
    $("#reset-printer-state").on("click", function () {
        disable_all_buttons();
        socket.emit("reset_printer_state");
    });

    // Upload button click function
    $("#upload-btn").on("click", function (e) {
        var selectedFile = filePickerElement.files[0];
        if (typeof selectedFile !== 'undefined') {  // if there is a file selected
            disable_upload_buttons();
            uploadFile(selectedFile);
        }
    });

    // Upload button click function
    $("#upload-btn-wintech").on("click", function (e) {
        console.log("upload Wintech")
        var selectedFile = filePickerElementWintech.files[0];
        if (typeof selectedFile !== 'undefined') {  // if there is a file selected
            disable_upload_buttons();
            uploadFileWintech(selectedFile);
        }
    });

    // Galil control top button click function
    $("#galil-top-btn").click(function () {
        disable_galil_buttons();
        socket.emit("galil_go_to_top");
    });

    // Galil control bottom button click function
    $("#galil-bottom-btn").click(function () {
        disable_galil_buttons();
        socket.emit("galil_go_to_bottom");
    });

    $("#galil-home-btn").click(function () {
        socket.emit("galil_home");
    });

    // Light engine control stop button click function
    $("#le-stop-btn").click(function () {
        socket.emit("light_engine_stop");
    });

    // Light engine control stop button click function
    $("#le-stop-btn-wintech").click(function () {
        console.log("stop Wintech")
        socket.emit("light_engine_stop_wintech");
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

    // Exposure text input change function
    $('#exposure-txt-wintech').on('change', function () {
        console.log("exposure Wintech")
        exposure = exposureElementWintech.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            exposureElementWintech.classList.remove("is-invalid")
            enable_project_start_stop_buttons();
        } else {
            exposureElementWintech.classList.add("is-invalid")
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

    // Light engine control start button click function
    $("#le-start-btn-wintech").click(function () {
        console.log("start Wintech")
        var repeatCheckboxElement = document.getElementById("repeat-chkbx-wintech");
        var exposure = exposureElementWintech.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = LedPowerSliderElementWintech.value;
        socket.emit("light_engine_start_wintech", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    // Calibration motor buttons for homing
    $(".home-btn").click(function () {
        // Disable calibration motor buttons
        disable_calibration_motor_buttons();
        // Parse button content and construct message
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis };
        // Emit control message with parsed values
        socket.emit("calibration_motor_home", message);
    });

    // Calibration motor text inputs for absolute positioning
    $(".mtr-cntrl-txt").on('change', function () {
        // Disable calibration motor buttons
        disable_calibration_motor_buttons();
        // Parse button content and construct message
        var microns = $(this).val();
        var axis = $(this).closest(".container").attr('aria-label');
        var message = { "axis": axis, "microns": microns, "mode": "absolute", "fast": false, "log": true };
        // Emit control message with parsed values
        socket.emit("calibration_motor_move", message);
    });

    // Calibration motor buttons for relative positioning
    $(".mtr-cntrl-btn").click(function () {
        // Disable calibration motor buttons
        disable_calibration_motor_buttons();
        // Parse button content and construct message
        var microns = $(this).text();
        var axis = $(this).closest(".container").attr('aria-label');
        var fast = document.getElementById("quick_move").checked;
        console.log(fast)
        var message = { "axis": axis, "microns": microns, "mode": "relative", "fast": fast, "log": true };
        // Emit control message with parsed values
        socket.emit("calibration_motor_move", message);
    });

    // Read value of external control select button
    $("#external_enable :input").change(function () {
        socket.emit("set_external_control_enable", $(this).parent().text());
    });

});

function uploadFile(image) {
    var fd = new FormData();    // Create form data
    fd.append("file", image);   // Attach the image file
    $.ajax({                    // Use ajax to compose and send the request
        url: "/handle-calibration-upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}

function uploadFileWintech(image) {
    console.log("upload Wintech")
    var fd = new FormData();    // Create form data
    fd.append("file", image);   // Attach the image file
    $.ajax({                    // Use ajax to compose and send the request
        url: "/handle-calibration-upload-wintech",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}