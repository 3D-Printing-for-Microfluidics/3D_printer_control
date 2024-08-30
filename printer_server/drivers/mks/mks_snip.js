let btn_on = 'btn-info';
let btn_off = 'btn-outline-info';
let chamber_vent = 'bg-light';
let chamber_mid = 'bg-warning';
let chamber_vac = 'bg-success';

var disable_crane_motor_buttons = function () {
    $('.crane-controls button').prop('disabled', true);
}

var enable_crane_motor_buttons = function () {
    $('.crane-controls button').prop('disabled', false);
}

var update_dist_position = function (message) {
    if (!$.isEmptyObject(message)) {
        document.getElementById('distance-state').innerHTML = message;
    }
}


$(document).ready(function () {
    // Initiaize to starting values
    let settings = {
        valve_pump1: Boolean(Number(hardware["mks"]["relay_setting"]["valve_pump1"])),
        valve_vent1: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vent1"])),
        valve_pump2: Boolean(Number(hardware["mks"]["relay_setting"]["valve_pump2"])),
        valve_vent2: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vent2"])),
        valve_vacuum: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vacuum"])),
        stirring: Boolean(Number(hardware["mks"]["relay_setting"]["stirring"])),
        vacuum_pump: Boolean(Number(hardware["mks"]["relay_setting"]["vacuum_pump"])),
        crane: Boolean(Number(hardware["mks"]["relay_setting"]["crane"]))
    };
    let gaugeReading1 = hardware["mks"]["gauge"][0];
    let gaugeReading2 = hardware["mks"]["gauge"][1];
    let target1 = hardware["mks"]["target"][0];
    let target2 = hardware["mks"]["target"][1];
    let atm = hardware["mks"]["atm"];

    updateAllButtonStatus();

    function updateAllButtonStatus() {
        updateButtonStatus("valve_pump1", "OPEN", "CLOSED");
        updateButtonStatus("valve_vent1", "OPEN", "CLOSED");
        updateButtonStatus("valve_pump2", "OPEN", "CLOSED");
        updateButtonStatus("valve_vent2", "OPEN", "CLOSED");
        updateButtonStatus("valve_vacuum", "OPEN", "CLOSED");
        updateButtonStatus("stirring", "ON", "OFF");
        updateButtonStatus("vacuum_pump", "ON", "OFF");
        updateButtonStatus("crane", "ENABLED", "DISABLED");

    }

    function updateButtonStatus(id, on_name, off_name) {
        document.getElementById(`${id}_status`).innerText = settings[id] ? on_name : off_name;
        document.getElementById(id).classList.remove(btn_on, btn_off);
        document.getElementById(id).classList.add(settings[id] ? btn_on : btn_off);
    }

    function updateChamberStatus() {
        let chamber1 = chamber_mid;
        let chamber2 = chamber_mid;

        if (gaugeReading1 >= atm) {
            chamber1 = chamber_vent;
        }
        if (gaugeReading1 <= target1) {
            chamber1 = chamber_vac;
        }

        if (gaugeReading2 >= atm) {
            chamber2 = chamber_vent;
        }
        if (gaugeReading2 <= target2) {
            chamber2 = chamber_vac;
        }

        if (gaugeReading1 < 1.0) {
            document.getElementById('gauge1_reading').innerText = `${gaugeReading1 * 1000} mTorr`;
        }
        else {
            document.getElementById('gauge1_reading').innerText = `${gaugeReading1} Torr`;
        }
        if (gaugeReading2 < 1.0) {
            document.getElementById('gauge2_reading').innerText = `${gaugeReading2 * 1000} mTorr`;
        }
        else {
            document.getElementById('gauge2_reading').innerText = `${gaugeReading2} Torr`;
        }
        document.getElementById('vacuum_chamber1').classList.remove(chamber_vent, chamber_mid, chamber_vac);
        document.getElementById('vacuum_chamber2').classList.remove(chamber_vent, chamber_mid, chamber_vac);
        document.getElementById('vacuum_chamber1').classList.add(chamber1);
        document.getElementById('vacuum_chamber2').classList.add(chamber2);
    }

    function toggleButton(id, on_name, off_name) {
        settings[id] = !settings[id];
        updateButtonStatus(id, on_name, off_name);
        updateChamberStatus();
        socket.emit("mks_switch_relay", { "relay": id, "state": settings[id] });
    }

    socket.on("mks_update_relay_status", function (message) {
        settings = {
            valve_pump1: Boolean(Number(message["relay_setting"]["valve_pump1"])),
            valve_vent1: Boolean(Number(message["relay_setting"]["valve_vent1"])),
            valve_pump2: Boolean(Number(message["relay_setting"]["valve_pump2"])),
            valve_vent2: Boolean(Number(message["relay_setting"]["valve_vent2"])),
            valve_vacuum: Boolean(Number(message["relay_setting"]["valve_vacuum"])),
            stirring: Boolean(Number(message["relay_setting"]["stirring"])),
            vacuum_pump: Boolean(Number(message["relay_setting"]["vacuum_pump"])),
            crane: Boolean(Number(message["relay_setting"]["crane"]))
        };
        updateAllButtonStatus();
    });

    socket.on("mks_update_pressure_readings", function (message) {
        gaugeReading1 = message["gauge"][0];
        gaugeReading2 = message["gauge"][1];
        updateChamberStatus();
    });

    $(".mks_button").click(function () {
        let id = $(this).attr('id');
        if (id.includes("valve")) {
            toggleButton(id, "OPEN", "CLOSED");
        }
        else if (id == "crane") {
            toggleButton(id, "ENABLED", "DISABLED");
        }
        else {
            toggleButton(id, "ON", "OFF");
        }
    });

    socket.on("mks_crane_done", function (message) {
        update_dist_position(message);
        enable_crane_motor_buttons();
    });

    // Calibration motor text inputs for absolute positioning
    $(".crane-cntrl-txt").on('change', function () {
        // Disable calibration motor buttons
        disable_crane_motor_buttons();
        // Parse button content and construct message
        let mm = $(this).val();
        let message = { "mm": mm, "mode": "absolute" };
        // Emit control message with parsed values
        socket.emit("mks_crane_move", message);
    });

    // Calibration motor buttons for relative positioning
    $(".crane-cntrl-btn").click(function () {
        // Disable calibration motor buttons
        disable_crane_motor_buttons();
        // Parse button content and construct message
        let mm = $(this).text();
        let message = { "mm": mm, "mode": "relative" };
        // Emit control message with parsed values
        socket.emit("mks_crane_move", message);
    });

});
