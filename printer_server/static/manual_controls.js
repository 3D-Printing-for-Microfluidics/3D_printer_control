var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");
    socket.emit("connecting");

    // After 60 minutes of inactivity, close socket and timeout web page
    var event = 'click',
        timer,
        delay = 10000,
        logout = function () {
            document.removeEventListener(event, reset, false);
            var content = 'This page has timed out. Please reload the page.';
            document.getElementById('base-body').innerHTML = content;
            socket.disconnect();
        },
        reset = function () {
            clearTimeout(timer);
            timer = setTimeout(logout, 3600000);
        };

    document.addEventListener(event, reset, false);
    reset();

    // Make sure the socket is immediately disconnected on window reload or close
    // This appears to work on Chrome and Edge but only partially on on Safari.
    // On Safari, if the window is closed it works, but if it is reloaded you need to wait for the timeout
    window.addEventListener('beforeunload', function (e) {
        socket.disconnect();
    });

    socket.on("hardware_failure", function (message) {
        const contentDiv = document.querySelector(`.container.${message}`);
  
        if (contentDiv) {
            // Check if the overlay already exists
            const existingOverlay = contentDiv.querySelector('.overlay');
        
            // Only add the overlay if it doesn't already exist
            if (!existingOverlay) {
                // Create overlay div
                const overlay = document.createElement("div");
                overlay.className = "overlay";
                overlay.innerHTML = "Failed";
                
                // Add the overlay and disable interaction
                contentDiv.classList.add("dimmed");
                contentDiv.appendChild(overlay);
            }
        }
    });
});
