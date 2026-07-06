
var in_start_session = false;
var username = null;

async function onSubmit(url, modalId, on_success, e) {
    e.preventDefault();

    // Remove any existing error messages
    $(modalId).find('.error-message').remove();

    const formData = new FormData(e.target);

    const response = await fetch(url, {
        method: 'POST',
        body: formData
    });

    const data = await response.json();

    if (data.success) {
        if (on_success) {
            on_success(data);
        }
    } else {
        // Remove any existing error messages
        $(modalId).find('.error-message').remove();

        // Show errors
        for (const [key, value] of Object.entries(data.errors)) {
            // if value is a list (of dicts), iterate through them, if it is just a list of strings ignore
            if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
                for (const [index, item] of value.entries()) {
                    for (const [subkey, subvalue] of Object.entries(item)) {  
                        if (!$(modalId).find(`[name="prints-${index}-${subkey}"]`).next('.error-message').length) {
                            $(modalId).find(`[name="prints-${index}-${subkey}"]`).after(`<div class="error-message text-danger small">${subvalue}</div>`);
                        }
                    }
                }
            }
            else {
                // Check if div already exists
                if (!$(modalId).find(`[name="${key}"]`).next('.error-message').length) {
                    $(modalId).find(`[name="${key}"]`).after(`<div class="error-message text-danger small">${value}</div>`);
                }

                // if subkey is "username" and "session_id" is in data.errors, show the "End Previous Session" button and set data-session-id attribute to the session_id value
                if (key === "password" && "session_id" in data.errors) {
                    $('#endPreviousSessionDiv').show();
                    $('#endPreviousSessionButton').attr('data-session-id', data.errors.session_id);
                }
            }
        }
    }
};

