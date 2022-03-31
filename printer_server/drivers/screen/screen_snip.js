var enable_upload_button = function (le) {
    $(`#${le}-upload-btn`).prop('disabled', false);
}

var disable_upload_button = function (le) {
    $(`#${le}-upload-btn`).prop('disabled', true);
}

$(document).ready(function () {
    // Once once upload is complete, re-enable upload controls
    socket.on("calibration_image_uploaded", function (le) {
        var filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.remove("is-invalid")
        // enable_upload_button(le);
    });

    // If a bad file was uploaded, disable upload options
    socket.on("calibration_image_bad", function (le) {
        var filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.add("is-invalid")
        enable_upload_button(le);
    });


    for (var le of hardware["screen"]["light_engines"]) {

        $(`#${le}-upload-btn`).prop('disabled', true);

        document.getElementById(`${le}-file-picker`).addEventListener('change', function (event) {
            var projector = $(this).closest(".row").attr('aria-label');
            filePickerElement = event.currentTarget
            const curFiles = filePickerElement.files;
            if (curFiles.length === 0) {
                disable_upload_button(projector);
            } else {
                enable_upload_button(projector);
            }
        });

        // Upload button click function
        $(`#${le}-upload-btn`).on("click", function (e) {
            var projector = $(this).closest(".row").attr('aria-label');
            var filePickerElement = document.getElementById(`${projector}-file-picker`);
            var selectedFile = filePickerElement.files[0];
            if (typeof selectedFile !== 'undefined') { // if there is a file selected
                uploadFile(selectedFile, projector);
                disable_upload_button(projector);
            }
        });

        // Draw button click function
        $(`#${le}-white-btn`).on("click", function (e) {
            var projector = $(this).closest(".row").attr('aria-label');
            socket.emit("screen_white", { "light_engine": projector });
        });

        // Draw button click function
        $(`#${le}-draw-btn`).on("click", function (e) {
            var projector = $(this).closest(".row").attr('aria-label');
            socket.emit("screen_draw", { "light_engine": projector });
        });

        // Clear button click function
        $(`#${le}-clear-btn`).on("click", function (e) {
            var projector = $(this).closest(".row").attr('aria-label');
            socket.emit("screen_clear", { "light_engine": projector });
        });
    };
});

function uploadFile(image, le) {
    var fd = new FormData(); // Create form data
    fd.append("file", image); // Attach the image file
    fd.append("light_engine", le);
    console.log(le)
    $.ajax({ // Use ajax to compose and send the request
        url: "/handle-calibration-upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}