(() => {
  const get = id => document.getElementById(id);
  const message = get('controlMessage');
  const sliders = [['selectFollow', 'follow'], ['switchHotspot', 'hotspot'], ['shutdownPi', 'shutdown']];
  let ready = false, pending = false, systemBusy = false, lastSystemMessage = '';
  function render() {
    get('selectStop').disabled = !ready;
    sliders.forEach(([id]) => { get(id).disabled = !ready || pending || systemBusy; });
  }
  async function request(action) {
    if (!ready || (pending && action !== 'stop')) return;
    window.disableRobotTeleop?.();
    pending = true; render();
    message.textContent = 'Sending request…';
    try {
      const response = await fetch('/api/action', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Robot-Control': window.robotControlToken},
        body: JSON.stringify({action, confirmed: ['follow', 'hotspot', 'shutdown'].includes(action)}),
        signal: AbortSignal.timeout(2000)
      });
      if (!response.ok) throw Error(await response.text());
      message.textContent = action === 'shutdown' ? 'Shutdown requested. Motors stop first.' :
        action === 'hotspot' ? 'Network switch requested. Join YardBot or your home network, then reopen the page.' :
        '';
    } catch (error) { message.textContent = 'Request could not be confirmed: ' + error.message; }
    finally { pending = false; render(); sliders.forEach(([id]) => { get(id).value = 0; }); }
  }
  get('selectStop').onclick = () => request('stop');
  for (const [id, action] of sliders) {
    const slider = get(id);
    let start = null, distance = 0;
    slider.addEventListener('pointerdown', event => {
      const bounds = slider.getBoundingClientRect();
      if (slider.disabled || event.clientX > bounds.left + bounds.width * .25) {
        start = null; event.preventDefault(); return;
      }
      slider.value = 0; start = event.clientX; distance = 0;
    });
    slider.addEventListener('pointermove', event => {
      if (start !== null) distance = Math.max(distance, event.clientX - start);
    });
    slider.addEventListener('change', () => {
      if (start === null) return; // Keyboard users confirm explicitly with Enter.
      const deliberate = start !== null && distance >= slider.getBoundingClientRect().width * .6;
      if (deliberate && Number(slider.value) >= 95) request(action);
      slider.value = 0; start = null; distance = 0;
    });
    window.addEventListener('blur', () => { start = null; distance = 0; slider.value = 0; });
    slider.addEventListener('pointercancel', () => { start = null; distance = 0; slider.value = 0; });
    slider.addEventListener('keydown', event => {
      if (event.key === 'Enter' && Number(slider.value) >= 95) {
        event.preventDefault(); request(action); slider.value = 0;
      }
    });
  }
  window.robotControlsStatus = status => {
    ready = status.live && status.teleop_ready;
    systemBusy = Boolean(status.system_action?.busy);
    if (status.system_action?.message && status.system_action.message !== lastSystemMessage) {
      lastSystemMessage = status.system_action.message; message.textContent = lastSystemMessage;
    }
    render();
  };
  window.robotControlsOffline = () => { ready = false; render(); sliders.forEach(([id]) => { get(id).value = 0; }); };
  window.addEventListener('blur', () => { sliders.forEach(([id]) => { get(id).value = 0; }); });
  render();
})();