$(document).ready(function () {
    var base_socket = io.connect("http://" + document.domain + ":" + location.port + "/users");
    base_socket.emit("connecting");

    window.addEventListener('beforeunload', function (e) {
        base_socket.disconnect();
    });

    $('#loginBtn').on('click', async function() {
        $.get("/users/login_modal", function(html) {
            $("#loginModal").html(html);
            $("#loginModal").modal("show");
        });
    });

    /////////////// Session Header ///////////////
    function updateSessionTime() {
        const el = document.getElementById('session-time');
        if (!el) return;

        const start = new Date(el.dataset.start);
        const now = new Date();

        const elapsed = Math.floor((now - start) / 1000);

        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);

        if (hours > 0) {
            el.textContent = `${hours} hr ${minutes} min`;
        } else {
            el.textContent = `${minutes} min`;
        }
    }

    base_socket.on("session_started", function(data) {
        // get session-active-banner and update its content
        const banner = document.getElementById('session-active-banner');
        if (banner) {
            active_session = {
                id: data.id,
                user: data.user,
                start_time: data.start_time
            };
            // const user = data.user;
            // const start_time = data.start_time;
            // banner.querySelector('strong').textContent = user;
            // banner.querySelector('small').textContent = `Session active • ${start_time}`;

            banner.querySelector('strong').textContent = active_session.user;
            banner.querySelector('small').textContent = `Session active • ${active_session.start_time}`;
        }
        // Show the active session banner
        document.getElementById('session-active-banner').classList.remove('d-none');
        document.getElementById('session-active-banner').classList.add('d-flex');
        document.getElementById('session-available-banner').classList.add('d-none');
        document.getElementById('session-available-banner').classList.remove('d-flex');
    });

    base_socket.on("session_ended", function() {
        // Show the active session banner
        document.getElementById('session-available-banner').classList.remove('d-none');
        document.getElementById('session-available-banner').classList.add('d-flex');
        document.getElementById('session-active-banner').classList.add('d-none');
        document.getElementById('session-active-banner').classList.remove('d-flex');

        // hide any any session modals that are open
        $('#startSessionModal').modal('hide');
        $('#sessionSummaryModal').modal('hide');
        $('#endPrintModal').modal('hide');
        $('#endSessionModal').modal('hide');
    });

    base_socket.on("print_finished", function(data) {
        const id = data.id;
        showEndPrintModal(id);
    });

    updateSessionTime();
    setInterval(updateSessionTime, 60000);

    /////////////// Submit Handlers ///////////////


    document.addEventListener('submit', function (e) {
        if (e.target.matches('#start-session-form')) {
            onSubmit(
                '/users/start_session',
                '#startSessionModal',
                function (response) { // On success
                    $('#startSessionModal').modal('hide');
                    sessionStorage.setItem('showSessionSummaryModal', '1');
                    window.location.reload();
                },
                e
            )
        }
        else if (e.target.matches('#end-session-form')) {
            const id = $('#endSessionModal').data('id');
            const later = e.submitter.value === 'later';

            onSubmit(
                `/users/end_session/${id}?later=${later}`,
                '#endSessionModal',
                function (response) { // On success
                    // reload the page
                    window.location.reload();
                },
                e
            )
        }
        else if (e.target.matches('#register-form')) {
            onSubmit(
                '/users/register_user',
                '#registerModal',
                function (response) { // On success
                    $('#registerModal').modal('hide');
                    if (in_start_session) {
                        username = $('#register-form').find('[name="username"]').val();
                        showStartSessionModal();
                    };
                },
                e
            )
        }
        else if (e.target.matches('#end-print-form')) {
            const printId = $('#endPrintModal').data('id');
            const later = e.submitter.value === 'later';

            onSubmit(
                `/users/end_print/${printId}?later=${later}`,
                '#endPrintModal',
                function (response) { // On success
                    // reload the page
                    // window.location.reload();
                    $('#endPrintModal').modal('hide');
                },
                e
            )
        }
        else if (e.target.matches('#reset-password-form')) {
            onSubmit(
                '/users/reset_password',
                '#resetPasswordModal',
                function (response) { // On success
                    $('#resetPasswordModal').modal('hide');
                    if (in_start_session) { // show start session modal if in_start_session is true
                        username = $('#reset-password-form').find('[name="username"]').val();
                        showStartSessionModal();
                    }
                },
                e
            )
        }
        else if (e.target.matches('#verify-reset-code-form')) {
            onSubmit(
                '/users/reset_code',
                '#resetCodeModal',
                function (response) { // On success
                    $('#resetCodeModal').modal('hide');
                    const username = $('#verify-reset-code-form').find('[name="username"]').val();
                    const token = response.token;
                    showResetPasswordModal(username, token);
                },
                e
            )
        }
        else if (e.target.matches('#login-modal-form')) {
            onSubmit(
                '/users/login_modal',
                '#loginModal',
                function (response) { // On success
                    $('#loginModal').modal('hide');
                    window.location.reload();
                },
                e
            )
        }
    });

    /////////////// Start Session ///////////////
    function showStartSessionModal() {
        $.get("/users/start_session", function(html) {
            $("#startSessionModal").html(html);
            $("#startSessionModal").modal("show");
        });
    }

    $('#startSessionBtn').on('click', function() {
        showStartSessionModal();
    });

    $(document).on('click', '#endPreviousSessionButton', function() {
        const sessionId = $(this).data('session-id');
        $('#startSessionModal').one('hidden.bs.modal', function () {
            showEndSessionModal(sessionId);
        });
        $('#startSessionModal').modal('hide');
    });

    $(document).on('click', '.resetPasswordLink', function() {
        if ($('#startSessionModal').is(':visible')) {
            $('#startSessionModal').one('hidden.bs.modal', function () {
                const username = $('#startSessionModal').find('[name="username"]').val();
                showResetCodeModal(username);
            });
            $('#startSessionModal').modal('hide');
        }
        else if ($('#loginModal').is(':visible')) {
            $('#loginModal').one('hidden.bs.modal', function () {
                const username = $('#loginModal').find('[name="username"]').val();
                showResetCodeModal(username);
            });
            $('#loginModal').modal('hide');
        }
    });

    $('#startSessionModal').on('shown.bs.modal', function () {
        in_start_session = true;
        if (username) {
            $(this).find('[name="username"]').val(username);
            $(this).find('[name="password"]').trigger('focus');
        }
        else{
            $(this).find('[name="username"]').trigger('focus');
        }
    });

    $('#startSessionModal').on('hidden.bs.modal', function () {
        in_start_session = false;
    });


    /////////////// Session Summary ///////////////
    function showSessionSummaryModal() {
        $.get("/users/session_summary", function(html) {
            $("#sessionSummaryModal").html(html);
            $("#sessionSummaryModal").modal("show");
        });
    }

    if (sessionStorage.getItem('showSessionSummaryModal') === '1') {
        sessionStorage.removeItem('showSessionSummaryModal');
        showSessionSummaryModal();
    }
    
    /////////////// Register User ///////////////
    function showRegisterModal() {
        $.get("/users/register_user", function(html) {
            $("#registerModal").html(html);
            $("#registerModal").modal("show");
        });
    }

    // $('#showRegisterModal').on('click', function () {
    $(document).on("click", "#showRegisterModal", function () {
        $('#startSessionModal').one('hidden.bs.modal', function () {
            in_start_session = true;
            showRegisterModal();
        });
        $('#startSessionModal').modal('hide');
    });

    // $('#backToSessionModal').on('click', function () {
    $(document).on("click", "#backToSessionModal", function () {
        $('#registerModal').modal('hide');
    });

    $('#registerModal').on('shown.bs.modal', function () {
        $(this).find('[name="first_name"]').trigger('focus');
    });

    $('#registerModal').on('hidden.bs.modal', function () {
        if (in_start_session) {
            showStartSessionModal();
        }
    });

    ///////////////// Reset Password ///////////////
    function showResetPasswordModal(username=null, token=null) {
        $.get(`/users/reset_password?username=${username}&token=${token}`, function(html) {
            if (typeof html === 'object' && html !== null && 'success' in html && html.success === false) {
                console.log("Reset password request failed: " + JSON.stringify(html.errors));
                return;
            }
            $("#resetPasswordModal").html(html);
            $("#resetPasswordModal").one('shown.bs.modal', function () {
                $("#resetPasswordModal").find('[name="password"]').trigger('focus');
            });
            $("#resetPasswordModal").modal("show");
        });
    }

    function showResetCodeModal(username=null) {
        $.get(`/users/reset_code?username=${username}`, function(html) {
            if (typeof html === 'object' && html !== null && 'success' in html && html.success === false) {
                console.log("Reset code request failed: " + JSON.stringify(html.errors));
                return;
            }
            $("#resetCodeModal").html(html);
            $("#resetCodeModal").one('shown.bs.modal', function () {
                $("#resetCodeModal").find('[name="otc"]').trigger('focus');
            });
            $("#resetCodeModal").modal("show");
        });
    }

    /////////////// Finish Print ///////////////
    function showEndPrintModal(printId) {
        $.get(`/users/print_form?print_id=${printId}`, function(html) {
            $("#endPrintModal").html(html);
            $("#endPrintModal").modal("show");
        });
        $('#endPrintModal').attr('data-id', printId);
    }

    /////////////// End Session ///////////////
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

    $('.logoutBtn').on('click', function() {
        $.get("/logout", function(html) {
            // if open_access is true, just reload the page, otherwise use the rendered html template (login page)
            if (open_access) {
                window.location.reload();
            }
            else {
                document.open();
                document.write(html);
                document.close(); 
            };
        });
    });

    // Load in updated modal partial on open
    $('#endSessionBtn').on('click', function() {
        showEndSessionModal(active_session.id);
    });

    // $('#printer_issues').change(function() {
    $(document).on('change','#printer_issues',function() {
        if ($(this).is(':checked')) {
            $('#printer_issue_details_div').show();
        } else {
            $('#printer_issue_details_div').hide();
        }
    });

    $(document).on('change','.print-success',function() {
        let parent = $(this).closest('.card');
        
        if ($(this).val() === 'no') {
            parent
                .find('.failure-div')
                .show();
        } else {
            parent
                .find('.failure-div')
                .hide();
        }
    });

    $(document).on('change','.failure-mode',function() {
        let parent = $(this).closest('.card');

        if ($(this).val() === 'OTHER_FAILURE') {
            parent
                .find('.other-failure-div')
                .show();
        } else {
            parent
                .find('.other-failure-div')
                .hide();
        }
    });

    $(document).on('click', '.card-header', function () {

        let target = $(this).data('target');

        let chevron = $(this).find('.chevron');

        $(target).collapse('toggle');

        $(target).on('shown.bs.collapse', function () {
            chevron.css('transform', 'rotate(0deg)');
        });

        $(target).on('hidden.bs.collapse', function () {
            chevron.css('transform', 'rotate(90deg)');
        });

    });
});