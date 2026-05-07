// Creates its own Manual namespace socket (keeps it self-contained).
const socketPlanar = io("/manual");

(function () {
  const $target = document.getElementById("planar-target");
  const $status = document.getElementById("planar-status");
  const $btnTighten = document.getElementById("planar-tighten-btn");
  const $btnLoosen  = document.getElementById("planar-loosen-btn");
  const $btnStop    = document.getElementById("planar-stop-btn");

  function setBusy(busy) {
    [$btnTighten, $btnLoosen, $target].forEach(el => el.disabled = busy);
    $btnStop.disabled = !busy;
  }

  function parseTorque() {
    const v = parseFloat($target.value);
    return isFinite(v) && v >= 0 ? v : null;
  }

  // --- Event wiring ---
  $btnTighten.addEventListener("click", () => {
    const t = parseTorque();
    if (t === null) { $target.focus(); $target.reportValidity?.(); return; }
    setBusy(true);
    socketPlanar.emit("planar_start", { direction: "tighten", torque_kgmm: t });
  });

  $btnLoosen.addEventListener("click", () => {
    const t = parseTorque();
    if (t === null) { $target.focus(); $target.reportValidity?.(); return; }
    setBusy(true);
    socketPlanar.emit("planar_start", { direction: "untighten", torque_kgmm: t });
  });

  $btnStop.addEventListener("click", () => {
    socketPlanar.emit("planar_stop");
  });

  // Keep target synced if user presses Enter in the box (optional).
  $target.addEventListener("change", () => {
    const t = parseTorque();
    if (t !== null) {
      socketPlanar.emit("planar_set_target", { torque_kgmm: t });
    }
  });

  // --- Server push / polling ---
  socketPlanar.on("planar_status", (msg) => {
    // msg: { running: bool, torque_target_kgmm: number|string }
    const running = !!msg?.running;
    const tgt = msg?.torque_target_kgmm;
    if ($target.value === "" && tgt != null) $target.value = tgt;
    $status.textContent = `Status: ${running ? "Running" : "Idle"}  •  Target: ${tgt ?? "—"} kg·mm`;
    setBusy(running);
  });

  // Some servers might also emit a completion event; handle it if present.
  socketPlanar.on("planar_done", () => {
    socketPlanar.emit("planar_status_query");
  });

  // Poll status periodically so we don’t need special callbacks in the driver.
  function poll() { socketPlanar.emit("planar_status_query"); }
  poll();                      // initial
  setInterval(poll, 1000);     // every second
})();
