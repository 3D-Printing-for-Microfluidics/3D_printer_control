
var disable_motor_control_buttons = function(){
    $('.motor-controls button').prop('disabled', true);
}

var enable_motor_control_buttons = function(){
    $('.motor-controls button').prop('disabled', false);
}

var disable_solus_buttons = function(){
    $('.solus button').prop('disabled', true);
}

var enable_solus_buttons = function(){
    $('.solus button').prop('disabled', false);
}



var update_print_message = function(message) {
    if(!$.isEmptyObject(message)) {
        var new_text = `
        <div class="row">
            <div class="col-4">
            ${message.time}
            </div>
            <div class="col-8">
            ${message.text}
            </div>
        </div>
        `;
        $("#print-message").append(new_text);
    }
}

$(document).ready(function(){
    
    var slider = document.getElementById("myRange");
    var output = document.getElementById("myValue");
    output.innerHTML = slider.value; // Display the default slider value

    // Update the current slider value (each time you drag the slider handle)
    slider.oninput = function() {
        output.innerHTML = this.value;
    }
    
    
    
    
    // Set up socket 
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibrate");
    
    
    disable_motor_control_buttons();
    socket.emit("connect");
    
    socket.on("matthew", function() {
        enable_motor_control_buttons();
    });

    socket.on("busy", function(message) {
        $("#printer-state").text("3D Printer is Busy");
        // show_btn();
        start_job_id = "";
        $(".clickable-row").removeClass("table-success");
        update_print_message(message);
    });
    
    socket.on("uninitialized", function(message) {
        $("#printer-state").text("Uninitialized");
        // show_btn("#init-btn, #shutdown-btn");
    });
    

    socket.on("shutdown completed", function(message) {
        $("html").text("3D printer has been shutdown");
    });

    socket.on("shutdown failed", function(message) {
        // TODO: add a warning window
        update_print_message(message);
    });


    
    $("#print-alert-confirm").click(function() {
        var operation = $("#print-alert-title").text();
        var msg;
        
        if (operation === "Start") {
            msg = {job: start_job_id};
        } else if (operation === "Delete Job") {
            msg = {job: delete_job_id};
        } else {
            msg = {};
        }
        socket.emit(operation.toLowerCase(), msg);
        $("#print-alert-title").text("");
        $("#print-alert-body").text("");
    });

    $("#shutdown-btn").click(function() {
        $("#print-alert-title").text("Shutdown");
        $("#print-alert-body").text("Make sure 3D printer is not operating, and that build platform is at home position.");
    });
});