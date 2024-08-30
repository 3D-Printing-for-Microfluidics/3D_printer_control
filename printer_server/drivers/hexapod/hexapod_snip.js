$(document).ready(function () {

    check_initialization();

    // ====================== HELPER METHODS
    function send_event(event_name, param_list = []) {
        console.log(event_name);
        if (param_list.length == 0) {
            socket.emit(event_name);
        }
        else {
            console.log(param_list);
            socket.emit(event_name, param_list);
        }
    }

    function update_pivot_fields(new_pivot) {

        // Update html elements
        document.getElementById("pivot_R_state").innerHTML = new_pivot.R.toFixed(0) + "um";
        document.getElementById("pivot_S_state").innerHTML = new_pivot.S.toFixed(0) + "um";
        document.getElementById("pivot_T_state").innerHTML = new_pivot.T.toFixed(0) + "um";

        document.getElementById("pivot_R_state_input").value = parseFloat(new_pivot.R.toFixed(0));
        document.getElementById("pivot_S_state_input").value = parseFloat(new_pivot.S.toFixed(0));
        document.getElementById("pivot_T_state_input").value = parseFloat(new_pivot.T.toFixed(0));
    }

    function update_rotation_fields(rotation) {
        console.log("rotation update", rotation);

        // Update html elements
        document.getElementById("rotation_U_state").innerHTML = (rotation[0]).toFixed(1) + " mrad";
        document.getElementById("rotation_V_state").innerHTML = (rotation[1]).toFixed(1) + " mrad";
        document.getElementById("rotation_W_state").innerHTML = (rotation[2]).toFixed(1) + " mrad";

        document.getElementById("rotation_U_state_input").value = parseFloat((rotation[0]).toFixed(1));
        document.getElementById("rotation_V_state_input").value = parseFloat((rotation[1]).toFixed(1));
        document.getElementById("rotation_W_state_input").value = parseFloat((rotation[2]).toFixed(1));
    }

    function update_translation_fields(translation) {
        console.log("translation update", translation);

        // Update html elements
        document.getElementById("translation_X_state").innerHTML = (translation[0]).toFixed(0) + "um";
        document.getElementById("translation_Y_state").innerHTML = (translation[1]).toFixed(0) + "um";
        document.getElementById("translation_Z_state").innerHTML = (translation[2]).toFixed(0) + "um";

        document.getElementById("translation_X_state_input").value = parseFloat((translation[0]).toFixed(0));
        document.getElementById("translation_Y_state_input").value = parseFloat((translation[1]).toFixed(0));
        document.getElementById("translation_Z_state_input").value = parseFloat((translation[2]).toFixed(0));
    }

    function check_initialization() {
        send_event("check_init");
    }

    $(`.hexapod-cntrl-btn`).click(function () {
        let command_elements = $(this).attr("id").split("_");

        let command_type = command_elements[0];
        let axis = command_elements[1];
        let value = parseFloat(command_elements[2]);

        console.log("command_type", command_type);
        console.log("axis", axis);
        console.log("value", value);

        send_event("axis_step", [command_type, axis, value]);
    });

    var init_btn = document.getElementById("init_btn");
    var set_pivot_btn = document.getElementById("set_pivot_btn");
    var send_command_btn = document.getElementById("send_command_btn");
    var stop_motion_btn = document.getElementById("stop_motion_btn");

    init_btn.onclick = function () {
        send_event("initialize_hexapod");
    }

    socket.on("dynamic_ranges", function (ranges) {
        console.log(ranges);
    });

    socket.on("init_msg", function (init_output) {
        let init_flag = init_output[0]
        let init_error_codes = init_output[1];
        let init_pivot = init_output[2];
        let init_pose = init_output[3];

        let rotation = [init_pose["U"], init_pose["V"], init_pose["W"]];
        let translation = [init_pose["X"], init_pose["Y"], init_pose["Z"]];

        if (init_flag) {
            // Update fields
            update_pivot_fields(init_pivot);
            update_translation_fields(translation);
            update_rotation_fields(rotation);
        }
    });

    set_pivot_btn.onclick = function () {
        // Compile inputs from all the boxes
        let pivot_R_state_text = parseFloat(document.getElementById("pivot_R_state_input").value);
        let pivot_S_state_text = parseFloat(document.getElementById("pivot_S_state_input").value);
        let pivot_T_state_text = parseFloat(document.getElementById("pivot_T_state_input").value);

        // console.log("pivot_R_state_text", pivot_R_state_text);
        // console.log("pivot_S_state_text", pivot_S_state_text);
        // console.log("pivot_T_state_text", pivot_T_state_text);

        // Pack values on a list
        let new_pivot_point = [pivot_R_state_text, pivot_S_state_text, pivot_T_state_text];

        // Send event
        send_event("pivot_command", new_pivot_point);
    }

    socket.on("pivot_update", function (pivot) {
        console.log("pivot update", pivot);
        update_pivot_fields(pivot);
    });

    send_command_btn.onclick = function () {
        // Compile inputs from all the boxes
        let translation_X_state_text = parseFloat(document.getElementById("translation_X_state_input").value);
        let translation_Y_state_text = parseFloat(document.getElementById("translation_Y_state_input").value);
        let translation_Z_state_text = parseFloat(document.getElementById("translation_Z_state_input").value);
        let rotation_U_state_text = parseFloat(document.getElementById("rotation_U_state_input").value);
        let rotation_V_state_text = parseFloat(document.getElementById("rotation_V_state_input").value);
        let rotation_W_state_text = parseFloat(document.getElementById("rotation_W_state_input").value);


        // console.log("translation_X_state_text", translation_X_state_text);
        // console.log("translation_Y_state_text", translation_Y_state_text);
        // console.log("translation_Z_state_text", translation_Z_state_text);
        // console.log("rotation_U_state_text", rotation_U_state_text);
        // console.log("rotation_V_state_text", rotation_V_state_text);
        // console.log("rotation_W_state_text", rotation_W_state_text);

        // Pack values on a list
        let new_pose = [translation_X_state_text, translation_Y_state_text, translation_Z_state_text,
            rotation_U_state_text, rotation_V_state_text, rotation_W_state_text]

        // Send event
        send_event("pose_command", new_pose);
    }

    socket.on("pose_update", function (pose) {
        console.log("pose update", pose);

        let rotation = [pose["U"], pose["V"], pose["W"]];
        let translation = [pose["X"], pose["Y"], pose["Z"]];

        update_translation_fields(translation);
        update_rotation_fields(rotation);
    });

    stop_motion_btn.onclick = function () {
        send_event("stop_motion");
    }

    var request_dynamic_ranges_btn = document.getElementById("request_dynamic_ranges");
    request_dynamic_ranges_btn.onclick = function () {
        send_event("request_dynamic_ranges");
    }
});