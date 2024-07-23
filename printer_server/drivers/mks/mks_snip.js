let btn_on = 'btn-info';
let btn_off = 'btn-outline-info';
let btn_warn = 'btn-outline-warn';
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
    // After 60 minutes of inactivity, close socket and timeout web page
    socket.emit("subscribe_mks");
    var event = 'click',
        timer,
        delay = 10000,
        logout = function () {
            document.removeEventListener(event, reset, false);
            var content = 'This page has timed out. Please reload the page.';
            document.getElementById('base-body').innerHTML = content;
            socket.emit("unsubscribe_mks");
            socket.disconnect();
        },
        reset = function () {
            clearTimeout(timer);
            timer = setTimeout(logout, 3600000);
        };
    document.addEventListener(event, reset, false);
    window.addEventListener('beforeunload', logout, false);
    reset();

    // Initiaize to starting values
    let pumpSetting = Boolean(Number(hardware["mks"]["relay_setting"]["vacuum_pump"]));
    let craneSetting = Boolean(Number(hardware["mks"]["relay_setting"]["crane"]));
    let valveSetting = {
        valve_pump1: Boolean(Number(hardware["mks"]["relay_setting"]["valve_pump1"])),
        valve_vent1: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vent1"])),
        valve_pump2: Boolean(Number(hardware["mks"]["relay_setting"]["valve_pump2"])),
        valve_vent2: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vent2"])),
        valve_vacuum: Boolean(Number(hardware["mks"]["relay_setting"]["valve_vacuum"])),
    };
    let valveStatus = {
        valve_pump1: Boolean(Number(hardware["mks"]["relay_status"]["valve_pump1"])),
        valve_vent1: Boolean(Number(hardware["mks"]["relay_status"]["valve_vent1"])),
        valve_pump2: Boolean(Number(hardware["mks"]["relay_status"]["valve_pump2"])),
        valve_vent2: Boolean(Number(hardware["mks"]["relay_status"]["valve_vent2"])),
        valve_vacuum: Boolean(Number(hardware["mks"]["relay_status"]["valve_vacuum"])),
    };
    let gaugeReading1 = hardware["mks"]["gauge"][0];
    let gaugeReading2 = hardware["mks"]["gauge"][1];
    let target1 = hardware["mks"]["target"][0];
    let target2 = hardware["mks"]["target"][1];
    let atm = hardware["mks"]["atm"];

    updateAllValveStatus();
    updatePumpStatus();
    updateCraneStatus();
    updateChamberStatus();

    function updatePumpStatus() {
        document.getElementById('pump_status').innerText = pumpSetting ? 'ON' : 'OFF';
        document.getElementById('vacuum_pump').classList.remove(btn_on, btn_off, btn_warn);
        document.getElementById('vacuum_pump').classList.add(pumpSetting ? btn_on : btn_off);
    }

    function updateCraneStatus() {
        document.getElementById('crane_status').innerText = craneSetting ? 'ENABLED' : 'DISABLED';
        document.getElementById('crane_status').classList.remove(btn_on, btn_off, btn_warn);
        document.getElementById('crane_status').classList.add(craneSetting ? btn_on : btn_off);
    }

    function updateAllValveStatus() {
        updateValveStatus("valve_pump1");
        updateValveStatus("valve_vent1");
        updateValveStatus("valve_pump2");
        updateValveStatus("valve_vent2");
        updateValveStatus("valve_vacuum");
    }

    function updateValveStatus(valveId) {
        document.getElementById(`${valveId}_status`).innerText = valveSetting[valveId] ? 'Open' : 'Closed';
        document.getElementById(valveId).classList.remove(btn_on, btn_off);
        document.getElementById(valveId).classList.add(valveSetting[valveId] ? btn_on : btn_off);
        document.getElementById(valveId).classList.add(valveSetting[valveId] ? (valveStatus[valveId] ? btn_on : btn_warn) : (valveStatus[valveId] ? btn_warn : btn_off));
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

    function togglePump() {
        pumpSetting = !pumpSetting;
        updatePumpStatus();
        updateChamberStatus();
        if (pumpSetting) {
            socket.emit("activateRelay", "vacuum_pump");
        }
        else {
            socket.emit("deactivateRelay", "vacuum_pump");
        }
    }

    function toggleValve(valveId) {
        valveSetting[valveId] = !valveSetting[valveId];
        updateValveStatus(valveId);
        updateChamberStatus();
        if (valveSetting[valveId]) {
            socket.emit("activateRelay", valveId);
        }
        else {
            socket.emit("deactivateRelay", valveId);
        }
    }

    socket.on("relay_status_updated", function (message) {
        pumpSetting = Boolean(Number(message["relay_setting"]["vacuum_pump"]));
        craneSetting = Boolean(Number(message["relay_setting"]["crane"]));
        valveSetting = {
            valve_pump1: Boolean(Number(message["relay_setting"]["valve_pump1"])),
            valve_vent1: Boolean(Number(message["relay_setting"]["valve_vent1"])),
            valve_pump2: Boolean(Number(message["relay_setting"]["valve_pump2"])),
            valve_vent2: Boolean(Number(message["relay_setting"]["valve_vent2"])),
            valve_vacuum: Boolean(Number(message["relay_setting"]["valve_vacuum"])),
        };
        valveStatus = {
            valve_pump1: Boolean(Number(message["relay_status"]["valve_pump1"])),
            valve_vent1: Boolean(Number(message["relay_status"]["valve_vent1"])),
            valve_pump2: Boolean(Number(message["relay_status"]["valve_pump2"])),
            valve_vent2: Boolean(Number(message["relay_status"]["valve_vent2"])),
            valve_vacuum: Boolean(Number(message["relay_status"]["valve_vacuum"])),
        };
        updatePumpStatus();
        updateCraneStatus();
        updateAllValveStatus();
    });

    socket.on("pressure_readings_updated", function (message) {
        gaugeReading1 = message["gauge"][0];
        gaugeReading2 = message["gauge"][1];
        updateChamberStatus();
    });

    $("#vacuum_pump").click(function () {
        togglePump();
    });

    $("#valve_pump1").click(function () {
        toggleValve("valve_pump1");
    });

    $("#valve_vent1").click(function () {
        toggleValve("valve_vent1");
    });

    $("#valve_pump2").click(function () {
        toggleValve("valve_pump2");
    });

    $("#valve_vent2").click(function () {
        toggleValve("valve_vent2");
    });

    $("#valve_vacuum").click(function () {
        toggleValve("valve_vacuum");
    });

    socket.on("cranePosition", function (message) {
        console.log(message);
        update_dist_position(message);
        enable_crane_motor_buttons();
    });

    // Calibration motor text inputs for absolute positioning
    $(".crane-cntrl-txt").on('change', function () {
        // Disable calibration motor buttons
        disable_crane_motor_buttons();
        // Parse button content and construct message
        var mm = $(this).val();
        var message = { "mm": mm, "mode": "absolute" };
        // Emit control message with parsed values
        socket.emit("craneMove", message);
    });

    // Calibration motor buttons for relative positioning
    $(".crane-cntrl-btn").click(function () {
        // Disable calibration motor buttons
        disable_crane_motor_buttons();
        // Parse button content and construct message
        var mm = $(this).text();
        var message = { "mm": mm, "mode": "relative" };
        // Emit control message with parsed values
        socket.emit("craneMove", message);
    });

});
