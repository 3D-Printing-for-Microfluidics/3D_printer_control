
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

var disable_all_buttons = function(){
    $('button').prop('disabled', true);
}

var enable_all_buttons = function(){
    $('button').prop('disabled', false);
}

$(document).ready(function(){
    
    var slider = document.getElementById("myRange");
    var output = document.getElementById("myValue");
    output.innerHTML = slider.value; // Display the default slider value

    // Update the current slider value (each time you drag the slider handle)
    slider.oninput = function() {
        output.innerHTML = this.value;
    }
        
    // Set up socket and send message to initialize hardware 
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibrate");
    
    disable_all_buttons();
    socket.emit("initialize");

    socket.on("initialized", function(){
        enable_all_buttons();
    });

    var tipLabel  = document.getElementById("tip-state");
    var tiltLabel = document.getElementById("tilt-state");
    var distLabel = document.getElementById("dist-state");

    $(".mtr-cntrl-btn").click(function() {
        var steps = $(this).text(); 
        var axis = $(this).parent().attr('aria-label')
        if (axis == "Tip") {
            tipLabel.innerHTML = Number(tipLabel.innerHTML) + Number(steps); 
        } else if (axis == "Tilt") {
            tiltLabel.innerHTML = Number(tiltLabel.innerHTML) + Number(steps); 
        } else if (axis == "Distance") {
            distLabel.innerHTML = Number(distLabel.innerHTML) + Number(steps); 
        }
        disable_calibration_motor_buttons();
        socket.emit("calibration_motor", {"axis": axis, "steps": steps});
    });

    $("#solus-top-btn").click(function() {
        disable_solus_buttons();
        socket.emit("solus_go_to_top");
    });

    $("#solus-bottom-btn").click(function() {
        disable_solus_buttons();
        socket.emit("solus_go_to_bottom");
    });

    socket.on("solus_done", function() {
        enable_solus_buttons();
    });

    socket.on("calibration_motor_done", function() {
        enable_calibration_motor_buttons();
    });
    
});