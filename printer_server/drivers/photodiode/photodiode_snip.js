
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

$(document).ready(function () {

    // ??? Put here one for reading/updating the value outputs?
// CAN i reuse read_photodiode_power twice, once for the output the other time for updating it?

    // $("#wavelength_350_405 :input").change(function () {
    //     socket.emit("wavelength_350_405", $(this).parent().text());
    // });

    $("#read_photodiode_power :input").change(function () {
        socket.emit("read_photodiode_power", $(this).parent().text());
        // Need to send this: socket.emit("get_photodiode_power",{"wavelength":365}) .. figure out what element its sending 
    }); // wavelenghtbtn.parent.text.... something???? Later do this? 
     
    // ####### Get socket on to update html element with power reading
});