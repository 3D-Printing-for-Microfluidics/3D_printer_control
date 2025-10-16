var enable_upload_button = function (le) {
    $(`#${le}-upload-btn`).prop('disabled', false);
    $(`#${le}-upload-btn`).addClass('btn-outline-info');
    $(`#${le}-upload-btn`).removeClass('btn-outline-secondary');
}

var disable_upload_button = function (le) {
    $(`#${le}-upload-btn`).prop('disabled', true);
    $(`#${le}-upload-btn`).removeClass('btn-outline-info');
    $(`#${le}-upload-btn`).addClass('btn-outline-secondary');
}

var highlight_draw_button = function (le) {
    $(`#${le}-draw-btn`).addClass('active');
}

var unhighlight_draw_button = function (le) {
    $(`#${le}-draw-btn`).removeClass('active');
}

var highlight_draw_white_button = function (le) {
    $(`#${le}-white-btn`).addClass('active');
}

var unhighlight_draw_white_button = function (le) {
    $(`#${le}-white-btn`).removeClass('active');
}

$(document).ready(function () {
    // Once once upload is complete, re-enable upload controls
    socket.on("screen_image_uploaded", function (le) {
        let filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.remove("is-invalid")
        // enable_upload_button(le);
    });

    // If a bad file was uploaded, disable upload options
    socket.on("screen_image_bad", function (le) {
        let filePickerElement = document.getElementById(`${le}-file-picker`);
        filePickerElement.classList.add("is-invalid")
        enable_upload_button(le);
    });

    socket.on('screen_load', function(message) {
        for (let le in manual_controls_data["light_engines"]) {
            let lightCheckboxElement = document.getElementById(`${le}-light-correction-chkbx`);
            let darkCheckboxElement = document.getElementById(`${le}-dark-correction-chkbx`);
            lightCheckboxElement.checked = message[le]["light"];
            darkCheckboxElement.checked = message[le]["dark"];
            
        }
    });

    socket.on('screen_previews', function(message) {
        for (let le in manual_controls_data["light_engines"]) {
            var img = document.getElementById(`${le}-preview`);
            if (message[le]) {
                img.src = 'data:image/jpeg;base64,' + message[le];
            }
            img.style.display = 'inline';
        }
    });

    socket.on('screen_done', function(message) {
        for (const [le, data] of Object.entries(message)) {
            var img = document.getElementById(`${le}-preview`);
            if (data) {
                img.src = 'data:image/jpeg;base64,' + data;
            }
            img.style.display = 'inline';
        }
    });


    for (let le in manual_controls_data["light_engines"]) {

        disable_upload_button(le);

        document.getElementById(`${le}-file-picker`).addEventListener('change', function (event) {
            let projector = $(this).closest(".container").attr('aria-label');
            filePickerElement = event.currentTarget
            const curFiles = filePickerElement.files;
            if (curFiles.length === 0) {
                disable_upload_button(projector);
            } else {
                enable_upload_button(projector);
            }
        });

        // Correction button click function
        $(`#${le}-light-correction-chkbx`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            let checkboxElement = document.getElementById(`${le}-light-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            socket.emit("screen_light_grayscale_correction", { "light_engine": projector, "correction":  correction});
        });

        // Correction button click function
        $(`#${le}-dark-correction-chkbx`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            let checkboxElement = document.getElementById(`${le}-dark-correction-chkbx`);
            let correction = Number(checkboxElement.checked);
            socket.emit("screen_dark_grayscale_correction", { "light_engine": projector, "correction":  correction});
        });

        // Upload button click function
        $(`#${le}-upload-btn`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            let filePickerElement = document.getElementById(`${projector}-file-picker`);
            let selectedFile = filePickerElement.files[0];
            if (typeof selectedFile !== 'undefined') { // if there is a file selected
                uploadFile(selectedFile, projector);
                disable_upload_button(projector);
                unhighlight_draw_button(projector);
            }
        });

        // Draw button click function
        $(`#${le}-white-btn`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            socket.emit("screen_white", { "light_engine": projector });
            highlight_draw_white_button(projector);
            unhighlight_draw_button(projector);
        });

        // Draw button click function
        $(`#${le}-draw-btn`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            socket.emit("screen_draw", { "light_engine": projector });
            highlight_draw_button(projector);
            unhighlight_draw_white_button(projector);
        });

        // Clear button click function
        $(`#${le}-clear-btn`).on("click", function (e) {
            let projector = $(this).closest(".container").attr('aria-label');
            socket.emit("screen_clear", { "light_engine": projector });
            unhighlight_draw_button(projector);
            unhighlight_draw_white_button(projector);
        });
    };
});

function uploadFile(image, le) {
    let fd = new FormData(); // Create form data
    fd.append("file", image); // Attach the image file
    fd.append("light_engine", le);
    console.log(le)
    $.ajax({ // Use ajax to compose and send the request
        url: "/screen_image_upload",
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd
    });
}