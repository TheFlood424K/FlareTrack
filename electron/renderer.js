// renderer.js - FlareTrack Electron UI Controller
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let currentDateStr = null;
let currentLog = null;
let patient = null;
let allDates = [];

// --- UTILS ---
function isoToday() { return new Date().toISOString().slice(0, 10); }

function setStatus(msg, isError = false) {
  const el = $('#status-label');
  el.textContent = msg;
  el.style.color = isError ? '#ff5566' : '#22cc66';
  setTimeout(() => { if (el.textContent === msg) el.textContent = ''; }, 3000);
}

// --- AUTH / LOCK ---
async function checkAuth() {
  const { has_password } = await window.api.hasPassword();
  if (!has_password) {
    $('#lock-screen').classList.add('hidden');
    $('#no-password-msg').classList.remove('hidden');
    // For a cleaner first run, maybe show the set-password screen
    // but we'll let them click the link in the message.
    await initApp();
    return;
  }
  $('#lock-screen').classList.remove('hidden');
  $('#lock-password').focus();
}

async function handleUnlock() {
  const pw = $('#lock-password').value;
  const { ok } = await window.api.verifyPassword(pw);
  if (ok) {
    $('#lock-screen').classList.add('hidden');
    await initApp();
  } else {
    const err = $('#lock-error');
    err.textContent = 'Invalid password';
    err.classList.remove('hidden');
    $('#lock-password').value = '';
  }
}

// --- INITIALIZATION ---
async function initApp() {
  $('#app').classList.remove('hidden');
  setupTabs();
  setupEvents();
  await loadPatient();
  await loadDate(isoToday());
  await refreshSummary();
}

// --- PATIENT ---
async function loadPatient() {
  patient = await window.api.getPatient();
  renderPatient();
}

function renderPatient() {
  const box = $('#patient-summary');
  if (!patient || !patient.name) {
    box.innerHTML = '<p class="muted">No profile set. Click edit to start.</p>';
    return;
  }
  box.innerHTML = `
    <div style="font-weight:600; font-size:14px; margin-bottom:4px;">${patient.name}</div>
    <div class="muted">${patient.conditions || 'No conditions listed'}</div>
  `;
}

// --- DATA LOADING ---
async function loadDate(dateStr) {
  currentDateStr = dateStr;
  $('#date-picker').value = dateStr;
  $('#current-date-label').textContent = dateStr;

  currentLog = await window.api.getLog(dateStr);
  
  // Ensure structure
  if (!currentLog.symptoms) currentLog.symptoms = [];
  if (!currentLog.medications) currentLog.medications = [];
  if (!currentLog.environment) currentLog.environment = {};

  renderSymptoms();
  renderMeds();
  renderEnvironment();

  allDates = await window.api.listLogDates();
  renderLogList();
}

// --- RENDERERS ---
function renderLogList() {
  const ul = $('#log-list');
  ul.innerHTML = '';
  if (allDates.length === 0) {
    ul.innerHTML = '<li class="muted">No logs yet</li>';
    return;
  }
  allDates.forEach(d => {
    const li = document.createElement('li');
    li.textContent = d;
    if (d === currentDateStr) li.classList.add('active');
    li.onclick = () => loadDate(d);
    ul.appendChild(li);
  });
}

