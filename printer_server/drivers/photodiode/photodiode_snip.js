// ??? Put here one for reading/updating the value outputs?
    // CAN i reuse read_photodiode_power twice, once for the output the other time for updating it?
    
$(document).ready(function () {
    $("#wavelength_350_905 :input").change(function () {
        socket.emit("wavelength_350_905", $(this).parent().text());
    });

    $("#read_photodiode_power :input").change(function () {
        socket.emit("read_photodiode_power", $(this).parent().text());
    }); 


     

});