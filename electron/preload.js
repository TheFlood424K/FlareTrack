// preload.js - Secure contextBridge between main and renderer
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // --- Password / Auth ---
  // Returns { has_password: bool }
  hasPassword: () => ipcRenderer.invoke('has-password'),
  // Returns { ok: bool }
  verifyPassword: (pw) => ipcRenderer.invoke('verify-password', pw),
  // Returns { ok: true }
  setPassword: (pw) => ipcRenderer.invoke('set-password', pw),

  // --- Patient ---
  // Returns patient object or null
  getPatient: () => ipcRenderer.invoke('get-patient'),
  // data: { name, conditions, notes, date_of_birth, ... }
  savePatient: (data) => ipcRenderer.invoke('save-patient', data),

  // --- Daily Logs ---
  // Returns log dict for the given YYYY-MM-DD date
  getLog: (dateStr) => ipcRenderer.invoke('get-log', dateStr),
  // log: full log dict; dateStr: YYYY-MM-DD
  saveLog: (dateStr, log) => ipcRenderer.invoke('save-log', { dateStr, log }),
  // Returns array of date strings, newest first
  listLogDates: () => ipcRenderer.invoke('list-log-dates'),
  // Returns array of all log dicts, newest first
  getAllLogs: () => ipcRenderer.invoke('get-all-logs'),

  // --- Utility ---
  openDataFolder: () => ipcRenderer.invoke('open-data-folder'),
});
