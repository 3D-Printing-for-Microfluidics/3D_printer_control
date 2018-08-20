var disable_all_buttons = function(){
    $('button').prop('disabled', true);
}

var enable_all_buttons = function(){
    $('button').prop('disabled', false);
}

var disable_calibration_motor_buttons = function(){
    $('.motor-controls button').prop('disabled', true);
}

var enable_calibration_motor_buttons = function(){
    $('.motor-controls button').prop('disabled', false);
}

var disable_solus_buttons = function(){
    $('.solus button').prop('disabled', true);
}

var enable_solus_buttons = function(){
    $('.solus button').prop('disabled', false);
}

var enable_upload_buttons = function(){
    $('.light-engine button').prop('disabled', false);
}

var disable_upload_buttons = function(){
    $('.light-engine button').prop('disabled', true);
}

var enable_upload_button = function(){
    $('#upload-btn').prop('disabled', false);
}

var disable_upload_button = function(){
    $('#upload-btn').prop('disabled', true);
}

var disable_project_start_button = function(){
    $('#le-start-btn').prop('disabled', true);
}

var enable_project_start_button = function(){
    $('#le-start-btn').prop('disabled', false);
}

var enable_project_start_stop_buttons = function(){
    $('#le-start-btn').prop('disabled', false);
    $('#le-stop-btn').prop('disabled', false);
}

var disable_project_start_stop_buttons = function(){
    $('#le-start-btn').prop('disabled', true);
    $('#le-stop-btn').prop('disabled', true);
}

$(document).ready(function(){
    
    // Set up socket, disable all controls, and send message to initialize hardware 
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibrate");
    disable_all_buttons();
    socket.emit("initialize");

    // Handles to user inputs 
    var LedPowerSliderElement = document.getElementById("led-power-slider");
    var LedPowerLabelElement  = document.getElementById("led-power-label");
    var exposureElement       = document.getElementById("exposure-txt");
    var filePickerElement     = document.getElementById("file-picker");
    
    // Set initial LED power slider label value 
    LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

    // Update the LedPowerLabelElement with the current slider value
    LedPowerSliderElement.oninput = function() {
        LedPowerLabelElement.innerHTML = this.value;
    }

    // Once hardware is initialized, enable controls 
    socket.on("initialized", function(){
        enable_all_buttons();
        disable_upload_buttons();
    });
    
    // Enable calibration motor buttons when current motion is complete 
    socket.on("calibration_motor_done", function() {
        enable_calibration_motor_buttons();
    });
    
    // Enable Solus control buttons when current Solus motion is complete 
    socket.on("solus_done", function() {
        enable_solus_buttons();
    });

    // Once once upload is complete, re-enable upload controls  
    socket.on("calibration_image_uploaded", function(){
        filePickerElement.classList.remove("is-invalid")
        enable_upload_button()
        
        var exposure = exposureElement.value;
        // Validate user input for exposure. Only allows positive integers > 0
        if(/^\d+$/.test(exposure) && exposure > 0){
            enable_project_start_stop_buttons();    // input was good 
        } else {
            disable_project_start_stop_buttons();   // input was bad 
        }
    });

    // If a bad file was uploaded, disable upload options  
    socket.on("calibration_image_bad", function(){
        filePickerElement.classList.add("is-invalid")
        disable_upload_buttons();
    });

    // Enable upload button when a file is chosen
    $("#file-picker").on("click", function(e) {
        enable_upload_button();
    });

    // Reset button click function 
    $("#reset-printer-state").on("click", function() {
        disable_all_buttons();
        socket.emit("reset_printer_state");
    });

    // Upload button click function 
    $("#upload-btn").on("click", function(e) {
        var selectedFile = filePickerElement.files[0];
        if (typeof selectedFile !== 'undefined') {  // if there is a file selected 
            disable_upload_buttons();
            uploadFile(selectedFile);
        }
    });

    // Solus control top button click function 
    $("#solus-top-btn").click(function() {
        disable_solus_buttons();
        console.log("emit solus_go_to_top")
        socket.emit("solus_go_to_top");
    });

    // Solus control bottom button click function 
    $("#solus-bottom-btn").click(function() {
        disable_solus_buttons();
        socket.emit("solus_go_to_bottom");
    });

    
    // Light engine control stop button click function 
    $("#le-stop-btn").click(function() {
        socket.emit("light_engine_stop");
    });

    // Exposure text input change function 
    $('#exposure-txt').on('change', function() {
        exposure = exposureElement.value;

        // Validate user input. Only allows positive integers > 0
        if(/^\d+$/.test(exposure) && exposure > 0){
            exposureElement.classList.remove("is-invalid")
            enable_project_start_stop_buttons();
        } else {
            exposureElement.classList.add("is-invalid")
            disable_project_start_stop_buttons();
        }
    })

    // Light engine control start button click function 
    $("#le-start-btn").click(function() {
        var repeatCheckboxElement = document.getElementById("repeat-chkbx");
        var exposure = exposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = LedPowerSliderElement.value;
        socket.emit("light_engine_start", {"repeat": repeat, "exposure": exposure, "ledPower": ledPower});
    });

    // Handles to auto-updating position labels
    var tipLabelElement  = document.getElementById("tip-state");
    var tiltLabelElement = document.getElementById("tilt-state");
    var distLabelElement = document.getElementById("dist-state");

    // Calibration motor control button click function  
    $(".mtr-cntrl-btn").click(function() {
        // Parse button content 
        var steps = $(this).text(); 
        var axis = $(this).parent().attr('aria-label')
        if (axis == "Tip") {
            tipLabelElement.innerHTML  = Number(tipLabelElement.innerHTML)  + Number(steps); 
        } else if (axis == "Tilt") {
            tiltLabelElement.innerHTML = Number(tiltLabelElement.innerHTML) + Number(steps); 
        } else if (axis == "Distance") {
            distLabelElement.innerHTML = Number(distLabelElement.innerHTML) + Number(steps); 
        }
        // Disable calibration motor buttons  
        disable_calibration_motor_buttons();
        // Emit control message with parsed values 
        socket.emit("calibration_motor", {"axis": axis, "steps": steps});
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
