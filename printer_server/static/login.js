
var username = null;

function setUsername(newUsername) {
    username = newUsername;
}

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

    /////////////// Submit Handlers ///////////////

    document.addEventListener('submit', function (e) {
        if (e.target.matches('#register-form')) {
            onSubmit(
                '/users/register_user',
                '#registerModal',
                function (response) { // On success
                    $('#registerModal').modal('hide');
                    username = $('#register-form').find('[name="username"]').val();
                    $('#username').val(username);
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
                    username = $('#reset-password-form').find('[name="username"]').val();
                    $('#username').val(username);
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
                    console.log("Login successful, redirecting to /");
                    window.location.href = '/';
                },
                e
            )
        }
    });

    /////////////// Register User ///////////////
    function showRegisterModal() {
        $.get("/users/register_user", function(html) {
            $("#registerModal").html(html);
            $("#registerModal").modal("show");
        });
    }

    // $('#showRegisterModal').on('click', function () {
    $(document).on("click", "#showRegisterModal", function () {
        showRegisterModal();
    });

    // $('#backToSessionModal').on('click', function () {
    $(document).on("click", "#backToSessionModal", function () {
        $('#registerModal').modal('hide');
    });

    $('#registerModal').on('shown.bs.modal', function () {
        $(this).find('[name="first_name"]').trigger('focus');
    });

    $('#registerModal').on('hidden.bs.modal', function () {
        username = $('#register-form').find('[name="username"]').val();
        $('#login-modal-form').find('[name="username"]').val(username);
        $('#login-modal-form').find('[name="password"]').trigger('focus');
    });

    $(document).on('click', '.resetPasswordLink', function() {
        const username = $('#loginModal').find('[name="username"]').val();
        showResetCodeModal(username);
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
});