$(document).ready(function () {
    var load_user_table = async function() {
        const response = await fetch('/users/user_table');
        const html = await response.text();
        document.getElementById('main-table-container').innerHTML = html;
        loadTable('user-table');
    }

    // Load the initial table on page load
    $(document).ready(async function() {
        await load_user_table();

        $('.user-table-delete-btn').on('click', async function() {
            const user_id = $(this).closest('tr').data('id');
            const user_name = $(this).closest('tr').find('td:first').text().trim();
            $.get(`/users/delete_user?user_id=${user_id}`, function(html) {
                if (typeof html === 'object' && html !== null && 'success' in html && html.success === false) {
                    console.log("Delete user request failed: " + JSON.stringify(html.errors));
                    return;
                }

                const token = html.token;
                $("#print-alert-title").text("Delete User");
                $("#print-alert-body").text("Are you sure you want to delete this user (" + user_name + ")? This action cannot be undone.");
                $("#print-alert-body").append(`<div id="user-id-to-delete" data-user-id="${user_id}" data-reset-token="${token}" style="display:none;"></div>`);
                $('#confirmModal').modal('show');
            });
        });

        $('.user-table-reset-btn').on('click', async function() {
            const user_id = $(this).closest('tr').data('id');
            $.get(`/users/reset_password?id=${user_id}`, function(html) {
                if (typeof html === 'object' && html !== null && 'success' in html && html.success === false) {
                    console.log("Reset password request failed: " + JSON.stringify(html.errors));
                    return;
                }
                $("#resetPasswordModal").html(html);
                $("#resetPasswordModal").modal("show");
            });
        });

        $(".user-table-permission-btn").on("click", async function () {
            const user_id = $(this).closest("tr").data("id");
            const $btn = $(this)
            console.log("Permission button clicked for user ID: " + user_id);
            $.get(`/users/change_permission?id=${user_id}`, function(response) {
                if (response.success) {
                    const token = response.token;
                    const value = $btn.find("input[type='checkbox']").is(":checked");
                    var type = "";
                    if ($btn.closest("td").hasClass("user-table-col-print-permissions")) {
                        type = "print";
                    }
                    else if ($btn.closest("td").hasClass("user-table-col-calibration-permissions")) {
                        type = "calibration";
                    }
                    else if ($btn.closest("td").hasClass("user-table-col-advanced-permissions")) {
                        type = "advanced";
                    }
                    else if ($btn.closest("td").hasClass("user-table-col-admin-permissions")) {
                        type = "admin";
                    }

                    $.ajax({
                        url: `/users/change_permission?id=${user_id}&permission=${type}&value=${value}&token=${token}`,
                        type: 'POST',
                        success: function(response) {
                            if (response.success) {
                                console.log(`Successfully changed ${type} permission for user ID ${user_id} to ${value}`);
                            } else {
                                console.error("Failed to change permission: " + JSON.stringify(response.errors));
                            }
                        },
                        error: function(xhr, status, error) {
                            console.error("Error changing permission: " + error);
                        }
                    });
                }
                else {
                    console.error("Failed to get token for changing permission: " + JSON.stringify(response.errors));
                }
            });
        });

        $("#print-alert-confirm").click(function () {
            const user_id = $("#user-id-to-delete").data("user-id");
            const token = $("#user-id-to-delete").data("reset-token");
            console.log(`Deleting user with ID: ${user_id} and reset token: ${token}`);
            $.ajax({
                url: `/users/delete_user?user_id=${user_id}&token=${token}`,
                type: 'POST',
                success: function(response) {
                    $('#confirmModal').modal('hide');
                    if (response.success) {
                        load_user_table();
                    } else {
                        console.error("Failed to delete user: " + JSON.stringify(response.errors));
                    }
                },
                error: function(xhr, status, error) {
                    console.error("Error deleting user: " + error);
                }
            });
        });

        $("#confirmModal").on("hidden.bs.modal", function () {
            $("#user-id-to-delete").remove();
            $("#print-alert-title").text("");
            $("#print-alert-body").text("");
        });
    });

    $('#addUserBtn').on('click', function () {
        $.get("/users/register_user", function(html) {
            $("#registerModal").html(html);
            $("#registerModal").modal("show");
        });
    });

    $('#registerModal').on('hidden.bs.modal', function () {
        window.location.reload();
    });
});
