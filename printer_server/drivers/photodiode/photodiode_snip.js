
var enable_button = function () {
    $(`#download-spectra-btn`).prop('disabled', false);
    $(`#download-spectra-btn`).addClass('btn-outline-info');
    $(`#download-spectra-btn`).removeClass('btn-outline-secondary');
}

var disable_button = function () {
    $(`#download-spectra-btn`).prop('disabled', true);
    $(`#download-spectra-btn`).removeClass('btn-outline-info');
    $(`#download-spectra-btn`).addClass('btn-outline-secondary');
}

var update_tiptilt_positions = function (message) {
    for (var axis of axes) {
        if (!$.isEmptyObject(message)) {
            document.getElementById(`${axis}-state`).innerHTML = message[axis];
        }
    }
}


$(document).ready(function () {

	socket.on("send_photodiode_power", function (message) {
        var pow = message[power];
        var length = message[wavelength]
        enable_button();

    });

    $("#photodiode_power").click(function () {
        socket.emit("read_photodiode_power", $(this).parent().text())
    }); 
    
    $("#wavelength_350_405").click(function () {
        
    });         
    
    $(`#read_photodiode_power`).on("click", function () {
        // socket.emit("read_photodiode_power", $(this).parent().text()); // Example based on loadcell
        socket.emit("get_photodiode_power",{"wavelength":length}) // ... figure out what element its sending 
    }); 


    // ??? Put here one for reading/updating the value outputs?

    // $("#wavelength_350_405 :input").change(function () {
    //     socket.emit("wavelength_350_405", $(this).parent().text());

    // wavelenghtbtn.parent.text.... something???? Later do this? 
    
    // ####### Get socket on to update html element with power reading
});

