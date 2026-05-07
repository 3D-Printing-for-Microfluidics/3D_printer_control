$(document).ready(function () {
    socket.on("loadcell_return_graph_mode", function (message) {
        if(message == true){
            $(`#newtons`).prop('checked', true).closest('label').addClass('active');
            $(`#counts`).prop('checked', false).closest('label').removeClass('active');
        }
        else{
            $(`#newtons`).prop('checked', false).closest('label').removeClass('active');
            $(`#counts`).prop('checked', true).closest('label').addClass('active');
        }
    });

    socket.on("loadcell_return_running", function (message) {
        if(message == true){
            $(`#loadcell-start`).prop('checked', true).closest('label').addClass('active');
            $(`#loadcell-stop`).prop('checked', false).closest('label').removeClass('active');
        }
        else{
            $(`#loadcell-start`).prop('checked', false).closest('label').removeClass('active');
            $(`#loadcell-stop`).prop('checked', true).closest('label').addClass('active');
        }
    });
    
    $("#loadcell_graph_mode :input").change(function () {
        socket.emit("loadcell_set_graph_mode", $(this).parent().text());
    });

    $("#loadcell_run :input").change(function () {
        var selection = $(this).parent().text().trim();
        if (selection === "Start") {
            socket.emit("loadcell_start");
        } else {
            socket.emit("loadcell_stop");
        }
    });
});