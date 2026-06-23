$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/print_history");

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

    var load_print_table = async function() {
        const response = await fetch('/print_history/print_table');
        const html = await response.text();
        document.getElementById('main-table-container').innerHTML = html;
        loadTable('print-history');
    }

    var load_session_table = async function() {
        const response = await fetch('/print_history/session_table');
        const html = await response.text();
        document.getElementById('main-table-container').innerHTML = html;
        loadTable('session-history');
    }

    // Load in updated modal partial on open
    $('#print-view-tab').on('click', async function() {
        await load_print_table();
    });

    $('#session-view-tab').on('click', async function() {
        await load_session_table();
    });

    // Load the initial table on page load
    $(document).ready(async function() {
        if (session_view) {
            await load_session_table();
        } else {
            await load_print_table();
        }
    });
});
