let pumpStatus = false;
let valveStatus = {
    valve1: false,
    valve2: false,
    valve3: false,
    valve4: false,
    valve5: false
};

let btn_on = 'btn-info';
let btn_off = 'btn-outline-info';
let chamber_vent = 'bg-light';
let chamber_mid = 'bg-warning';
let chamber_vac = 'bg-success';

function togglePump() {
    pumpStatus = !pumpStatus;
    document.getElementById('pump-status').innerText = pumpStatus ? 'ON' : 'OFF';
    document.getElementById('vacuum-pump').classList.remove('btn-info', 'btn-outline-info');
    document.getElementById('vacuum-pump').classList.add(pumpStatus ? btn_on : btn_off);
    updateChamberStatus();
}

function toggleValve(valveId) {
    valveStatus[valveId] = !valveStatus[valveId];
    document.getElementById(`${valveId}-status`).innerText = valveStatus[valveId] ? 'Open' : 'Closed';
    document.getElementById(valveId).classList.remove('btn-info', 'btn-outline-info');
    document.getElementById(valveId).classList.add(valveStatus[valveId] ? btn_on : btn_off);
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

    document.getElementById('gauge1-reading').innerText = `${gaugeReading1} Torr`;
    document.getElementById('gauge2-reading').innerText = `${gaugeReading2} Torr`;
    document.getElementById('vacuum-chamber1').classList.remove('bg-light', 'bg-warning', 'bg-success');
    document.getElementById('vacuum-chamber2').classList.remove('bg-light', 'bg-warning', 'bg-success');
    document.getElementById('vacuum-chamber1').classList.add(chamber1);
    document.getElementById('vacuum-chamber2').classList.add(chamber2);

}

$(document).ready(function () {
    // socket.on("keyence_setpoint_updated", function (message) {
    //     update_keyence_positions(message);
    // });

    // $("#loadcell_graph_mode :input").change(function () {
    //     socket.emit("loadcell_graph_mode", $(this).parent().text());
    // });


});



// // Initialize the system
// document.getElementById('gauge1-reading').innerText = `650 Torr`;
// document.getElementById('gauge2-reading').innerText = `650 Torr`;
// document.getElementById('vacuum-pump').className = pump_off;
// document.getElementById('valve1').className = valve_on;
// document.getElementById('valve2').className = valve_on;
// document.getElementById('valve3').className = valve_on;
// document.getElementById('valve4').className = valve_on;
// document.getElementById('valve5').className = valve_on;
// document.getElementById('vacuum-chamber1').className = chamber_vent;
// document.getElementById('vacuum-chamber2').className = chamber_vent;
