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
    });
});
