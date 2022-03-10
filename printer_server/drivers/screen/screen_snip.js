var enable_upload_button = function (le) {
    console.log(`enable_upload_button ${le}`)
    $(`#${le}-upload-btn`).prop('disabled', false);
}

var disable_upload_button = function (le) {
    console.log(`disable_upload_button ${le}`)
    // $(`#${le}-upload-btn`).prop('disabled', true);
}

$(document).ready(function () {
    // Once once upload is complete, re-enable upload controls
    socket.on("calibration_image_uploaded", function (le) {
        var filePickerElement = document.getElementById(`${le}-file-picker`);
        console.log(`calibration_image_uploaded ${le}`)
        filePickerElement.classList.remove("is-invalid")
        enable_upload_button(le)

        var exposure = exposureElement.value;
        // Validate user input for exposure. Only allows positive integers > 0
        if (/^\d+$/.test(exposure) && exposure > 0) {
            enable_project_start_stop_buttons();    // input was good
        } else {
            disable_project_start_stop_buttons();   // input was bad
        }
    });

    // If a bad file was uploaded, disable upload options
    socket.on("calibration_image_bad", function (le) {
        var filePickerElement = document.getElementById(`${le}-file-picker`);
        console.log(`calibration_image_bad ${le}`)
        filePickerElement.classList.add("is-invalid")
        disable_le_buttons();
    });


    for (var le of light_engines) {
        le = le.toLowerCase()
        // Enable upload button when a file is chosen
        $(`#${le}-file-picker`).on("click", function (e) {
            console.log(`#${le}-file-picker`)
            enable_upload_button(le);
        });

        // Upload button click function
        $(`#${le}-upload-btn`).on("click", function (e) {
            var filePickerElement = document.getElementById(`${le}-file-picker`);
            console.log(`#${le}-upload-btn ${le}-file-picker`)
            var selectedFile = filePickerElement.files[0];
            if (typeof selectedFile !== 'undefined') {  // if there is a file selected
                disable_le_buttons();
                uploadFile(selectedFile, le);
            }
        });
    };
});

function uploadFile(image, le) {
    console.log(`uploadFile ${le}`)
    var fd = new FormData();    // Create form data
    fd.append("file", image);   // Attach the image file
    fd.append("light_engine", le);
    $.ajax({                    // Use ajax to compose and send the request
        url: "/handle-calibration-upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}