(() => {
  const text = (id, value) => { document.getElementById(id).textContent = value; };
  const duration = seconds => {
    if (seconds == null) return '—';
    const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds / 60) % 60;
    return hours ? `${hours}h ${minutes}m` : `${minutes}m ${Math.floor(seconds % 60)}s`;
  };
  const states = {clear: 'Clear', stop: 'Forward stop (<20 cm)', slow: 'Forward limited (≤100 cm)',
                  unreliable: 'Unreliable signal', sensor_stale: 'Sensor not updating',
                  stale: 'Telemetry stale', unavailable: 'Not reported · update Nano'};
  window.updateRobotTelemetry = status => {
    const nano = status?.nano || {}, fresh = Boolean(status?.live && nano.fresh);
    text('tofDistance', fresh && nano.sensor_valid ? `${nano.distance_cm} cm` :
         fresh && nano.distance_cm != null ? `${nano.distance_cm} cm · unverified` : 'Not reported');
    text('tofState', status ? states[nano.tof_state || 'unavailable'] : 'Status unavailable');
    for (const [key, id] of [['left', 'sonarLeft'], ['right', 'sonarRight']]) {
      const sensor = nano.sonar?.[key];
      const label = !status ? 'Status unavailable' : !sensor ? 'Not reported' :
        sensor.state === 'ok' ? `${sensor.distance_cm} cm` :
        sensor.state === 'no_echo' ? 'No echo / outside 2–200 cm' :
        sensor.state === 'stale' ? 'Reading stale' : 'Not reported';
      text(id, label);
    }
    text('tofSignal', fresh ? String(nano.signal) : '—');
    text('nanoApplied', fresh ? nano.applied_outputs.map(value => Math.round(value * 100) + '%').join(' / ') : '—');
    text('nanoWatchdog', fresh ? nano.watchdog ? 'Timed out · motors stopped' : 'Receiving commands' : '—');
    text('nanoAge', nano.age_s == null ? '—' : `${nano.age_s.toFixed(1)} s${fresh ? '' : ' · stale'}`);
    text('nanoUptime', fresh ? duration(nano.uptime_ms / 1000) : '—');
    text('piTemperature', status?.pi?.temperature_c == null ? 'Not reported' : `${status.pi.temperature_c.toFixed(1)} °C`);
    text('piUptime', duration(status?.pi?.uptime_s));
  };
})();
