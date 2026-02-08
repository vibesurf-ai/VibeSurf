// ES6 Module wrapper for config.js
// This file provides ES6 module interface for background.js
// It dynamically loads config.js in service worker context to get the actual config

// Default config values (fallback if config.js fails to load)
const DEFAULT_CONFIG = {
  BACKEND_URL: 'http://127.0.0.1:9337',
  API_PREFIX: '/api',
  DEFAULT_TIMEOUT: 30000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000,
  DEFAULT_SESSION_PREFIX: '',
  NOTIFICATIONS: {
    enabled: true,
    taskComplete: true,
    taskError: true
  },
  UI: {
    theme: 'auto',
    autoScroll: true,
    compactMode: false
  },
  SOCIAL_LINKS: {
    github: "https://github.com/vibesurf-ai/VibeSurf",
    discord: "https://discord.gg/86SPfhRVbk",
    x: "https://x.com/warmshao",
    wechat: "icons/wx.png",
    website: "https://vibe-surf.com/"
  },
  DEBUG: false
};

// In service worker context, try to load config.js dynamically
// This ensures we get the latest config values updated by CLI
let VIBESURF_CONFIG = DEFAULT_CONFIG;

// Check if config was already loaded (e.g., by another script)
if (typeof self !== 'undefined' && self.VIBESURF_CONFIG) {
  VIBESURF_CONFIG = self.VIBESURF_CONFIG;
}

// Export the config
export { VIBESURF_CONFIG };

// Also export a function to reload config from storage if needed
export function getConfig() {
  // Always check global scope first (in case config.js was loaded)
  if (typeof self !== 'undefined' && self.VIBESURF_CONFIG) {
    return self.VIBESURF_CONFIG;
  }
  return VIBESURF_CONFIG;
}
