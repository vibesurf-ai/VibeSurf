// VibeSurf Extension Configuration
// Change BACKEND_URL here to update all backend connections synchronously

const VIBESURF_CONFIG = {
  // Backend server configuration
  BACKEND_URL: 'http://127.0.0.1:9335',
  
  // API related configuration
  API_PREFIX: '/api',
  DEFAULT_TIMEOUT: 30000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000,
  
  // Session configuration
  DEFAULT_SESSION_PREFIX: '',
  
  // Notification configuration
  NOTIFICATIONS: {
    enabled: true,
    taskComplete: true,
    taskError: true
  },
  
  // UI configuration
  UI: {
    theme: 'auto',
    autoScroll: true,
    compactMode: false
  },
  
  // Debug mode
  DEBUG: false
};

// Export configuration for use in other files
if (typeof window !== 'undefined') {
  window.VIBESURF_CONFIG = VIBESURF_CONFIG;
}

// Service worker environment (background script)
if (typeof self !== 'undefined' && typeof window === 'undefined') {
  self.VIBESURF_CONFIG = VIBESURF_CONFIG;
}

// Node.js environment compatibility (if needed)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VIBESURF_CONFIG;
}