function renderSymptoms() {
  const tbody = $('#symptom-table tbody');
  tbody.innerHTML = '';
  const syms = currentLog.symptoms || [];
  $('#no-symptoms-msg').classList.toggle('hidden', syms.length > 0);

  syms.forEach((s, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="${s.name || ''}" oninput="updateSym(${i}, 'name', this.value)"></td>
      <td><input type="number" min="0" max="10" value="${s.severity ?? ''}" oninput="updateSym(${i}, 'severity', this.value)"></td>
      <td><input type="text" value="${s.location || ''}" oninput="updateSym(${i}, 'location', this.value)"></td>
      <td><input type="text" value="${s.triggers || ''}" oninput="updateSym(${i}, 'triggers', this.value)"></td>
      <td><input type="text" value="${s.duration || ''}" oninput="updateSym(${i}, 'duration', this.value)"></td>
      <td><button onclick="removeSym(${i})">&times;</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMeds() {
  const tbody = $('#med-table tbody');
  tbody.innerHTML = '';
  const meds = currentLog.medications || [];
  $('#no-meds-msg').classList.toggle('hidden', meds.length > 0);

  meds.forEach((m, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" value="${m.name || ''}" oninput="updateMed(${i}, 'name', this.value)"></td>
      <td><input type="text" value="${m.dosage || ''}" oninput="updateMed(${i}, 'dosage', this.value)"></td>
      <td>
        <select onchange="updateMed(${i}, 'status', this.value)">
          <option value="" ${!m.status ? 'selected' : ''}>--</option>
          <option value="taken" ${m.status==='taken' ? 'selected' : ''}>Taken</option>
          <option value="missed" ${m.status==='missed' ? 'selected' : ''}>Missed</option>
          <option value="late" ${m.status==='late' ? 'selected' : ''}>Late</option>
        </select>
      </td>
      <td><input type="time" value="${m.time || ''}" oninput="updateMed(${i}, 'time', this.value)"></td>
      <td><button onclick="removeMed(${i})">&times;</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderEnvironment() {
  const e = currentLog.environment || {};
  $('#env-sleep').value = e.sleep_hours ?? '';
  $('#env-stress').value = e.stress_level ?? '';
  $('#env-exercise').value = e.exercise_minutes ?? '';
  $('#env-diet').value = e.diet_notes || '';
  $('#env-weather').value = e.weather || '';
  $('#env-humidity').value = e.humidity ?? '';
  
  const val = currentLog.overall_wellbeing ?? 5;
  $('#wellbeing-slider').value = val;
  $('#wellbeing-value').textContent = val;
  $('#daily-notes').value = currentLog.daily_notes || '';
}

// --- UPDATERS ---
window.updateSym = (i, field, val) => {
  if (field === 'severity') val = val === '' ? null : parseInt(val);
  currentLog.symptoms[i][field] = val;
};
window.removeSym = (i) => {
  currentLog.symptoms.splice(i, 1);
  renderSymptoms();
};
window.updateMed = (i, field, val) => {
  currentLog.medications[i][field] = val;
};
window.removeMed = (i) => {
  currentLog.medications.splice(i, 1);
  renderMeds();
};

// --- EVENTS ---
function setupEvents() {
  $('#lock-submit-btn').onclick = handleUnlock;
  $('#lock-password').onkeydown = (e) => { if (e.key === 'Enter') handleUnlock(); };

  $('#today-btn').onclick = () => loadDate(isoToday());
  $('#date-picker').onchange = (e) => loadDate(e.target.value);
  
  $('#prev-day-btn').onclick = () => {
    const d = new Date(currentDateStr);
    d.setDate(d.getDate() - 1);
    loadDate(d.toISOString().slice(0, 10));
  };
  $('#next-day-btn').onclick = () => {
    const d = new Date(currentDateStr);
    d.setDate(d.getDate() + 1);
    loadDate(d.toISOString().slice(0, 10));
  };

  $('#add-symptom-btn').onclick = () => {
    currentLog.symptoms.push({ name: '', severity: 5, location: '', triggers: '', duration: '' });
    renderSymptoms();
  };
  $('#add-med-btn').onclick = () => {
    currentLog.medications.push({ name: '', dosage: '', status: '', time: '' });
    renderMeds();
  };

  $('#wellbeing-slider').oninput = (e) => {
    const val = parseInt(e.target.value);
    $('#wellbeing-value').textContent = val;
    currentLog.overall_wellbeing = val;
  };

  $('#save-log-btn').onclick = async () => {
    // Sync environment fields
    currentLog.environment = {
      sleep_hours: parseFloat($('#env-sleep').value) || null,
      stress_level: parseInt($('#env-stress').value) || null,
      exercise_minutes: parseInt($('#env-exercise').value) || null,
      diet_notes: $('#env-diet').value,
      weather: $('#env-weather').value,
      humidity: parseInt($('#env-humidity').value) || null,
    };
    currentLog.daily_notes = $('#daily-notes').value;
    
    await window.api.saveLog(currentDateStr, currentLog);
    setStatus('Day saved successfully');
    allDates = await window.api.listLogDates();
    renderLogList();
  };

  $('#edit-patient-btn').onclick = () => {
    $('#patient-modal').classList.remove('hidden');
    $('#patient-name').value = patient?.name || '';
    $('#patient-dob').value = patient?.date_of_birth || '';
    $('#patient-conditions').value = patient?.conditions || '';
    $('#patient-allergies').value = patient?.allergies || '';
    $('#patient-notes').value = patient?.notes || '';
  };

  $('#patient-cancel-btn').onclick = () => $('#patient-modal').classList.add('hidden');
  
  $('#patient-save-btn').onclick = async () => {
    const data = {
      name: $('#patient-name').value,
      date_of_birth: $('#patient-dob').value,
      conditions: $('#patient-conditions').value,
      allergies: $('#patient-allergies').value,
      notes: $('#patient-notes').value,
    };
    await window.api.savePatient(data);
    patient = data;
    renderPatient();
    $('#patient-modal').classList.add('hidden');
    setStatus('Profile updated');
  };

  $('#open-data-folder-btn').onclick = () => window.api.openDataFolder();
  $('#refresh-summary-btn').onclick = refreshSummary;

  // Set password flow
  $('#set-password-link').onclick = (e) => {
    e.preventDefault();
    $('#lock-screen').classList.add('hidden');
    $('#set-password-screen').classList.remove('hidden');
  };
  $('#skip-password-link').onclick = (e) => { e.preventDefault(); $('#lock-screen').classList.add('hidden'); initApp(); };
  
  $('#set-pw-btn').onclick = async () => {
    const p1 = $('#new-password').value;
    const p2 = $('#confirm-password').value;
    if (!p1) return;
    if (p1 !== p2) {
      $('#set-pw-error').textContent = 'Passwords do not match';
      $('#set-pw-error').classList.remove('hidden');
      return;
    }
    await window.api.setPassword(p1);
    $('#set-password-screen').classList.add('hidden');
    await initApp();
  };
  $('#skip-pw-btn').onclick = () => { $('#set-password-screen').classList.add('hidden'); initApp(); };
}

function setupTabs() {
  $$('.tab').forEach(t => {
    t.onclick = () => {
      $$('.tab').forEach(x => x.classList.remove('active'));
      $$('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      $(`#tab-${t.dataset.tab}`).classList.add('active');
    };
  });
}

// --- SUMMARY ---
async function refreshSummary() {
  const logs = await window.api.getAllLogs();
  const container = $('#summary-content');
  container.innerHTML = '';

  if (logs.length === 0) {
    container.innerHTML = '<p class="muted">Not enough data for summary.</p>';
    return;
  }

  // Calc average wellbeing
  const avgW = (logs.reduce((acc, l) => acc + (l.overall_wellbeing ?? 5), 0) / logs.length).toFixed(1);
  const totalSyms = logs.reduce((acc, l) => acc + (l.symptoms ? l.symptoms.length : 0), 0);
  
  container.innerHTML = `
    <div class="summary-card">
      <h4>Avg Wellbeing</h4>
      <div class="value">${avgW}</div>
    </div>
    <div class="summary-card">
      <h4>Total Symptoms</h4>
      <div class="value">${totalSyms}</div>
    </div>
    <div class="summary-card">
      <h4>Days Tracked</h4>
      <div class="value">${logs.length}</div>
    </div>
  `;
}

// --- START ---
checkAuth();
