// main.js - Electron main process for FlareTrack
// Shells out to electron/bridge.py for all data operations so that
// encryption stays entirely inside Python (same key/logic as the CLI).

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;

// Repo root is one level up from the electron/ directory
const REPO_ROOT = path.join(__dirname, '..');
const BRIDGE = path.join(__dirname, 'bridge.py');
const DATA_DIR = path.join(REPO_ROOT, 'data');

// ---------------------------------------------------------------------------
// Python bridge helper
// Spawns `python bridge.py <command> [...args]` and pipes data via stdin.
// Returns a Promise that resolves with the parsed JSON response.
// ---------------------------------------------------------------------------
function runBridge(args, inputData) {
  return new Promise((resolve, reject) => {
    // Try 'python3' first; fall back to 'python' on Windows
    const pyBin = process.platform === 'win32' ? 'python' : 'python3';
    const proc = spawn(pyBin, [BRIDGE, ...args], { cwd: REPO_ROOT });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('error', (err) => {
      // If python3 not found try plain python
      if (err.code === 'ENOENT' && pyBin === 'python3') {
        const fallback = spawn('python', [BRIDGE, ...args], { cwd: REPO_ROOT });
        let out2 = ''; let err2 = '';
        fallback.stdout.on('data', (c) => { out2 += c.toString(); });
        fallback.stderr.on('data', (c) => { err2 += c.toString(); });
        fallback.on('error', reject);
        fallback.on('close', (code) => {
          if (code !== 0) return reject(new Error(`bridge.py: ${err2}`));
          try { resolve(JSON.parse(out2 || 'null')); } catch (e) { reject(e); }
        });
        if (inputData !== undefined) {
          fallback.stdin.write(JSON.stringify(inputData));
        }
        fallback.stdin.end();
      } else {
        reject(err);
      }
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`bridge.py exited ${code}: ${stderr}`));
      }
      try {
        resolve(JSON.parse(stdout || 'null'));
      } catch (e) {
        reject(new Error(`bridge.py bad JSON: ${stdout}`));
      }
    });

    if (inputData !== undefined) {
      proc.stdin.write(JSON.stringify(inputData));
    }
    proc.stdin.end();
  });
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#0a0a14',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  wireIpc();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ---------------------------------------------------------------------------
// IPC Handlers - all delegate to bridge.py
// ---------------------------------------------------------------------------
function wireIpc() {
  // --- Password ---
  ipcMain.handle('has-password', () => runBridge(['has-password']));

  ipcMain.handle('verify-password', (_e, pw) =>
    runBridge(['verify-password', pw])
  );

  ipcMain.handle('set-password', (_e, pw) =>
    runBridge(['set-password', pw])
  );

  // --- Patient ---
  ipcMain.handle('get-patient', () => runBridge(['get-patient']));

  ipcMain.handle('save-patient', (_e, data) =>
    runBridge(['save-patient'], data)
  );

  // --- Logs ---
  ipcMain.handle('get-log', (_e, dateStr) =>
    runBridge(['get-log', dateStr])
  );

  ipcMain.handle('save-log', (_e, { dateStr, log }) =>
    runBridge(['save-log', dateStr], log)
  );

  ipcMain.handle('list-log-dates', () => runBridge(['list-log-dates']));

  ipcMain.handle('get-all-logs', () => runBridge(['get-all-logs']));

  // --- Utility ---
  ipcMain.handle('open-data-folder', () => shell.openPath(DATA_DIR));
}
