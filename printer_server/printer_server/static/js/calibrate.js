$("#create-job").on("click", function() {
  if($(this).text() == "Create a job") {
    $(this).text("Hide");
  } else {
    $(this).text("Create a job");
  }
});

$("#job-table").on("click", ".clickable-row", function(event) {
  if($(this).hasClass("table-success")){
    $(this).removeClass("table-success");
    start_job_id = "";
    $("#start-btn").prop("disabled", true).addClass("btn-secondary");
  } else {
    $(this).addClass("table-success").siblings().removeClass("table-success");
    start_job_id = $(this).attr("id").replace("row-", "")
    $("#start-btn").prop("disabled", false).removeClass("btn-secondary");
  }
});

$("#clear-print-message").on("click", function() {
    $("#print-message > div").remove();
});

var show_btn = function(btn) {
    $(".printer-btn").prop("disabled", true).addClass("d-none");
    $(btn).prop("disabled", false).removeClass("d-none");
};

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
    
    
    
    
    
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/printing");
    socket.emit("connect");
    
    socket.on("busy", function(message) {
        $("#printer-state").text("3D Printer is Busy");
        show_btn();
        start_job_id = "";
        $(".clickable-row").removeClass("table-success");
        update_print_message(message);
    });
    
    socket.on("uninitialized", function(message) {
        $("#printer-state").text("Uninitialized");
        show_btn("#init-btn, #shutdown-btn");
    });
    
    socket.on("initialized", function(message) {
        $("#printer-state").text("Initialized");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
    });
    
    socket.on("planarizing", function(message) {
        $("#printer-state").text("Planarizing");
        show_btn("#plana2-btn");
    });
    
    socket.on("planarized", function(message) {
        $("#printer-state").text("Planarized");
        show_btn("#plana1-btn, #shutdown-btn");
        $("#start-btn").removeClass("d-none").addClass("btn-secondary");
    });
    
    socket.on("printing", function(message) {
        $("#printer-state").text("Printing");
        show_btn("#pause-btn, #stop-btn");
        $("#print-progress-bar").css({"width": message.percent + "%"})
                                .attr({"aria-valuenow": message.percent})
                                .text(message.percent + "%");
        $("#print-progress").removeClass("d-none");
        update_print_message(message);
    });
    
    socket.on("print progress", function(message) {
        $("#print-progress-bar").css({"width": message.percent + "%"})
                                .attr({"aria-valuenow": message.percent})
                                .text(message.percent + "%");
        update_print_message(message);
    });
    
    socket.on("paused", function(message) {
        $("#printer-state").text("Paused");
        show_btn("#resume-btn, #stop-btn");
    });
    
    socket.on("stopped", function(message) {
        $("#printer-state").text("Stopped");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        $("#print-progress").addClass("d-none");
    });
    
    socket.on("completed", function(message) {
        $("#printer-state").text("Completed");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        $("#print-progress").addClass("d-none");
        update_print_message(message);
    });

    socket.on("shutting down", function(message) {
        $("#printer-state").text("Shutting down");
        update_print_message(message);
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

    $("#print-alert-cancel").click(function() {
        $("#print-alert-title").text("");
        $("#print-alert-body").text("");
    });

    $("#shutdown-btn").click(function() {
        $("#print-alert-title").text("Shutdown");
        $("#print-alert-body").text("Make sure 3D printer is not operating, and that build platform is at home position.");
    });
});