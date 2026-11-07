(() => {
  const button = document.getElementById('enableTeleop');
  const pad = document.getElementById('joystick');
  const knob = document.getElementById('knob');
  const message = document.getElementById('teleopMessage');
  const badge = document.getElementById('teleopState');
  const dumpButtons = [[document.getElementById('dumpRaise'), 1], [document.getElementById('dumpLower'), -1]];
  const dumpHolds = new Map();
  let dump = 0;
  let owner = null, sequence = 0, x = 0, forward = 0, pointer = null;
  let holdTimer = null, generation = 0, ready = false, inFlight = 0, enabling = false, lastAck = 0, lastReason = '';

  // iOS Safari also needs the prefixed CSS plus explicit gesture suppression.
  // Restrict it to hold controls so the rest of the page remains scrollable.
  for (const control of [button, pad, ...dumpButtons.map(([element]) => element)]) {
    for (const name of ['contextmenu', 'selectstart', 'dragstart']) {
      control.addEventListener(name, event => event.preventDefault());
    }
    for (const name of ['touchstart', 'touchmove']) {
      control.addEventListener(name, event => {
        if (event.cancelable) event.preventDefault();
      }, {passive: false});
    }
  }

  async function post(action, body, keepalive = false) {
    const response = await fetch('/api/teleop/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Robot-Control': window.robotControlToken},
      body: JSON.stringify(body), keepalive,
      signal: keepalive ? undefined : AbortSignal.timeout(1000)
    });
    if (!response.ok) {
      const error = Error(await response.text()); error.serverRejected = true; throw error;
    }
    return response.json();
  }
  function center() {
    x = forward = 0;
    pointer = null;
    knob.style.transform = 'translate(0,0)';
  }
  function resetDump() {
    dumpHolds.clear(); dump = 0;
    dumpButtons.forEach(([control]) => {
      control.disabled = !owner; control.classList.remove('pressed'); control.setAttribute('aria-pressed', 'false');
    });
  }
  function dumpChanged() {
    dump = Math.max(-1, Math.min(1, [...dumpHolds.values()].reduce((a, b) => a + b, 0)));
    dumpButtons.forEach(([control, direction]) => {
      const pressed = [...dumpHolds.values()].includes(direction);
      control.classList.toggle('pressed', pressed); control.setAttribute('aria-pressed', String(pressed));
    });
    transmit(true);
  }
  function cancelHold() {
    clearTimeout(holdTimer); holdTimer = null;
    button.textContent = 'Hold 1 second to enable';
  }
  function disable(reason = 'Web driving disabled.') {
    generation++; cancelHold(); enabling = false;
    document.body.classList.remove('driving');
    const previous = owner; owner = null;
    center(); resetDump(); pad.classList.remove('armed'); pad.setAttribute('aria-disabled', 'true');
    lastReason = reason;
    badge.textContent = 'Disabled'; message.textContent = reason;
    button.disabled = !ready;
    if (previous) post('disable', {owner: previous}, true).catch(() => {});
  }
  async function transmit(force = false) {
    if (!owner || (inFlight >= 2 && !force)) return;
    const current = owner;
    inFlight++;
    try {
      const reply = await post('command', {owner: current, sequence: ++sequence, x, forward, dump});
      if (owner === current && reply.accepted !== false) lastAck = performance.now();
    } catch (error) {
      if (owner === current && (error.serverRejected || performance.now() - lastAck >= 400)) {
        disable('Control interrupted: ' + error.message + '. Enable again to resume.');
      }
    } finally { inFlight--; }
  }
  function beginHold(event) {
    if (button.disabled || owner || enabling || holdTimer || document.hidden) return;
    if (event.type === 'pointerdown' && event.button !== 0) return;
    button.textContent = 'Keep holding…';
    const currentGeneration = generation;
    holdTimer = setTimeout(async () => {
      holdTimer = null; enabling = true; button.disabled = true;
      try {
        const response = await post('enable', {});
        if (currentGeneration !== generation || document.hidden || !document.hasFocus()) {
          post('disable', {owner: response.owner}, true).catch(() => {});
          return;
        }
        owner = response.owner; sequence = 0; lastAck = performance.now(); lastReason = ''; center(); resetDump();
        document.body.classList.add('driving');
        pad.classList.add('armed'); pad.setAttribute('aria-disabled', 'false');
        badge.textContent = 'Enabled'; message.textContent = 'Drag from the center to drive. Release to stop.';
        await transmit(true);
      } catch (error) { disable('Could not enable: ' + error.message); }
      finally { enabling = false; button.textContent = 'Hold 1 second to enable'; }
    }, 1000);
  }
  button.addEventListener('pointerdown', event => {
    if (button.disabled || event.button !== 0) return;
    event.preventDefault();
    button.setPointerCapture(event.pointerId); beginHold(event);
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(name, cancelHold);
  button.addEventListener('keydown', event => {
    if ([' ', 'Enter'].includes(event.key)) { event.preventDefault(); if (!event.repeat) beginHold(event); }
  });
  button.addEventListener('keyup', cancelHold);
  document.getElementById('disableTeleop').onclick = () => disable();
  pad.addEventListener('pointerdown', event => {
    if (!owner || pointer !== null || event.button !== 0) return;
    const bounds = pad.getBoundingClientRect();
    const dx = event.clientX - bounds.left - bounds.width / 2;
    const dy = event.clientY - bounds.top - bounds.height / 2;
    // A tap near the rim never starts movement: pick up the centered knob first.
    if (Math.hypot(dx, dy) > 38) return;
    pointer = event.pointerId; pad.setPointerCapture(pointer); event.preventDefault();
  });
  pad.addEventListener('pointermove', event => {
    if (event.pointerId !== pointer || !owner) return;
    const bounds = pad.getBoundingClientRect(), radius = bounds.width / 2 - 36;
    let dx = (event.clientX - bounds.left - bounds.width / 2) / radius;
    let dy = (event.clientY - bounds.top - bounds.height / 2) / radius;
    const length = Math.hypot(dx, dy);
    if (length > 1) { dx /= length; dy /= length; }
    x = Math.abs(dx) < .08 ? 0 : dx; forward = Math.abs(dy) < .08 ? 0 : -dy;
    knob.style.transform = `translate(${dx * radius}px,${dy * radius}px)`;
    event.preventDefault();
  });
  function release(event) {
    if (event.pointerId !== pointer) return;
    center(); transmit(true);
  }
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) pad.addEventListener(name, release);
  for (const [control, direction] of dumpButtons) {
    control.addEventListener('pointerdown', event => {
      if (!owner || event.button !== 0) return;
      event.preventDefault(); control.setPointerCapture(event.pointerId);
      dumpHolds.set('pointer:' + event.pointerId, direction); dumpChanged();
    });
    const endPointer = event => {
      if (dumpHolds.delete('pointer:' + event.pointerId)) dumpChanged();
    };
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) control.addEventListener(name, endPointer);
    control.addEventListener('keydown', event => {
      if (!owner || ![' ', 'Enter'].includes(event.key)) return;
      event.preventDefault();
      if (!event.repeat) { dumpHolds.set('key:' + control.id, direction); dumpChanged(); }
    });
    control.addEventListener('keyup', event => {
      if ([' ', 'Enter'].includes(event.key)) {
        event.preventDefault();
        if (dumpHolds.delete('key:' + control.id)) dumpChanged();
      }
    });
    control.addEventListener('blur', () => {
      if (dumpHolds.delete('key:' + control.id)) dumpChanged();
    });
  }
  window.addEventListener('blur', () => disable('Page lost focus. Enable again to drive.'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) disable('Page hidden. Web driving disabled.'); });
  window.addEventListener('pagehide', () => disable());
  window.addEventListener('keydown', event => { if (event.key === 'Escape') disable(); });
  window.disableRobotTeleop = () => disable('Web driving ended by a page action.');
  window.robotTeleopOffline = () => { ready = false; disable('Robot unavailable. Web driving disabled.'); };
  window.robotTeleopStatus = status => {
    ready = status.live && status.teleop_ready;
    if (!ready && (owner || enabling)) disable('Robot is not ready for web driving.');
    button.disabled = !ready || Boolean(owner) || enabling;
    if (!owner && !enabling) message.textContent = lastReason || (ready ? 'Hold enable for one second, then drag from the center.' : 'Waiting for robot connection.');
  };
  setInterval(() => transmit(), 100);
})();
