// main.js — entry point, imports all modules
import './utils.js';
import './api.js';
import './navigation.js';
import './projects.js';
import './models.js';
import './categories.js';
import './tzView.js';
import './dataView.js';
import './aiCheck.js';
import './changesView.js';
import './themes.js';
// Note: viewer.js is NOT imported here — it's imported by models.js where needed
// The import of each module triggers its code execution including window.* assignments

// Init
window.showHome();  // Start the app
