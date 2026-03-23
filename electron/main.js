// main.js - Electron main process for FlareTrack
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

const DATA_DIR = path.join(app.getPath('userData'), 'flaretrack-data');
const LOGS_DIR = path.join(DATA_DIR, 'logs');
const PATIENT_FILE = path.join(DATA_DIR, 'patient.json');

function ensureDirs() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#0f0f1a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets', 'icon.png')
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  ensureDirs();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ---- IPC Handlers ----

// Patient
ipcMain.handle('get-patient', () => {
  if (!fs.existsSync(PATIENT_FILE)) return null;
  return JSON.parse(fs.readFileSync(PATIENT_FILE, 'utf-8'));
});

ipcMain.handle('save-patient', (_, data) => {
  fs.writeFileSync(PATIENT_FILE, JSON.stringify(data, null, 2));
  return true;
});

// Daily logs
function logPath(dateStr) {
  return path.join(LOGS_DIR, dateStr + '.json');
}

ipcMain.handle('get-log', (_, dateStr) => {
  const p = logPath(dateStr);
  if (!fs.existsSync(p)) return { date: dateStr, symptoms: [], medications: [], environment: null, overall_wellbeing: null, daily_notes: '' };
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
});

ipcMain.handle('save-log', (_, dateStr, data) => {
  fs.writeFileSync(logPath(dateStr), JSON.stringify(data, null, 2));
  return true;
});

ipcMain.handle('list-log-dates', () => {
  if (!fs.existsSync(LOGS_DIR)) return [];
  return fs.readdirSync(LOGS_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => f.replace('.json', ''))
    .sort((a, b) => b.localeCompare(a));
});

ipcMain.handle('get-all-logs', () => {
  if (!fs.existsSync(LOGS_DIR)) return [];
  return fs.readdirSync(LOGS_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => JSON.parse(fs.readFileSync(path.join(LOGS_DIR, f), 'utf-8')))
    .sort((a, b) => b.date.localeCompare(a.date));
});

ipcMain.handle('open-data-folder', () => {
  shell.openPath(DATA_DIR);
});
