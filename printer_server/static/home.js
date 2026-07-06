var start_job_id = "";
var delete_job_id;
var critical_error_process = ""
let sessionTimeout = null;
let countdownInterval = null;

function clearSessionTimers() {
    if (sessionTimeout) {
        clearTimeout(sessionTimeout);
        sessionTimeout = null;
    }

    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
}

function endSession() {
    clearSessionTimers();

    $.post(`/users/end_session_timeout/${active_session.id}?later=True`, function (data) {
        if (data.success) {
            console.log("Session ended");
            location.reload();
        } else {
            console.log("Session end failed:", data.errors);
        }
    });
}


if (loadcell_exists) {
    var loadcell_trace = {
        x: [new Date()],
        y: [0],
        mode: 'lines',
        name: "1",
        type: "scattergl",
        line: {
            shape: 'spline',
            color: 'rgb(255, 255, 255)'
        }
    };
    var loadcell_traces = [loadcell_trace];
    var initial_point_removed = false;

    function draw_loadcell_graph() {
        let defaultPlotlyConfiguration = {
            displayModeBar: false,
            displaylogo: false,
            scrollZoom: true,
            showTips: false
        };

        let layout = {
            xaxis: {
                linecolor: 'white',
                linewidth: 1,
                mirror: true,
                showticklabels: false
            },
            yaxis: {
                ticksuffix: "",
                range: [-50, 50],
                linecolor: 'white',
                linewidth: 1,
                mirror: true
            },
            margin: {
                l: 40,
                r: 20,
                b: 40,
                t: 20,
                pad: 0
            },
            legend: {
                x: 0,
                y: 1,
                traceorder: 'normal',
                borderwidth: 2
            },
            autosize: true,
            height: 250,
            paper_bgcolor: '#222',
            plot_bgcolor: '#222',
            font: {
                color: '#999'
            }
        }
        Plotly.plot('loadcell-data',
            loadcell_traces,
            layout, defaultPlotlyConfiguration);

    }

    function update_loop(message) {
        let data = message.data;
        if (data != 0) {
            if (!initial_point_removed) {
                // Remove the initial point
                loadcell_traces[0].x.splice(0, 1);
                loadcell_traces[0].y.splice(0, 1);
                initial_point_removed = true;
            }

            data.forEach(
                element => {
                    let time = new Date(element.timestamp);
                    let force = element.force;

                    Plotly.extendTraces('loadcell-data',
                        {
                            y: [[force]],
                            x: [[time]]
                        },
                        [0], 750)
                }
            )
        }
    }
}

var show_print_btn = function (btn) {
    $(".printer-btn").prop("disabled", true).addClass("d-none");
    $(btn).prop("disabled", false).removeClass("d-none");
};

var show_degas_btn = function (btn) {
    $(".degas-btn").prop("disabled", true).addClass("d-none");
    $(btn).prop("disabled", false).removeClass("d-none");
};

var write_to_message_box = function (message) {
    const message_box = document.getElementById("print-message")
    // allow 1px inaccuracy by adding 1
    const isScrolledToBottom = message_box.scrollHeight - message_box.clientHeight <= message_box.scrollTop + 1

    if (!$.isEmptyObject(message)) {
        let new_text = `<div class='log-message'>${message}</div>`;
        $("#print-message").append(new_text);
    }

    // scroll to bottom if isScrolledToBottom is true
    if (isScrolledToBottom) {
        message_box.scrollTop = message_box.scrollHeight - message_box.clientHeight
    }
}

