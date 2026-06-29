// List of pending files to handle when the Upload button is finally clicked.
var PENDING_FILES = [];


function initDropbox() {
    let $dropbox = $("#dropbox");

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
        let files = e.originalEvent.dataTransfer.files;
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
    let file_str = PENDING_FILES.length > 1 ? " files" : " file";
    return PENDING_FILES.length + file_str + " selected"
}

function addFiles(files) {
    let $selected = $("#selected-files");

    // Add them to the pending files list.
    for (let i = 0; i < files.length; i++) {
        PENDING_FILES.push(files[i]);

        // Append files to show on page
        let li_file = $("<li/>", {
            class: "list-group-item d-flex justify-content-between align-items-center",
            text: files[i].name
        }).appendTo($selected);
        let del_file = $("<button/>", {
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

{/* <div class="form-group mb-4">
                    <label class="small text-muted">Upload as:</label>
                    <div class="btn-group btn-group-toggle w-100" data-toggle="buttons">
                        <label class="btn btn-outline-secondary active">
                            <input type="radio" name="userOption" id="currentUser" checked> Current User
                        </label>
                        <label class="btn btn-outline-secondary">
                            <input type="radio" name="userOption" id="otherUser"> Other User
                        </label>
                    </div>
                    <input type="text" id="otherUserField" class="form-control mt-2 d-none" placeholder="Enter username...">
                </div> */}

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
    let fd = new FormData();

    if ($("#otherUser").is(":checked")) {
        fd.append("user", $("#otherUserField").val());
    }

    // Attach the files.
    for (let i = 0; i < PENDING_FILES.length; i++) {
        // Collect the other form data.
        fd.append("file", PENDING_FILES[i]);
    }

    let xhr = $.ajax({
        xhr: function () {
            var xhrobj = $.ajaxSettings.xhr();
            if (xhrobj.upload) {
                xhrobj.upload.addEventListener("progress", function (event) {
                    let percent = 0;
                    let position = event.loaded || event.position;
                    let total = event.total;
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
            $("#otherUser").prop("checked", false);
            $("#otherUser").parent().removeClass("active");
            $("#currentUser").prop("checked", true);
            $("#currentUser").parent().addClass("active");
            $("#otherUserField").addClass("d-none").val("");
            $("#file-number").text(get_file_str());
            $("ul#selected-files > li").remove()
            $("#upload-progress-bar").css({ "width": "0%" });
            $("#upload-progress").addClass("d-none");
        },
    });
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/printing");
    socket.emit("connecting");

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

    $('#uploadModal').on('hidden.bs.modal', function () {
        PENDING_FILES = []; 
        $("#otherUser").prop("checked", false);
        $("#otherUser").parent().removeClass("active");
        $("#currentUser").prop("checked", true);
        $("#currentUser").parent().addClass("active");
        $("#otherUserField").addClass("d-none").val("");

        $("#file-number").text(get_file_str());
        $("ul#selected-files > li").remove();
        
        // Always hide the progress bar
        $("#upload-progress").addClass("d-none");
        $("#upload-progress-bar").css({ "width": "0%" });
    });

    // Toggle visibility of the text field
    $('input[name="userOption"]').on('change', function() {
        if ($('#otherUser').is(':checked')) {
            $('#otherUserField').removeClass('d-none');
        } else {
            $('#otherUserField').addClass('d-none').val(''); // Clear on hide
        }
    });
});