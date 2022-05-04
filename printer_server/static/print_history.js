$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/print_history");

    $('.btn-sm').on('click', function (e) {
        var id = $(this).closest('tr').prop('id');
        socket.emit("add_to_queue", id);
    });

    socket.on("flash", function (message) {
        var flash_msg = `
        <div class="alert alert-${message.category} justify-center">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
         <pre>${message.text}</pre>
        </div>
        `;
        console.log(message)
        $("table").before(flash_msg);
    });

    $('#apply_button').on('click', function (e) {
        location.href = print_history_url + '?start=' + $('#start-date').val() + '&end=' + $('#end-date').val();
    });
});