$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/printing");
    socket.emit("connecting");

    let audioQueue = [];
    let isPlaying = false;
    let lastAlertTime = 0;
    const ALERT_TIMEOUT_MS = 5000;
    const NEXT_SOUND_DELAY_MS = 1000;
    function playNextSound() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            return;
        }
        isPlaying = true;
        const sound = audioQueue.shift();
        const audio = new Audio("/static/audio/" + sound);
        audio.preload = "auto";
        audio.onended = function () {
            setTimeout(playNextSound, NEXT_SOUND_DELAY_MS);
        };
        audio.play().catch(function (error) {
            console.warn("Audio blocked:", error);
            setTimeout(playNextSound, NEXT_SOUND_DELAY_MS);
        });
    }

    function play_sound(sound) {
        // Throttle alert.mp3
        if (sound === "alert.mp3") {
            const now = Date.now();
            if (now - lastAlertTime < ALERT_TIMEOUT_MS) {
                return;
            }
            lastAlertTime = now;
        }
        audioQueue.push(sound);
        if (!isPlaying) {
            playNextSound();
        }
    }

    socket.on("play_sound", function (message) {
        let sound = message.sound;
        play_sound(sound);
    });

    if (loadcell_exists) {
        // Set up Loadcell graph
        draw_loadcell_graph();
    }

    // check if degas state is available
    if (typeof degas_state !== "undefined") {
        try {
            if (degas_state == "idle") {
                show_degas_btn("#start-degas-btn");
            }
            else if (degas_state == "running") {
                show_degas_btn("#stop-degas-btn");
            }
            else if (degas_state == "finish") {
                show_degas_btn("#finish-degas-btn");
            }
            else if (degas_state == "none") {
                show_degas_btn();
            }
        } catch (error) {
            console.error(error);
        }
    }

    // Set up the drag/drop zone.
    initDropbox();

    // After 60 minutes of inactivity, close socket and timeout web page
    var event = 'click',
        timer,
        delay = 10000,
        logout = function () {
            document.removeEventListener(event, reset, false);
            var content = 'This page has timed out. Please reload the page.';
            document.getElementById('base-body').innerHTML = content;
            socket.disconnect();
        },
        reset = function () {
            clearTimeout(timer);
            timer = setTimeout(logout, 7200000);
        };

    document.addEventListener(event, reset, false);
    reset();

    // Make sure the socket is immediately disconnected on window reload or close
    // This appears to work on Chrome and Edge but only partially on on Safari.
    // On Safari, if the window is closed it works, but if it is reloaded you need to wait for the timeout
    window.addEventListener('beforeunload', function (e) {
        socket.disconnect();
    });

    $("#clear-print-message").on("click", function () {
        $("#print-message > div").remove();
    });

    $("#create-job").on("click", function () {
        $("#uploadModal").modal("show");
    });

    $("#job-table").on("click", ".clickable-row", function (event) {
        if ($(this).hasClass("table-success")) {
            $(this).removeClass("table-success");
            start_job_id = "";
            $("#start-btn").prop("disabled", true);
        } else {
            $(this).addClass("table-success").siblings().removeClass("table-success");
            start_job_id = $(this).attr("id").replace("row-", "")
            $("#start-btn").prop("disabled", false);
        }
    });

    if (loadcell_exists) {
        var show_loadcell = function (btn) {
            $("#toggle-loadcell").text("Hide loadcell data");
            $("#collapseLoadcell").addClass('show');
            socket.emit("request_loadcell_data");
        };

        var hide_loadcell = function (btn) {
            $("#toggle-loadcell").text("Show loadcell data");
            $("#collapseLoadcell").removeClass('show');
            socket.emit("unrequest_loadcell_data");
        };

        $("#toggle-loadcell").on("click", function () {
            if ($("#collapseLoadcell").hasClass("show")) {
                hide_loadcell();
            } else {
                show_loadcell();
            }
        });
    }

    socket.on("busy", function (message) {
        $("#printer-state").text("Printer is busy");
        show_print_btn();
        // start_job_id = "";
        // $(".clickable-row").removeClass("table-success");
    });

    socket.on("uninitialized", function (message) {
        console.log("Printer is uninitialized");
        $("#printer-state").text("Uninitialized");
        show_print_btn("#init-btn, #shutdown-btn");

        let content = '3D printer has been shutdown';
        if (document.getElementById('base-body').innerHTML == content) {
            console.log("Reloading page because printer is uninitialized");
            location.reload();
        }

        
        // Session timeout logic: if there is an active session, and the session start time is more than 60 seconds ago, show a modal to end the session
        const session_start_time = active_session && active_session.start_time ? new Date(active_session.start_time).getTime() / 1000 : null;
        const printer_server_time = server_time ? new Date(server_time).getTime() / 1000 : null;

        if (
            active_session && 
            session_start_time !== null && 
            (printer_server_time - session_start_time) > session_expiration_minutes*60
        ) {
            // Clear any existing timers in case this event fires multiple times
            if (sessionTimeout) clearTimeout(sessionTimeout);
            if (countdownInterval) clearInterval(countdownInterval);

            $("#print-alert-title").text("Session Timeout");

            let countdown = 60;
            $("#print-alert-body").text(
                `Printer is uninitialized while a session is active. The session will timeout in ${countdown} seconds. Click "Confirm" to end the session now or "Cancel" to keep the session active.`
            );

            sessionTimeout = setTimeout(function () {
                $('#confirmModal').modal('hide');
                endSession();
            }, 60000);

            countdownInterval = setInterval(function () {
                countdown--;

                $("#print-alert-body").text(
                    `Printer is uninitialized while a session is active. The session will timeout in ${countdown} seconds. Click "Confirm" to end the session now or "Cancel" to keep the session active.`
                );

                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    countdownInterval = null;
                }
            }, 1000);

            $('#confirmModal').modal('show');
        }
    });

    $('#confirmModal').on('hidden.bs.modal', function () {
        if (sessionTimeout) {
            clearTimeout(sessionTimeout);
            sessionTimeout = null;
        }

        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    });

    socket.on("initialized", function (message) {
        $("#printer-state").text("Initialized");
        show_print_btn("#plana1-btn, #shutdown-btn, #admin-btn");
    });

    socket.on("failed", function (message) {
        $("#printer-state").text("Error");
        show_print_btn("#shutdown-btn, #admin-btn");
    });

    socket.on("planarizing", function (message) {
        $("#printer-state").text("Planarizing");
        show_print_btn("#plana2-btn, #planaCancel-btn, #admin-btn, #shutdown-btn");
    });

    socket.on("planarized", function (message) {
        $("#printer-state").text("Planarized");
        show_print_btn("#planaCancel-btn, #shutdown-btn, #admin-btn");
        $("#start-btn").removeClass("d-none");
        if (start_job_id != "") {
            $("#start-btn").prop("disabled", false);
        }
    });

    socket.on("printing", function (message) {
        $("#printer-state").text("Printing");
        show_print_btn("#pause-btn, #stop-btn, #admin-btn");
        $("#print-progress-bar").css({ "width": message.percent + "%" })
            .attr({ "aria-valuenow": message.percent })
            .text(message.percent + "%");
        $("#print-progress").removeClass("d-none");
    });

    socket.on("print progress", function (message) {
        $("#print-progress-bar").css({ "width": message.percent + "%" })
            .attr({ "aria-valuenow": message.percent })
            .text(message.percent + "%");
    });

    socket.on("paused", function (message) {
        $("#printer-state").text("Paused");
        show_print_btn("#resume-btn, #stop-btn, #admin-btn");
    });

    socket.on("stopped", function (message) {
        $("#printer-state").text("Stopped");
        show_print_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        if (loadcell_exists) {
            hide_loadcell();
        }
        $("#print-progress").addClass("d-none");
    });

    socket.on("completed", function (message) {
        $("#printer-state").text("Completed");
        show_print_btn("#plana1-btn, #shutdown-btn, #admin-btn");
        if (loadcell_exists) {
            hide_loadcell();
        }
        $("#print-progress").addClass("d-none");
    });

    socket.on("shutting down", function (message) {
        $("#printer-state").text("Shutting down");
    });

    socket.on("shutdown completed", function (message) {
        $(".navbar").prop("disabled", true).addClass("d-none");
        let content = '3D printer has been shutdown';
        document.getElementById('base-body').innerHTML = content;

    });

    socket.on("shutdown failed", function (message) {
        // TODO: add a warning window
    });

    socket.on("update_message_box", function (message) {
        write_to_message_box(message);
    });

    socket.on("critical_error", function (message) {
        console.log(message);
        critical_error_process = message["process"]
        if (critical_error_process == "initialization") {
            show_print_btn("#init-btn", "#shutdown-btn");
        }
        else {
            show_print_btn("#shutdown-btn");
        }
        $("#print-alert-title").text(message["title"]);
        $("#print-alert-body").text(message["message"]);
        $('#confirmModal').modal('show');
    });

    $("#print-alert-confirm").click(function () {
        let operation = $("#print-alert-title").text();
        let msg;

        if (operation === "Session Timeout") {
            endSession();
            return;
        }

        if (loadcell_exists && (operation === "Start" || operation === "Planarization Step 1" || operation === "Planarization Step 2" || operation === "Resume")) {
            show_loadcell();
        }

        if (operation === "Start") {
            msg = { job: start_job_id };
        } else if (operation === "Delete Job") {
            msg = { job: delete_job_id };
        } else if (critical_error_process != "") {
            operation = "critical_error_confirm"
            msg = critical_error_process;
        } else {
            msg = {};
        }
        socket.emit(operation.toLowerCase(), msg);
    });

    $("#print-alert-cancel").click(function () {
        let operation = $("#print-alert-title").text();
        let msg;

        if (critical_error_process != "") {
            operation = "critical_error_cancel"
            msg = critical_error_process;
            socket.emit(operation.toLowerCase(), msg);
        }
    });

    $("#confirmModal").on("hidden.bs.modal", function () {
        clearSessionTimers();
        $("#print-alert-title").text("");
        $("#print-alert-body").text("");
        critical_error_process = "";
    });

    $("#init-btn").click(function () {
        $("#print-alert-title").text("Initialize");
        $("#print-alert-body").text("Make sure hardware is powered on and unobstructed. Stages will begin motion.");
    });

    $("#plana1-btn").click(function () {
        $("#print-alert-title").text("Planarization Step 1");
        $("#print-alert-body").text("Is build platform mounted? (Make sure the previous print has been removed if applicable)");
    });

    $("#plana2-btn").click(function () {
        $("#print-alert-title").text("Planarization Step 2");
        $("#print-alert-body").text("Make sure the build platform or silanized glass is flat and tighten the screws.");
    });

    $("#planaCancel-btn").click(function () {
        $("#print-alert-title").text("Cancel Planarization");
        $("#print-alert-body").text("Are you sure you want to cancel planarization? The build platform will return to top.");
    });

    $("#start-btn").click(function () {
        $("#print-alert-title").text("Start");
        $("#print-alert-body").text("Are you sure you want to start printing?");
    });

    $("#pause-btn").click(function () {
        $("#print-alert-title").text("Pause");
        $("#print-alert-body").text("Are you sure you want to pause printing?");
    });

    $("#resume-btn").click(function () {
        $("#print-alert-title").text("Resume");
        $("#print-alert-body").text("Are you sure you want to resume printing?");
    });

    $("#stop-btn").click(function () {
        $("#print-alert-title").text("Stop");
        $("#print-alert-body").text("Are you sure you want to stop printing?");
    });

    try {
        $("#start-degas-btn").click(function () {
            socket.emit("degas", "run");
        });
        $("#stop-degas-btn").click(function () {
            socket.emit("degas", "stop");
        });
        $("#finish-degas-btn").click(function () {
            socket.emit("degas", "finish");
        });
        socket.on("update_degas_state", function (message) {
            if (message == "idle") {
                show_degas_btn("#start-degas-btn");
            }
            else if (message == "running") {
                show_degas_btn("#stop-degas-btn");
            }
            else if (message == "finish") {
                show_degas_btn("#finish-degas-btn");
            }
            else if (message == "none") {
                show_degas_btn();
            }
        });
    } catch (error) {
        console.error(error);
    }

    $("#shutdown-btn").click(function () {
        $("#print-alert-title").text("Shutdown");
        $("#print-alert-body").text("Make sure 3D printer is not in operation.");
    });

    // Database interaction
    socket.on("job uploaded", function (message) {
        let new_row = `
    <tr id="row-${message.id}" class="clickable-row">
      <th scope="row">${$("#job-table > tbody > tr").length + 1}</th>
      <td>${message.name}</td>
      <td>${message.upload_time}</td>
      <td>${message.upload_ip}</td>
      <td><a class="btn btn-sm btn-warning delete-job" id="delete-job${message.id}" role="button" aria-pressed="true" data-toggle="modal" data-target="#confirmModal">delete</a></td>
    </tr>
        `;

        if (message.is_current_user) {
            $("#job-table > tbody").append(new_row);
            let new_msg = { time: message.upload_time, text: "Print Job (" + message.name + ") Uploaded by " + message.user_name };
        };
        // $("#create-job").text("Upload a job");
        $("#uploadModal").modal("hide");

    });

    $(document).on("click", ".delete-job", function () {
        delete_job_id = $(this).attr("id").replace("delete-job", "");
        $("#print-alert-title").text("Delete Job");
        $("#print-alert-body").text("Are you sure you want to delete this print job?");
    });

    socket.on("job deleted", function (message) {
        $("#row-" + message.job).remove();
    });

    socket.on("bootstrap alert", function (message) {
        let flash_msg = `
       <div class="alert alert-${message.category}">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
        <pre>${message.text}</pre>
       </div>
        `;
        $("#printer-controls").before(flash_msg);
    });

    if (loadcell_exists) {
        socket.on("loadcell_graph_data", function (message) {
            update_loop(message)
        });

        socket.on("loadcell_graph_clear", function (message) {
            Plotly.deleteTraces('loadcell-data', 0);
            loadcell_trace["x"] = [new Date() - 750];
            loadcell_trace["y"] = [0];
            Plotly.addTraces('loadcell-data', loadcell_trace);
        });
    }
});