// preload.js - Secure bridge between main and renderer
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // Patient
  getPatient: () => ipcRenderer.invoke('get-patient'),
  savePatient: (data) => ipcRenderer.invoke('save-patient', data),

  // Logs
  getLog: (dateStr) => ipcRenderer.invoke('get-log', dateStr),
  saveLog: (dateStr, data) => ipcRenderer.invoke('save-log', dateStr, data),
  listLogDates: () => ipcRenderer.invoke('list-log-dates'),
  getAllLogs: () => ipcRenderer.invoke('get-all-logs'),

  // Utility
  openDataFolder: () => ipcRenderer.invoke('open-data-folder'),
});
