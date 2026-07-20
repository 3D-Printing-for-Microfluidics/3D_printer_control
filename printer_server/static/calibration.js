var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

var update_parameters = function (message) {
    if ($.isEmptyObject(message)) {
        return;
    }
    for (let i = 0; i < message.length; i++) {
        let item = message[i];
        let el = document.getElementById(`${item.machine_name}-state`);
        if (el) {
            el.innerHTML = item.value;
        }
    }
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
    $("#calibration-print-name").text("");
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
            <div class="row">
                <div class="col-6">
                    <label>${label}</label>
                </div>
                <div class="col-6">
                    <input type="text" class="form-control calibration-print-variable" data-var="${key}" value="${value}">
                </div>
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

    for (let i = 0; i < calibration_data.length; i++) {
        let item = calibration_data[i];
        let machine = item.machine_name;
        let group = item.group;
        // text inputs for absolute changes
        $(`.${machine}-cntrl-txt`).on('change', function () {
            // Parse button content and construct message
            let distance = $(this).val();
            let p = $(this).closest(".container").data('machine-name');
            let g = $(this).closest(".container").data('group');
            let message = { "mode": "absolute", "distance": distance, "parameter": p, "group": g || group };
            socket.emit("set", message);
        });

        // buttons for relative changes
        $(`.${machine}-cntrl-btn`).click(function () {
            // Parse button content and construct message
            let distance = $(this).text();
            let p = $(this).closest(".container").data('machine-name');
            let g = $(this).closest(".container").data('group');
            let message = { "mode": "relative", "distance": distance, "parameter": p, "group": g || group };
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
        $("#calibration-print-name").text(details.name || "");
        $("#calibration-print-readme").html(details.readme_html || "");
        $("#calibration-print-add").prop("disabled", false).data("id", details.id);
        show_calibration_print_details();

        if(details.name === "Visitech and Wintech Alignment Print") {
            initializeAlignmentCalculators($("#calibration-print-readme"));
            // link the "Add to adjustments" button
            $(document).on("click", "#add-to-adjustments", function () {
                addResultsToAdjustments($("#calibration-print-readme"));
            });
        }
    });

    socket.on("calibration_prints_add_done", function (message) {
        $("#calibration-print-add").prop("disabled", false);
    });

    $("#calibration-print-list").on("click", ".list-group-item", function () {
        let id = $(this).data("id");
        if (!id) {
            return;
        }
        if ($(this).hasClass("active")) {
            $(this).removeClass("active");
            $("#calibration-print-add").prop("disabled", true).data("id", null);
            reset_calibration_print_details();
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


    async function addResultsToAdjustments(container){
        const alignX = parseFloat(container.find("#out_align_x").text()) || 0;
        const alignY = parseFloat(container.find("#out_align_y").text()) || 0;

        const stitchXX = parseFloat(container.find("#out_stitch_xx").text()) || 0;
        const stitchXY = parseFloat(container.find("#out_stitch_xy").text()) || 0;
        const stitchYX = parseFloat(container.find("#out_stitch_yx").text()) || 0;
        const stitchYY = parseFloat(container.find("#out_stitch_yy").text()) || 0;


        console.log("Adding results to adjustments:");

        let message = { "mode": "relative", "distance": alignX, "parameter": "wintech_x_alignment", "group": "Alignment Adjustments" };
        socket.emit("set", message);
        await new Promise(resolve => setTimeout(resolve, 250));

        message = { "mode": "relative", "distance": alignY, "parameter": "wintech_y_alignment", "group": "Alignment Adjustments" };
        socket.emit("set", message);
        await new Promise(resolve => setTimeout(resolve, 250));

        message = { "mode": "relative", "distance": stitchXX, "parameter": "wintech_x_shift_x", "group": "Stitching Adjustments" };
        socket.emit("set", message);
        await new Promise(resolve => setTimeout(resolve, 250));

        message = { "mode": "relative", "distance": stitchXY, "parameter": "wintech_y_shift_x", "group": "Stitching Adjustments" };
        socket.emit("set", message);
        await new Promise(resolve => setTimeout(resolve, 250));

        message = { "mode": "relative", "distance": stitchYX, "parameter": "wintech_x_shift_y", "group": "Stitching Adjustments" };
        socket.emit("set", message);
        await new Promise(resolve => setTimeout(resolve, 250));

        message = { "mode": "relative", "distance": stitchYY, "parameter": "wintech_y_shift_y", "group": "Stitching Adjustments" };
        socket.emit("set", message);
    }

});


function initializeAlignmentCalculators(container) {

    container.find(".alignment-calculator").each(function () {

        // Don't initialize twice
        if ($(this).data("initialized"))
            return;

        $(this).data("initialized", true);

        $(this).html(`
<table class="table table-sm table-bordered text-center">
<thead>
<tr>
    <th></th>
    <th>-X</th>
    <th>+X</th>
    <th>Center</th>
    <th>-Y</th>
    <th>+Y</th>
</tr>
</thead>
<tbody>
<tr>
    <th>x (μm)</th>
    <td><input class="form-control calc" id="negx_x" type="number" value="0"></td>
    <td><input class="form-control calc" id="posx_x" type="number" value="0"></td>
    <td><input class="form-control calc" id="origin_x" type="number" value="0"></td>
    <td><input class="form-control calc" id="negy_x" type="number" value="0"></td>
    <td><input class="form-control calc" id="posy_x" type="number" value="0"></td>
</tr>
<tr>
    <th>y (μm)</th>
    <td><input class="form-control calc" id="negx_y" type="number" value="0"></td>
    <td><input class="form-control calc" id="posx_y" type="number" value="0"></td>
    <td><input class="form-control calc" id="origin_y" type="number" value="0"></td>
    <td><input class="form-control calc" id="negy_y" type="number" value="0"></td>
    <td><input class="form-control calc" id="posy_y" type="number" value="0"></td>
</tr>
</tbody>
</table>

<h5>Results</h5>

<table class="table table-sm table-bordered">
<tr>
    <th>Alignment Adjustments - Wintech</th>
<tr>
<tr>
    <th></th>
    <th>X</th>
    <td id="out_align_x"></td>
</tr>
<tr>
    <th></th>
    <th>Y</th>
    <td id="out_align_y"></td>
</tr>
<tr>
    <th>Stitching Adjustments - Wintech (per mm X)</th>
<tr>
<tr>
    <th></th>
    <th>X</th>
    <td id="out_stitch_xx"></td>
</tr>
<tr>
    <th></th>
    <th>Y</th>
    <td id="out_stitch_xy"></td>
</tr>
<tr>
    <th>Stitching Adjustments - Wintech (per mm Y)</th>
<tr>
<tr>
    <th></th>
    <th>X</th>
    <td id="out_stitch_yx"></td>
</tr>
<tr>
    <th></th>
    <th>Y</th>
    <td id="out_stitch_yy"></td>
</tr>
</table>
`);

        $(this).find(".calc").on("input", function () {
            updateAlignmentCalculator($(this).closest(".alignment-calculator"));
        });

        updateAlignmentCalculator($(this));
    });
}

function updateAlignmentCalculator(container) {

    function v(id) {
        return parseFloat(container.find("#" + id).val()) || 0;
    }

    const negx_x = v("negx_x");
    const negx_y = v("negx_y");

    const origin_x = v("origin_x");
    const origin_y = v("origin_y");

    const posx_x = v("posx_x");
    const posx_y = v("posx_y");

    const negy_x = v("negy_x");
    const negy_y = v("negy_y");

    const posy_x = v("posy_x");
    const posy_y = v("posy_y");

    //---------------------------------------------------
    // Wintech Alignment
    //---------------------------------------------------

    const alignX =
        -(negx_x + origin_x + posx_x + negy_x + posy_x) / 5;

    const alignY =
        -(negx_y + origin_y + posx_y + negy_y + posy_y) / 5;

    //---------------------------------------------------
    // Stitching
    //---------------------------------------------------

    const stitchXX =
        (((negx_x - origin_x) + (origin_x - posx_x)) / 2) / 5;

    const stitchXY =
        (((negx_y - origin_y) + (origin_y - posx_y)) / 2) / 5;

    const stitchYX =
        (((negy_x - origin_x) + (origin_x - posy_x)) / 2) / 5;

    const stitchYY =
        (((negy_y - origin_y) + (origin_y - posy_y)) / 2) / 5;

    //---------------------------------------------------

    container.find("#out_align_x").text(alignX.toFixed(3) + " μm");
    container.find("#out_align_y").text(alignY.toFixed(3) + " μm");

    container.find("#out_stitch_xx").text(stitchXX.toFixed(3) + " μm/mm");
    container.find("#out_stitch_xy").text(stitchXY.toFixed(3) + " μm/mm");
    container.find("#out_stitch_yx").text(stitchYX.toFixed(3) + " μm/mm");
    container.find("#out_stitch_yy").text(stitchYY.toFixed(3) + " μm/mm");
}