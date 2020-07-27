var start_job_id;
var delete_job_id;

// List of pending files to handle when the Upload button is finally clicked.
var PENDING_FILES = [];


$("#create-job").on("click", function () {
    if ($(this).text() == "Create a job") {
        $(this).text("Hide");
    } else {
        $(this).text("Create a job");
    }
});

$("#job-table").on("click", ".clickable-row", function (event) {
    if ($(this).hasClass("table-success")) {
        $(this).removeClass("table-success");
        start_job_id = "";
        $("#start-btn").prop("disabled", true);
    } else {
        $(this).addClass("table-success").siblings().removeClass("table-success");
        start_job_id = $(this).attr("id").replace("row-", "")
        $("#start-btn").prop("disabled", false);
    }
});

$("#clear-print-message").on("click", function () {
    $("#print-message > div").remove();
});

var show_btn = function (btn) {
    $(".printer-btn").prop("disabled", true).addClass("d-none");
    $(btn).prop("disabled", false).removeClass("d-none");
};

var update_print_message = function (message) {
    if (!$.isEmptyObject(message)) {
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


function initDropbox() {
    var $dropbox = $("#dropbox");

    // On drag enter...
    $dropbox.on("dragenter", function (e) {
        e.stopPropagation();
        e.preventDefault();
        $(this).addClass("active");
    });

    $dropbox.on("dragleave", function (e) {
        e.stopPropagation();
        e.preventDefault();
        $(this).removeClass("active");
    });

    // On drag over...
    $dropbox.on("dragover", function (e) {
        e.stopPropagation();
        e.preventDefault();
    });

    // On drop...
    $dropbox.on("drop", function (e) {
        e.preventDefault();
        $(this).removeClass("active");

        // Get the files.
        var files = e.originalEvent.dataTransfer.files;
        addFiles(files);
    });

    // If the files are dropped outside of the drop zone, the browser will
    // redirect to show the files in the window. To avoid that we can prevent
    // the "drop" event on the document.
    function stopDefault(e) {
        e.stopPropagation();
        e.preventDefault();
    }
    $(document).on("dragenter", stopDefault);
    $(document).on("dragover", stopDefault);
    $(document).on("drop", stopDefault);
}

var get_file_str = function () {
    if (PENDING_FILES.length <= 0) {
        return "No files selected."
    }
    var file_str = PENDING_FILES.length > 1 ? " files" : " file";
    return PENDING_FILES.length + file_str + " selected"
}

function addFiles(files) {
    var $selected = $("#selected-files");

    // Add them to the pending files list.
    for (var i = 0; i < files.length; i++) {
        PENDING_FILES.push(files[i]);

        // Append files to show on page
        var li_file = $("<li/>", {
            class: "list-group-item d-flex justify-content-between align-items-center",
            text: files[i].name
        }).appendTo($selected);
        var del_file = $("<button/>", {
            type: "button",
            class: "ml-auto btn btn-sm btn-danger",
            html: "&times;"
        }).appendTo(li_file);
        del_file.on("click", function () {
            PENDING_FILES.splice($(this).parent().index(), 1);
            $(this).parent().remove();
            $("#file-number").text(get_file_str());
        });
    }
    $("#file-number").text(get_file_str());
}

function doUpload() {
    $("#upload-progress").removeClass("d-none");

    // Gray out the form.
    $("#upload-form :input").attr("disabled", "disabled");

    // Initialize the progress bar.
    $("#upload-progress-bar").css({ "width": "0%" })
        .attr({ "aria-valuenow": 0 })
        .text("%");

    // Collect the form data.
    // fd = collectFormData();
    var fd = new FormData();

    // Attach the files.
    for (var i = 0; i < PENDING_FILES.length; i++) {
        // Collect the other form data.
        fd.append("file", PENDING_FILES[i]);
    }

    var xhr = $.ajax({
        xhr: function () {
            var xhrobj = $.ajaxSettings.xhr();
            if (xhrobj.upload) {
                xhrobj.upload.addEventListener("progress", function (event) {
                    var percent = 0;
                    var position = event.loaded || event.position;
                    var total = event.total;
                    if (event.lengthComputable) {
                        percent = Math.ceil(position / total * 100);
                    }

                    // Set the progress bar.
                    $("#upload-progress-bar").css({ "width": percent + "%" })
                        .attr({ "aria-valuenow": percent })
                        .text(percent + "%");
                    $("#upload-completion").text(percent + "%");
                }, false)
            }
            return xhrobj;
        },
        url: "/handle-upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd,
        success: function (data) {
            PENDING_FILES = [];
            $("#file-number").text(get_file_str());
            $("ul#selected-files > li").remove()
            $("#upload-progress-bar").css({ "width": "0%" });
            $("#upload-progress").addClass("d-none");
        },
    });
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/printing");
    socket.emit("connect");

    // Set up the drag/drop zone.
    initDropbox();

    // Set up the handler for the file input box.
    $("#file-picker").on("change", function () {
        addFiles(this.files);
        this.value = null
    });

    // Handle the submit button.
    $("#upload-btn").on("click", function (e) {
        // If the user has JS disabled, none of this code is running but the
        // file multi-upload input box should still work. In this case they"ll
        // just POST to the upload endpoint directly. However, with JS we"ll do
        // the POST using ajax and then redirect them ourself when done.
        e.preventDefault();
        if (PENDING_FILES.length == 0) {
            window.close();
        }
        doUpload();
    });

    socket.on("busy", function (message) {
        $("#printer-state").text("3D Printer is Busy");
        show_btn();
        start_job_id = "";
        $(".clickable-row").removeClass("table-success");
        update_print_message(message);
    });

    socket.on("uninitialized", function (message) {
        $("#printer-state").text("Uninitialized");
        show_btn("#init-btn, #shutdown-btn");
    });

    socket.on("initialized", function (message) {
        $("#printer-state").text("Initialized");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
    });

    socket.on("planarizing", function (message) {
        $("#printer-state").text("Planarizing");
        show_btn("#plana2-btn, #admin-btn");
    });

    socket.on("planarized", function (message) {
        $("#printer-state").text("Planarized");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        $("#start-btn").removeClass("d-none");
    });

    socket.on("printing", function (message) {
        $("#printer-state").text("Printing");
        show_btn("#pause-btn, #stop-btn, #admin-btn");
        $("#print-progress-bar").css({ "width": message.percent + "%" })
            .attr({ "aria-valuenow": message.percent })
            .text(message.percent + "%");
        $("#print-progress").removeClass("d-none");
        update_print_message(message);
    });

    socket.on("print progress", function (message) {
        $("#print-progress-bar").css({ "width": message.percent + "%" })
            .attr({ "aria-valuenow": message.percent })
            .text(message.percent + "%");
        update_print_message(message);
    });

    socket.on("paused", function (message) {
        $("#printer-state").text("Paused");
        show_btn("#resume-btn, #stop-btn, #admin-btn");
    });

    socket.on("stopped", function (message) {
        $("#printer-state").text("Stopped");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        $("#print-progress").addClass("d-none");
    });

    socket.on("completed", function (message) {
        $("#printer-state").text("Completed");
        show_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        $("#print-progress").addClass("d-none");
        update_print_message(message);
    });

    socket.on("shutting down", function (message) {
        $("#printer-state").text("Shutting down");
        update_print_message(message);
    });

    socket.on("shutdown completed", function (message) {
        $("html").text("3D printer has been shutdown");
    });

    socket.on("shutdown failed", function (message) {
        // TODO: add a warning window
        update_print_message(message);
    });



    $("#print-alert-confirm").click(function () {
        var operation = $("#print-alert-title").text();
        var msg;

        if (operation === "Start") {
            msg = { job: start_job_id };
        } else if (operation === "Delete Job") {
            msg = { job: delete_job_id };
        } else {
            msg = {};
        }
        socket.emit(operation.toLowerCase(), msg);
        $("#print-alert-title").text("");
        $("#print-alert-body").text("");
    });

    $("#print-alert-cancel").click(function () {
        $("#print-alert-title").text("");
        $("#print-alert-body").text("");
    });

    $("#init-btn").click(function () {
        $("#print-alert-title").text("Initialize");
        $("#print-alert-body").text("WARNING: Is the bluid platform taken off? Initializing with the platform on can seriously damage the printer!");
    });

    $("#plana1-btn").click(function () {
        $("#print-alert-title").text("Planarization Step 1");
        $("#print-alert-body").text("Is bluid platform mounted? (Make sure the previous print has been removed if applicable)");
    });

    $("#plana2-btn").click(function () {
        $("#print-alert-title").text("Planarization Step 2");
        $("#print-alert-body").text("Make sure the build platform or silanized glass is flat and tighten the screws.");
    });

    $("#start-btn").click(function () {
        $("#print-alert-title").text("Start");
        $("#print-alert-body").text("Are you sure you want to start printing?");
    });

    $("#pause-btn").click(function () {
        $("#print-alert-title").text("Pause");
        $("#print-alert-body").text("Are you sure you want to pause printing?");
    });

    $("#resume-btn").click(function () {
        $("#print-alert-title").text("Resume");
        $("#print-alert-body").text("Are you sure you want to resume printing?");
    });

    $("#stop-btn").click(function () {
        $("#print-alert-title").text("Stop");
        $("#print-alert-body").text("Are you sure you want to stop printing?");
    });

    $("#shutdown-btn").click(function () {
        $("#print-alert-title").text("Shutdown");
        $("#print-alert-body").text("Make sure 3D printer is not in operation.");
    });

    // Database interaction
    socket.on("job uploaded", function (message) {
        var new_row = `
    <tr id="row-${message.id}" class="clickable-row">
      <th scope="row">${$("#job-table > tbody > tr").length + 1}</th>
      <td>${message.name}</td>
      <td>${message.upload_time}</td>
      <td>${message.upload_ip}</td>
      <td><a class="btn btn-sm btn-warning delete-job" id="delete-job${message.id}" role="button" aria-pressed="true" data-toggle="modal" data-target="#confirmModal">delete</a></td>
    </tr>
        `;
        $("#job-table > tbody").append(new_row);
        var new_msg = { time: message.upload_time, text: "Print Job (" + message.name + ") Uploaded" };
        update_print_message(new_msg);
        $("#create-job").trigger('click');  // collapse the upload menu when done
    });

    $(document).on("click", ".delete-job", function () {
        delete_job_id = $(this).attr("id").replace("delete-job", "");
        $("#print-alert-title").text("Delete Job");
        $("#print-alert-body").text("Are you sure you want to delete this print job?");
    });

    socket.on("job deleted", function (message) {
        $("#row-" + message.job).remove();
        update_print_message(message);
    });

    socket.on("validation error", function (message) {
        var flash_msg = `
       <div class="alert alert-${message.category}">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
        <pre>${message.text}</pre>
       </div>
        `;
        $("#printer-controls").before(flash_msg);
    });
});