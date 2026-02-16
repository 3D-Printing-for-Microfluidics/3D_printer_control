var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

var update_parameters = function (message) {
    for (let parameter in calibration_data) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${parameter.replaceAll(' ', '-')}-state`).innerHTML = message[parameter];
        }
    }
}

var show_calibration_print_alert = function (text, category = "info") {
    let alert = `
        <div class="alert alert-${category} justify-center">
            <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
            <pre>${text}</pre>
        </div>
    `;
    $("#calibration-print-alerts").html(alert);
}

var show_calibration_print_details = function () {
    $("#calibration-print-empty").addClass("d-none");
    $("#calibration-print-details").removeClass("d-none");
}

var reset_calibration_print_details = function () {
    $("#calibration-print-details").addClass("d-none");
    $("#calibration-print-empty").removeClass("d-none");
    $("#calibration-print-alerts").empty();
    $("#calibration-print-variables").empty();
    $("#calibration-print-readme").empty();
    $("#calibration-print-add").prop("disabled", true);
}

var render_calibration_print_variables = function (variables) {
    let $container = $("#calibration-print-variables");
    $container.empty();
    if (!variables || Object.keys(variables).length === 0) {
        $container.html("<div class='text-muted'>No variables defined.</div>");
        return;
    }
    variables.forEach(function (item) {
        let key = item.key;
        let label = item.label || item.key;
        let value = item.value;
        let input = `
            <div class="form-group">
                <label>${label}</label>
                <input type="text" class="form-control calibration-print-variable" data-var="${key}" value="${value}">
            </div>
        `;
        $container.append(input);
    });
}

var load_calibration_prints = function () {
    socket.emit("calibration_prints_list");
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/calibration");

    socket.on("set_done", function (message) {
        update_parameters(message)
    });

    socket.on("goto_done", function (message) {
        update_parameters(message)
        enable_all_buttons();
    });

    $("#goto").click(function () {
        disable_all_buttons();
        socket.emit("goto");
    });

    for (let parameter in calibration_data) {
        parameter = parameter.replaceAll(' ', '-');
        // text inputs for absolute changes
        $(`.${parameter}-cntrl-txt`).on('change', function () {
            // Parse button content and construct message
            let distance = $(this).val();
            let p = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "absolute", "distance": distance, "parameter": p };
            socket.emit("set", message);
        });

        // buttons for relative changes
        $(`.${parameter}-cntrl-btn`).click(function () {
            // Parse button content and construct message
            let distance = $(this).text();
            let p = $(this).closest(".container").attr('aria-label');
            let message = { "mode": "relative", "distance": distance, "parameter": p };
            socket.emit("set", message);
        });
    }

    socket.on("calibration_prints_list_done", function (message) {
        let prints = message.prints || [];
        let $list = $("#calibration-print-list");
        $list.empty();
        reset_calibration_print_details();
        if (prints.length === 0) {
            $list.append(`<div class="text-muted">No calibration prints found.</div>`);
            return;
        }
        prints.forEach(function (item) {
            $list.append(`
                <button type="button" class="list-group-item list-group-item-action" data-id="${item.id}">
                    ${item.name}
                </button>
            `);
        });
    });

    socket.on("calibration_prints_details_done", function (details) {
        render_calibration_print_variables(details.variables);
        $("#calibration-print-readme").html(details.readme_html || "");
        $("#calibration-print-add").prop("disabled", false).data("id", details.id);
        show_calibration_print_details();
    });

    socket.on("calibration_prints_add_done", function (message) {
        show_calibration_print_alert(message.text, "success");
        $("#calibration-print-add").prop("disabled", false);
    });

    socket.on("calibration_prints_flash", function (message) {
        show_calibration_print_alert(message.text, message.category || "warning");
        $("#calibration-print-add").prop("disabled", false);
    });

    $("#calibration-print-list").on("click", ".list-group-item", function () {
        let id = $(this).data("id");
        if (!id) {
            return;
        }
        $("#calibration-print-list .list-group-item").removeClass("active");
        $(this).addClass("active");
        $("#calibration-print-add").prop("disabled", true).data("id", id);
        socket.emit("calibration_prints_details", { id: id });
    });

    $("#calibration-print-add").on("click", function () {
        let id = $(this).data("id");
        if (!id) {
            show_calibration_print_alert("Select a calibration print first.", "warning");
            return;
        }
        let variables = {};
        $(".calibration-print-variable").each(function () {
            let key = $(this).data("var");
            variables[key] = $(this).val();
        });
        $("#calibration-print-add").prop("disabled", true);
        socket.emit("calibration_prints_add_to_queue", { id: id, variables: variables });
    });

    load_calibration_prints();
    reset_calibration_print_details();

});
