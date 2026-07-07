$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibration_history");

    var load_calibration_table = async function() {
        const response = await fetch('/calibration_history/calibration_table');
        const html = await response.text();
        document.getElementById('main-table-container').innerHTML = html;
        loadTable('calibration-table');
    }

    // Load the initial table on page load
    $(document).ready(async function() {
        await load_calibration_table();
    });
});
