
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
            on_success();
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
        console.log("Session started:", data);
        // get session-active-banner and update its content
        const banner = document.getElementById('session-active-banner');
        if (banner) {
            const user = data.user;
            const start_time = data.start_time;
            banner.querySelector('strong').textContent = user;
            banner.querySelector('small').textContent = `Session active • ${start_time}`;
        }
        // Show the active session banner
        document.getElementById('session-active-banner').classList.remove('d-none');
        document.getElementById('session-active-banner').classList.add('d-flex');
        document.getElementById('session-available-banner').classList.add('d-none');
        document.getElementById('session-available-banner').classList.remove('d-flex');
    });

    base_socket.on("session_ended", function() {
        console.log("Session ended");
        // Show the active session banner
        document.getElementById('session-available-banner').classList.remove('d-none');
        document.getElementById('session-available-banner').classList.add('d-flex');
        document.getElementById('session-active-banner').classList.add('d-none');
        document.getElementById('session-active-banner').classList.remove('d-flex');
    });

    updateSessionTime();
    setInterval(updateSessionTime, 60000);

    /////////////// Start Session ///////////////
    $('#startSessionBtn').on('click', function() {
        $('#sessionModal')
            .one('shown.bs.modal', function () {
                $(this).find('[name="username"]').trigger('focus');
            })
            .modal('show');
    });

    function onSessionStartSuccess() {
        // reload the page
        window.location.reload();
    }

    document.getElementById('start-session-form').addEventListener('submit', onSubmit.bind(null, '/users/start-session', '#sessionModal', onSessionStartSuccess));

    $('#showRegisterModal').on('click', function () {
        console.log(base_socket);
        $('#sessionModal').one('hidden.bs.modal', function () {
            $('#registerModal')
                .one('shown.bs.modal', function () {
                    $(this).find('[name="first_name"]').trigger('focus');
                })
                .modal('show');
        });

        $('#sessionModal').modal('hide');
    });

    $('#backToSessionModal').on('click', function () {
        $('#registerModal').one('hidden.bs.modal', function () {
            $('#sessionModal')
                .one('shown.bs.modal', function () {
                    $(this).find('[name="username"]').trigger('focus');
                })
                .modal('show');
        });

        $('#registerModal').modal('hide');
    });

    function onRegisterSuccess() {
        $('#registerModal').one('hidden.bs.modal', function () {
            $('#sessionModal')
                .one('shown.bs.modal', function () {
                    const username = $('#register-form').find('[name="username"]').val();
                    $('#sessionModal').find('[name="username"]').val(username);
                    $(this).find('[name="password"]').trigger('focus');
                })
                .modal('show');
        });

        $('#registerModal').modal('hide');
    }

    document.getElementById('register-form').addEventListener('submit', onSubmit.bind(null, '/users/register_user', '#registerModal', onRegisterSuccess));

    /////////////// End Session ///////////////

    // Load in updated modal partial on open
    $('#endSessionBtn').on('click', function() {
        $('#endSessionModal').one('shown.bs.modal', async function () {
                const response = await fetch('/users/print_form');
                const html = await response.text();
                document.getElementById('print-container').innerHTML = html;
            })
            .modal('show');
    });

    function onSessionEndSuccess() {
        // reload the page
        console.log("Session ended successfully");
        window.location.reload();
    }

    document.getElementById('end-session-form').addEventListener('submit', onSubmit.bind(null, '/users/end_session', '#endSessionModal', onSessionEndSuccess));

    $('#printer_issues').change(function() {
        
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