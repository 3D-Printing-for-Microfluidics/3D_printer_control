var start_job_id;
var delete_job_id;

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

    $("#init-btn").click(function() {
        $("#print-alert-title").text("Initialize");
        $("#print-alert-body").text("WARNING: Is the bluid platform taken off? Initializing with the platform on can seriously damage the printer!");
    });

    $("#plana1-btn").click(function() {
        $("#print-alert-title").text("Planarization Step 1");
        $("#print-alert-body").text("Is bluid platform mounted? (Make sure the previous print has been removed if applicable)");
    });

    $("#plana2-btn").click(function() {
        $("#print-alert-title").text("Planarization Step 2");
        $("#print-alert-body").text("Make sure the build platform or silanized glass is flat and tighten the screws.");
    });

    $("#start-btn").click(function() {
        $("#print-alert-title").text("Start");
        $("#print-alert-body").text("Are you sure you want to start printing?");
    });

    $("#pause-btn").click(function() {
        $("#print-alert-title").text("Pause");
        $("#print-alert-body").text("Are you sure you want to pause printing?");
    });

    $("#resume-btn").click(function() {
        $("#print-alert-title").text("Resume");
        $("#print-alert-body").text("Are you sure you want to resume printing?");
    });

    $("#stop-btn").click(function() {
        $("#print-alert-title").text("Stop");
        $("#print-alert-body").text("Are you sure you want to stop printing?");
    });

    $("#shutdown-btn").click(function() {
        $("#print-alert-title").text("Shutdown");
        $("#print-alert-body").text("Make sure 3D printer is not in operation.");
    });

    // Database interaction
    socket.on("job uploaded", function(message) {
        var new_row = `
    <tr id="row-${message.id}" class="clickable-row">
      <th scope="row">${$("#job-table > tbody > tr").length+1}</th>
      <td>${message.name}</td>
      <td>${message.uploadTime}</td>
      <td>${message.uploadIP}</td>
      <td><a class="btn btn-sm btn-warning delete-job" id="delete-job${message.id}" role="button" aria-pressed="true" data-toggle="modal" data-target="#confirmModal">delete</a></td>
    </tr>
        `;
        $("#job-table > tbody").append(new_row);
        var new_msg = {time: message.uploadTime, text: "Print Job (" + message.name + ") Uploaded"};
        update_print_message(new_msg);
    });

    $(document).on("click", ".delete-job", function() {
        delete_job_id = $(this).attr("id").replace("delete-job", "");
        $("#print-alert-title").text("Delete Job");
        $("#print-alert-body").text("Are you sure to delete this print job?");
    });

    socket.on("job deleted", function(message) {
        $("#row-" + message.job).remove();
        update_print_message(message);
    });

    socket.on("my error", function(message){
        var flash_msg = `
       <div class="alert alert-${message.category}">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
        ${message.text}
       </div>
        `;
        $("#printer-controls").before(flash_msg);
    });
});