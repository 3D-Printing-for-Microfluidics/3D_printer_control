$(document).ready(function () {
    // Set up socket, disable all controls, and send message to initialize hardware 
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibrate");
    // information about what stages need to be displayed 
    var stageTypes = JSON.parse(document.getElementById("mydata").dataset.stages);
    // Handles to user inputs 
    var LedPowerSliderElement = document.getElementById("led-power-slider");
    var LedPowerLabelElement = document.getElementById("led-power-label");
    var exposureElement = document.getElementById("exposure-txt");
    var filePickerElement = document.getElementById("file-picker");
    var gotoElement = document.getElementById("k-cube-dist-txt");

    // keep track of movement info while waiting for response from server
    var last_movement_axis = "";
    var last_movement_steps = "";
    var last_initialized = "";
    var last_homed = "";
    var last_saved_pos_stage = "";

    // Set initial LED power slider label value 
    LedPowerLabelElement.innerHTML = LedPowerSliderElement.value; // Display the default slider value

    // Update the LedPowerLabelElement with the current slider value
    LedPowerSliderElement.oninput = function () {
        LedPowerLabelElement.innerHTML = this.value;
    }

    // get saved stage positions
    get_saved_positions();


    //////////////////////////////////////////
    //////// Button activation states ////////
    //////////////////////////////////////////

    // When a stage is moving, all of the other stage buttons should be disabled. 
    // This variable stores the state of the buttons so that they can be correctly reenabled. 
    var button_states = {}
    // Solus buttons states
    var solus_uninitialized = function () {
        document.getElementById("solus-init-btn").disabled = false;
        document.getElementById("solus-home-btn").disabled = true;
        document.getElementById("solus-top-btn").disabled = true;
        document.getElementById("solus-bottom-btn").disabled = true;
        button_states["solus"] = solus_uninitialized;
    }
    var solus_initialized = function () {
        document.getElementById("solus-init-btn").disabled = false;
        document.getElementById("solus-home-btn").disabled = false;
        document.getElementById("solus-top-btn").disabled = true;
        document.getElementById("solus-bottom-btn").disabled = true;
        button_states["solus"] = solus_initialized;
    }
    var solus_homed = function () {
        document.getElementById("solus-init-btn").disabled = false;
        document.getElementById("solus-home-btn").disabled = false;
        document.getElementById("solus-top-btn").disabled = false;
        document.getElementById("solus-bottom-btn").disabled = false;
        button_states["solus"] = solus_homed;
    }

    // Light engine button states
    var le_uninitialized = function () {
        document.getElementById("le-init-btn").disabled = false;
        document.getElementById("le-upload-btn").disabled = true;
        document.getElementById("le-start-btn").disabled = true;
        document.getElementById("le-stop-btn").disabled = true;
        button_states["le"] = le_uninitialized;
    }
    var le_initialized = function () {
        document.getElementById("le-init-btn").disabled = false;
        document.getElementById("le-upload-btn").disabled = false;
        document.getElementById("le-start-btn").disabled = true;
        document.getElementById("le-stop-btn").disabled = true;
        button_states["le"] = le_uninitialized;
    }
    var enable_upload_button = function () {
        document.getElementById("le-upload-btn").disabled = false;
    }
    var disable_upload_button = function () {
        document.getElementById("le-upload-btn").disabled = true;
    }
    var le_init_stop = function () {
        document.getElementById("le-init-btn").disabled = false;
        document.getElementById("le-upload-btn").disabled = false;
        document.getElementById("le-start-btn").disabled = true;
        document.getElementById("le-stop-btn").disabled = false;
        button_states["le"] = le_init_stop;
    }
    var le_init_start = function () {
        document.getElementById("le-init-btn").disabled = false;
        document.getElementById("le-upload-btn").disabled = false;
        document.getElementById("le-start-btn").disabled = false;
        document.getElementById("le-stop-btn").disabled = true;
        button_states["le"] = le_init_start;
    }

    // general motor control functions
    var disable_calibration_motor_buttons = function () {
        $('.motor-controls button').prop('disabled', true);
    }
    var disable_solus_buttons = function () {
        $('.solus button').prop('disabled', true);
    }
    var disable_stage_buttons = function () {
        disable_calibration_motor_buttons();
        disable_solus_buttons();
    }
    // 28byj48 stage button states
    var uninitialized_28byj48 = function (stage_type) {
        $('.' + stage_type + '-btn-group button').prop('disabled', true);
        document.getElementById(stage_type + "-init-btn").disabled = false;
        button_states[stage_type] = uninitialized_28byj48;
    }
    var initialized_28byj48 = function (stage_type) {
        $('.' + stage_type + '-btn-group button').prop('disabled', false);
        document.getElementById(stage_type + "-init-btn").disabled = false;
        button_states[stage_type] = initialized_28byj48;
    }

    // kdc101 stage button states
    var uninitialized_kdc101 = function (stage_type) {
        $('.' + stage_type + '-btn-group button').prop('disabled', true);
        document.getElementById(stage_type + "-init-btn").disabled = false;
        document.getElementById(stage_type + "-home-btn").disabled = true;
        document.getElementById(stage_type + "-goto-btn").disabled = true;
        document.getElementById(stage_type + "-goto-saved-pos-btn").disabled = true;
        document.getElementById(stage_type + "-save-curr-pos-btn").disabled = true;
        button_states[stage_type] = uninitialized_kdc101;
    }
    var initialized_kdc101 = function (stage_type) {
        $('.' + stage_type + '-btn-group button').prop('disabled', false);
        document.getElementById(stage_type + "-init-btn").disabled = false;
        document.getElementById(stage_type + "-home-btn").disabled = false;
        document.getElementById(stage_type + "-goto-btn").disabled = true;
        document.getElementById(stage_type + "-goto-saved-pos-btn").disabled = true;
        document.getElementById(stage_type + "-save-curr-pos-btn").disabled = true;
        button_states[stage_type] = initialized_kdc101;
    }
    var initialized_homed_kdc101 = function (stage_type) {
        $('.' + stage_type + '-btn-group button').prop('disabled', false);
        document.getElementById(stage_type + "-init-btn").disabled = false;
        document.getElementById(stage_type + "-home-btn").disabled = false;
        document.getElementById(stage_type + "-goto-btn").disabled = false;
        document.getElementById(stage_type + "-goto-saved-pos-btn").disabled = false;
        document.getElementById(stage_type + "-save-curr-pos-btn").disabled = false;
        button_states[stage_type] = initialized_homed_kdc101;
    }

    //  functions for all buttons
    var reset_button_states = function () {
        for (var key in stageTypes) {
            if (key == "le" || key == "solus") {
                button_states[key]();
            }
            else {
                button_states[key](key);
            }
        }
    }
    var initialize_button_states = function () {
        for (var key in stageTypes) {
            if (stageTypes[key] == "28byj48") {
                uninitialized_28byj48(key);
            }
            else if (stageTypes[key] == "kdc101") {
                uninitialized_kdc101(key);
            }
        }
        solus_uninitialized();
        le_uninitialized();
    }
    var set_home_button_state = function (type) {
        if (type == "solus") {
            solus_homed();
        }
        else if (stageTypes[type] == "kdc101") {
            initialized_homed_kdc101();
        }
    }

    initialize_button_states(); 


    /////////////////////////////////
    //////// SocketIO logic  ////////
    /////////////////////////////////

    // Once hardware is initialized, enable controls 
    socket.on("initialized", function () {
        if (last_initialized == "solus") {
            solus_initialized();
        }
        else if (last_initialized == "le") {
            le_initialized();
        }
        else {
            for (var key in stageTypes) {
                if (last_initialized == key) {
                    if (stageTypes[key] == "28byj48") {
                        initialized_28byj48(key);
                        return;
                    }
                    else if (stageTypes[key] == "kdc101") {
                        initialized_kdc101(key);
                        return;
                    }
                }
            }
        }
    });

    // Enable calibration motor buttons when current motion is complete 
    socket.on("calibration_motor_done", function () {
        // enable_calibration_motor_buttons();
        reset_button_states();
        socket.emit("calibration_get_position", stage = last_movement_axis);
    });

    // Enable calibration motor buttons when homing is complete
    socket.on("stage_homed", function () {
        reset_button_states();
        if(last_homed == "solus") {
            solus_homed();
        }
        else {
            for (var key in stageTypes) {
                if (last_homed == key) {
                    if (stageTypes[key] == "28byj48"){
                        return; // does not have a homed state
                    }
                    else if (stageTypes[key] == "kdc101") {
                        initialized_homed_kdc101(key); 
                        return; 
                    }
                }
            }
        }
    });

    socket.on("calibration_stage_position", function (message) {
        var pos = Number(message["pos"]);
        set_axis_position(pos);
    });

    // Enable Solus control buttons when current Solus motion is complete 
    socket.on("solus_done", function () {
        solus_homed();
    });

    // Once once upload is complete, re-enable upload controls  
    socket.on("calibration_image_uploaded", function () {
        filePickerElement.classList.remove("is-invalid")
        enable_upload_button();

        var exposure = exposureElement.value;
        // Validate user input for exposure. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            le_init_start();    // input was good 
            
        } else {
            le_initialized(); // input was bad 
        }
    });

    // If a bad file was uploaded, disable upload options  
    socket.on("calibration_image_bad", function () {
        filePickerElement.classList.add("is-invalid")
        disable_upload_button();
    });

    socket.on("last_saved_pos", function (pos) {
        document.getElementById(last_saved_pos_stage + "-last-saved-pos").innerHTML = pos.toFixed(3);
    });

    socket.on("saved_position", function(message) {
        var stage = message["stage"];
        var pos = message["pos"]; 
        document.getElementById(stage+"-last-saved-pos").innerHTML = pos; 
    });

    ///////////////////////////////
    //////// Button logic ////////
    ///////////////////////////////

    // Enable upload button when a file is chosen
    $("#file-picker").on("click", function () {
        enable_upload_button();
    });

    // Reset button click function 
    $("#reset-printer-state").on("click", function () {
        // disable_all_buttons();
        initialize_button_states();
        socket.emit("reset_printer_state");
    });

    // Upload button click function 
    $("#upload-btn").on("click", function (e) {
        var selectedFile = filePickerElement.files[0];
        if (typeof selectedFile !== 'undefined') {  // if there is a file selected 
            disable_upload_button();
            uploadFile(selectedFile);
        }
    });

    // Solus control top button click function 
    $("#solus-top-btn").click(function () {
        disable_solus_buttons();
        socket.emit("solus_go_to_top");
    });

    // Solus control bottom button click function 
    $("#solus-bottom-btn").click(function () {
        disable_solus_buttons();
        socket.emit("solus_go_to_bottom");
    });

    // Light engine control stop button click function 
    $("#le-stop-btn").click(function () {
        le_init_start(); // go to start state
        socket.emit("light_engine_stop");
    });

    // Exposure text input change function 
    $('#exposure-txt').on('change', function () {
        exposure = exposureElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            exposureElement.classList.remove("is-invalid")
            le_init_start();
        } else {
            exposureElement.classList.add("is-invalid")
            le_initialized();
        }
    })

    // K cube go to position
    $('.goto-btn').click(function () {
        // get the axis and the number of steps to move
        last_movement_axis = $(this).parent().attr('aria-label');
        last_movement_steps = parseFloat(gotoElement.value);
        // set the movement to absolute mode and move the stage
        socket.emit("set_absolute", { "stage": last_movement_axis });
        socket.emit("calibration_motor", { "axis": last_movement_axis, "steps": last_movement_steps });
    })

    $('.goto-saved-pos-btn').click(function () {
        // get the axis and the number of steps to move
        last_movement_axis = $(this).parent().attr('aria-label');
        last_movement_steps = parseFloat(gotoElement.value);
        // set the movement to absolute mode and move the stage
        socket.emit("set_absolute", { "stage": last_movement_axis });
        socket.emit("goto_saved_pos", last_movement_axis);
    });

    $('.save-curr-pos-btn').click(function () {
        var axis = $(this).parent().attr('aria-label');
        socket.emit("save_current_position", axis)
        socket.emit("get_saved_position", axis)
    });

    // Light engine control start button click function 
    $("#le-start-btn").click(function () {
        le_init_stop(); // go to stop state
        var repeatCheckboxElement = document.getElementById("repeat-chkbx");
        var exposure = exposureElement.value;
        var repeat = Number(!repeatCheckboxElement.checked);
        var ledPower = LedPowerSliderElement.value;
        socket.emit("light_engine_start", { "repeat": repeat, "exposure": exposure, "ledPower": ledPower });
    });

    // Calibration motor control button click function  
    $(".mtr-cntrl-btn").click(function () {
        // Parse button content 
        last_movement_steps = $(this).text();
        last_movement_axis = $(this).parent().attr('aria-label');
        // Disable calibration motor buttons  
        disable_calibration_motor_buttons();
        // Emit control message with parsed values 
        socket.emit("set_relative", { "stage": last_movement_axis });
        socket.emit("calibration_motor", { "axis": last_movement_axis, "steps": last_movement_steps });
    });

    $(".init-btn").click(function () {
        last_initialized = $(this).parent().attr('aria-label');
        socket.emit("initialize", last_initialized);
    });

    $(".home-btn").click(function () {
        last_homed = $(this).parent().attr('aria-label');
        socket.emit("home", last_homed)
        disable_stage_buttons();
    });


    //////////////////////////////////    
    //////// Helper functions ////////
    //////////////////////////////////

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
    function set_axis_position(pos) {
        var type = $("#" + last_movement_axis).data()["type"];
        var positionElement = document.getElementById(last_movement_axis + "-pos");
        if (type == "28byj48") {
            positionElement.innerHTML = Number(positionElement.innerHTML) + Number(last_movement_steps);
        }
        else if (type == "kdc101") {
            if (pos == NaN) {
                positionElement.innerHTML = "Undef";
            }
            else {
                positionElement.innerHTML = pos.toFixed(3) + " mm";
            }
        }
    }

    function get_saved_positions() {
        for (var key in stageTypes) {
            if (stageTypes[key] == "28byj48") { } // do nothing
            else if(stageTypes[key] == "kdc101") {
                socket.emit("get_saved_position", key); 
            }
        }   
    }

});
