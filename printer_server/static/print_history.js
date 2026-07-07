$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/print_history");

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

    function showEndSessionModal(sessionId) {
        $.get(`/users/end_session/${sessionId}`, function(html) {
            $("#endSessionModal").html(html);
            const waitForContainer = () => {
                const el = document.getElementById("print-container");
                if (!el) {
                    requestAnimationFrame(waitForContainer);
                    return;
                }
                $.get(`/users/print_form?session_id=${sessionId}`, function(inner_html) {
                    el.innerHTML = inner_html;
                });
                $("#endSessionModal").modal("show");
            };
            waitForContainer();
        });
        $('#endSessionModal').attr('data-id', sessionId);
    }

    function showEndPrintModal(printId) {
        $.get(`/users/print_form?print_id=${printId}`, function(html) {
            $("#endPrintModal").html(html);
            $("#endPrintModal").modal("show");
        });
        $('#endPrintModal').attr('data-id', printId);
    }

    // Load the initial table on page load
    $(document).ready(async function() {
        if (session_view) {
            await load_session_table();
        } else {
            await load_print_table();
        }

        $(document).on("click", ".session-history-finish-session-btn", function() {
        // $('.session-history-finish-session-btn').on('click', async function() {
            // get row id
            const session_id = $(this).closest('tr').data('id');
            showEndSessionModal(session_id);
        });

        $(document).on("click", ".print-history-print-log-btn", function() {
        // $('.print-history-print-log-btn').on('click', async function() {
            const print_id = $(this).closest('tr').data('id');
            showEndPrintModal(print_id);
        });

        document.addEventListener('submit', function (e) {
            if (e.target.matches('#end-print-form')) {
                // if in print view, reload the print table, if in session view, reload the session table
                if (session_view) {
                    load_session_table();
                } else {
                    load_print_table();
                }
            }
        });
    });
});
