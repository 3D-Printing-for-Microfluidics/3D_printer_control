var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");
    socket.emit("connecting");

    let audioQueue = [];
    let isPlaying = false;
    let lastAlertTime = 0;
    const ALERT_TIMEOUT_MS = 5000;
    const NEXT_SOUND_DELAY_MS = 1000;
    function playNextSound() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            return;
        }
        isPlaying = true;
        const sound = audioQueue.shift();
        const audio = new Audio("/static/audio/" + sound);
        audio.preload = "auto";
        audio.onended = function () {
            setTimeout(playNextSound, NEXT_SOUND_DELAY_MS);
        };
        audio.play().catch(function (error) {
            console.warn("Audio blocked:", error);
            setTimeout(playNextSound, NEXT_SOUND_DELAY_MS);
        });
    }

    function play_sound(sound) {
        // Throttle alert.mp3
        if (sound === "alert.mp3") {
            const now = Date.now();
            if (now - lastAlertTime < ALERT_TIMEOUT_MS) {
                return;
            }
            lastAlertTime = now;
        }
        audioQueue.push(sound);
        if (!isPlaying) {
            playNextSound();
        }
    }

    socket.on("play_sound", function (message) {
        let sound = message.sound;
        play_sound(sound);
    });

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
            timer = setTimeout(logout, 7200000);
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
        play_sound("alert.mp3");
    });

    socket.on("bootstrap alert", function (message) {
        console.log(message);
        let flash_msg = `
       <div class="alert alert-${message.category}">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
        <pre>${message.text}</pre>
       </div>
        `;
        $("#manual-controls").before(flash_msg);
    });
});
