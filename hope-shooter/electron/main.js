'use strict';

const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('node:path');

// The game is a self-contained page with no outbound requests, so the window
// needs no privileges at all: the renderer runs sandboxed with node disabled.
const GAME = path.join(__dirname, '..', 'dist', 'index.html');

// A frame-locked WebGL game should not be throttled or vsync-capped down when
// the window loses focus mid-round.
app.commandLine.appendSwitch('disable-renderer-backgrounding');

let win = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: '#06060a',
    title: '호프: 마지막 거리',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
    },
  });

  // Nothing in the game navigates or opens windows; anything that tries is a
  // bug or worse, so send it to the system browser instead of the game window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event) => event.preventDefault());

  win.once('ready-to-show', () => win.show());
  win.loadFile(GAME);
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
