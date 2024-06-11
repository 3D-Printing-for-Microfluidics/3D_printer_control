$(document).ready(function () {
    // socket.on("keyence_setpoint_updated", function (message) {
    //     update_keyence_positions(message);
    // });

    // $("#loadcell_graph_mode :input").change(function () {
    //     socket.emit("loadcell_graph_mode", $(this).parent().text());
    // });
});

let pumpStatus = false;
let valveStatus = {
    valve1: false,
    valve2: false,
    valve3: false,
    valve4: false,
    valve5: false
};

let valve_on = 'btn btn-info valve';
let valve_off = 'btn btn-outline-info valve';
let pump_on = 'btn btn-info vacuum-pump';
let pump_off = 'btn btn-outline-info vacuum-pump';
let chamber_vent = 'card text-white bg-light';
let chamber_mid = 'card text-white bg-warning';
let chamber_vac = 'card text-white bg-success';

function togglePump() {
    pumpStatus = !pumpStatus;
    document.getElementById('pump-status').innerText = pumpStatus ? 'ON' : 'OFF';
    document.getElementById('vacuum-pump').className = pumpStatus ? pump_on : pump_off;
    updateChamberStatus();
}

function toggleValve(valveId) {
    valveStatus[valveId] = !valveStatus[valveId];
    document.getElementById(`${valveId}-status`).innerText = valveStatus[valveId] ? 'Open' : 'Closed';
    document.getElementById(valveId).className = valveStatus[valveId] ? valve_on : valve_off;
    updateChamberStatus();
}

function updateChamberStatus() {
    let gaugeReading1 = 760;
    let gaugeReading2 = 760;
    let chamber1 = chamber_vent;
    let chamber2 = chamber_vent;

    if (!valveStatus.valve2) {
        if (pumpStatus && valveStatus.valve5 && valveStatus.valve1) {
            gaugeReading1 = 0.1; // Example value when pump is on and valve1 is open
            chamber1 = chamber_vac;
        }
        else if (pumpStatus || !valveStatus.valve5) {
            gaugeReading1 = 123; // Example value for intermediate state
            chamber1 = chamber_mid;
        }
    }

    if (!valveStatus.valve4) {
        if (pumpStatus && valveStatus.valve5 && valveStatus.valve3) {
            gaugeReading2 = 0.1; // Example value when pump is on and valve1 is open
            chamber2 = chamber_vac;
        }
        else if (pumpStatus || !valveStatus.valve5) {
            gaugeReading2 = 123; // Example value for intermediate state
            chamber2 = chamber_mid;
        }
    }

    document.getElementById('gauge1-reading').innerText = `\n${gaugeReading1} Torr\n\n`;
    document.getElementById('gauge2-reading').innerText = `\n${gaugeReading2} Torr\n\n`;
    document.getElementById('vacuum-chamber1').className = chamber1;
    document.getElementById('vacuum-chamber2').className = chamber2;

}

// // Initialize the system
// document.getElementById('gauge1-reading').innerText = `\n650 Torr\n\n`;
// document.getElementById('gauge2-reading').innerText = `\n650 Torr\n\n`;
// document.getElementById('vacuum-pump').className = pump_off;
// document.getElementById('valve1').className = valve_on;
// document.getElementById('valve2').className = valve_on;
// document.getElementById('valve3').className = valve_on;
// document.getElementById('valve4').className = valve_on;
// document.getElementById('valve5').className = valve_on;
// document.getElementById('vacuum-chamber1').className = chamber_vent;
// document.getElementById('vacuum-chamber2').className = chamber_vent;
