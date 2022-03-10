var enable_upload_button = function () {
    $('#upload-btn').prop('disabled', false);
}

var disable_upload_button = function () {
    // $('#upload-btn').prop('disabled', true);
}

$(document).ready(function () {
    var filePickerElement = document.getElementById("file-picker");

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

    // If a bad file was uploaded, disable upload options
    socket.on("calibration_image_bad", function () {
        filePickerElement.classList.add("is-invalid")
        disable_le_buttons();
    });

    // Enable upload button when a file is chosen
    $("#file-picker").on("click", function (e) {
        enable_upload_button();
    });

    // Upload button click function
    $("#upload-btn").on("click", function (e) {
        var selectedFile = filePickerElement.files[0];
        if (typeof selectedFile !== 'undefined') {  // if there is a file selected
            disable_le_buttons();
            uploadFile(selectedFile);
        }
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