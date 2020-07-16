$(document).ready(function () {

    var socket = io.connect("http://" + document.domain + ":" + location.port + "/chart");
    socket.emit("connected");
    console.log("emit connected")

    socket.on("new_data", function (message) {
        // do something with message.data
        console.log('got something')

    });
});