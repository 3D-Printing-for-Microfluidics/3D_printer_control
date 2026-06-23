$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/calibration_history");

    socket.on("flash", function (message) {
        let flash_msg = `
        <div class="alert alert-${message.category} justify-center">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
         <pre>${message.text}</pre>
        </div>
        `;
        console.log(message)
        $("table").before(flash_msg);
    });

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
