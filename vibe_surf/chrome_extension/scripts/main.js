// Main Entry Point - VibeSurf Chrome Extension
// Initializes and coordinates all components of the extension

console.log('[VibeSurf] Main script starting...');

class VibeSurfApp {
  constructor() {
    this.apiClient = null;
    this.sessionManager = null;
    this.uiManager = null;
    this.settings = {};
    this.isInitialized = false;
    
    console.log('[VibeSurf] Application starting...');
  }

  async initialize() {
    try {
      console.log('[VibeSurf] Initializing application...');

      // First, get fresh config from background script (which reads from disk)
      const freshConfig = await this.getFreshConfig();

      // Load settings from storage (with fresh config as default)
      await this.loadSettings(freshConfig);

      // Initialize API client
      this.initializeAPIClient();

      // Initialize locale from location if not already set
      await this.initializeLocale();

      // Non-blocking backend check - don't prevent UI from loading
      const backendReady = await this.checkBackendConnection();
      if (!backendReady) {
        console.warn('[VibeSurf] Backend not ready yet, will retry in background');
        // Start background retry mechanism
        this.retryBackendConnection();
      }

      // Initialize session manager (continue even if backend not ready)
      this.initializeSessionManager();

      // Initialize UI manager
      await this.initializeUIManager();

      // Translate the page with the loaded locale (after UI is ready)
      window.i18n.translatePage();

      // Setup global error handling
      this.setupErrorHandling();

      // Setup periodic health checks
      this.setupHealthChecks();

      this.isInitialized = true;

      console.log('[VibeSurf] Application initialized successfully');

      // Show success notification
      chrome.runtime.sendMessage({
        type: 'SHOW_NOTIFICATION',
        data: {
          title: 'VibeSurf Ready',
          message: 'Extension is ready to automate your browsing tasks!'
        }
      });

    } catch (error) {
      console.error('[VibeSurf] Initialization failed:', error);
      this.handleInitializationError(error);
    }
  }

  async getFreshConfig() {
    try {
      console.log('[VibeSurf] Getting fresh config from background...');
      const response = await chrome.runtime.sendMessage({ type: 'GET_CONFIG' });
      if (response && response.BACKEND_URL) {
        console.log('[VibeSurf] Fresh config received:', response.BACKEND_URL);
        return response;
      }
    } catch (error) {
      console.warn('[VibeSurf] Failed to get fresh config:', error);
    }
    // Fallback to window.VIBESURF_CONFIG (loaded from cached config.js)
    return window.VIBESURF_CONFIG || {};
  }

  async loadSettings(freshConfig = {}) {
    try {
      const result = await chrome.storage.local.get('settings');
      this.settings = result.settings || {};

      // Apply default settings if not present
      // Priority: freshConfig (from background) > window.VIBESURF_CONFIG (cached)
      const configBackendUrl = freshConfig.BACKEND_URL ||
                               (typeof window !== 'undefined' && window.VIBESURF_CONFIG?.BACKEND_URL);
      const defaultSettings = {
        backendUrl: configBackendUrl,
        defaultSessionPrefix: 'vibesurf_',
        pollingFrequency: 1000,
        notifications: {
          enabled: true,
          taskComplete: true,
          taskError: true
        },
        ui: {
          theme: 'auto',
          autoScroll: true,
          compactMode: false
        },
        debug: false
      };
      
      this.settings = { ...defaultSettings, ...this.settings };
      
      // Save merged settings back
      await chrome.storage.local.set({ settings: this.settings });
      
      console.log('[VibeSurf] Settings loaded:', this.settings);
    } catch (error) {
      console.error('[VibeSurf] Failed to load settings:', error);
      this.settings = {};
    }
  }

  initializeAPIClient() {
    const backendUrl = this.settings.backendUrl || 'http://localhost:8000';
    this.apiClient = new VibeSurfAPIClient(backendUrl);

    console.log('[VibeSurf] API client initialized with URL:', backendUrl);
  }

  async initializeLocale() {
    try {
      console.log('[VibeSurf] Initializing locale from location...');

      // Use the i18n helper to initialize locale from location
      // This will only detect and set locale if user hasn't already selected one
      const locale = await window.i18n.initializeLocaleFromLocation(
        () => this.apiClient
      );

      console.log('[VibeSurf] Locale initialized:', locale);
      // Note: translatePage() will be called after UI is initialized
    } catch (error) {
      console.warn('[VibeSurf] Failed to initialize locale from location, using default:', error);
      // Continue with default locale on error
    }
  }

  async checkBackendConnection() {
    try {
      console.log('[VibeSurf] Checking backend connection...');
      
      const healthCheck = await this.apiClient.healthCheck();
      
      if (healthCheck.status === 'healthy') {
        console.log('[VibeSurf] Backend connection successful');
        return true;
      } else {
        console.warn('[VibeSurf] Backend health check returned unhealthy status');
        return false;
      }
      
    } catch (error) {
      console.warn('[VibeSurf] Backend connection failed:', error.message);
      // Don't throw error - allow UI to load anyway
      return false;
    }
  }

  retryBackendConnection() {
    let retryCount = 0;
    const maxRetries = 10;
    const retryInterval = 3000; // 3 seconds
    
    console.log('[VibeSurf] Starting background backend connection retry...');
    
    const retryTimer = setInterval(async () => {
      retryCount++;
      console.log(`[VibeSurf] Backend retry attempt ${retryCount}/${maxRetries}`);
      
      const isReady = await this.checkBackendConnection();
      
      if (isReady) {
        clearInterval(retryTimer);
        console.log('[VibeSurf] Backend connected successfully after retry');
        
        // Show success notification
        chrome.runtime.sendMessage({
          type: 'SHOW_NOTIFICATION',
          data: {
            title: 'VibeSurf Backend Connected',
            message: 'Successfully connected to VibeSurf backend server'
          }
        });
      } else if (retryCount >= maxRetries) {
        clearInterval(retryTimer);
        console.warn('[VibeSurf] Backend connection timeout after max retries');
        
        // Show warning notification (not error)
        chrome.runtime.sendMessage({
          type: 'SHOW_NOTIFICATION',
          data: {
            title: 'VibeSurf Backend Unavailable',
            message: 'Cannot connect to backend. Please ensure the VibeSurf server is running.'
          }
        });
      }
    }, retryInterval);
  }

  initializeSessionManager() {
    this.sessionManager = new VibeSurfSessionManager(this.apiClient);
    
    // Configure polling frequency from settings
    if (this.settings.pollingFrequency) {
      this.sessionManager.pollingFrequency = this.settings.pollingFrequency;
    }
    
    console.log('[VibeSurf] Session manager initialized');
  }

  async initializeUIManager() {
    this.uiManager = new VibeSurfUIManager(this.sessionManager, this.apiClient);

    // Initialize UI with loaded data
    await this.uiManager.initialize();
    
    console.log('[VibeSurf] UI manager initialized successfully');
  }

  setupErrorHandling() {
    // Global error handler for unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      console.error('[VibeSurf] Unhandled promise rejection:', event.reason);
      
      if (this.settings.notifications?.enabled) {
        chrome.runtime.sendMessage({
          type: 'SHOW_NOTIFICATION',
          data: {
            title: 'VibeSurf Error',
            message: 'An unexpected error occurred. Check the console for details.'
          }
        });
      }
    });

    // Global error handler for script errors
    window.addEventListener('error', (event) => {
      console.error('[VibeSurf] Script error:', event.error);
    });

    console.log('[VibeSurf] Error handling setup complete');
  }

  setupHealthChecks() {
    // Periodic backend health check
    setInterval(async () => {
      try {
        // Check if apiClient exists and is initialized
        if (!this.apiClient || typeof this.apiClient.healthCheck !== 'function') {
          console.warn('[VibeSurf] Health check skipped - API client not available');
          return;
        }
        
        const healthCheck = await this.apiClient.healthCheck();
        
        if (healthCheck.status === 'healthy') {
          // Backend is healthy
        } else {
          // Health check failed
        }
        
      } catch (error) {
        // Silently handle health check failures
        console.warn('[VibeSurf] Health check failed:', error.message);
      }
    }, 30000); // Check every 30 seconds

    console.log('[VibeSurf] Health checks setup complete');
  }

  handleInitializationError(error) {
    console.error('[VibeSurf] Initialization error:', error);
    
    // Show error in UI
    const errorElement = document.createElement('div');
    errorElement.className = 'initialization-error';
    errorElement.innerHTML = `
      <div style="padding: 20px; text-align: center; color: #dc3545;">
        <h3>VibeSurf Initialization Failed</h3>
        <p>${error.message}</p>
        <button id="retry-initialization-btn" style="
          padding: 8px 16px;
          border: 1px solid #dc3545;
          background: #dc3545;
          color: white;
          border-radius: 4px;
          cursor: pointer;
          margin-top: 10px;
        ">Retry</button>
      </div>
    `;
    
    document.body.innerHTML = '';
    document.body.appendChild(errorElement);
    
    // Add proper retry event listener
    const retryBtn = document.getElementById('retry-initialization-btn');
    retryBtn.addEventListener('click', () => {
      console.log('[VibeSurf] Retrying initialization...');
      this.retryInitialization();
    });
    
    // Show error notification
    chrome.runtime.sendMessage({
      type: 'SHOW_NOTIFICATION',
      data: {
        title: 'VibeSurf Error',
        message: `Initialization failed: ${error.message}`
      }
    });
  }

  async retryInitialization() {
    console.log('[VibeSurf] Retrying initialization...');
    
    try {
      // Clear any existing error UI
      const errorElement = document.querySelector('.initialization-error');
      if (errorElement) {
        errorElement.remove();
      }
      
      // Restore the original HTML structure
      document.body.innerHTML = `
        <div id="app" class="vibesurf-container">
          <!-- Header -->
          <header class="header">
            <div class="header-left">
              <div class="logo">
                <div class="logo-content">
                  <span class="logo-text">VibeSurf Activity Logs</span>
                  <div class="session-info">
                    <span class="session-label">Session:</span>
                    <span id="session-id">-</span>
                    <button id="copy-session-btn" class="copy-btn" title="Copy Session ID">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z" fill="currentColor"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div class="header-right">
              <button id="new-session-btn" class="icon-btn" title="New Session">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 4V20M4 12H20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
              <button id="history-btn" class="icon-btn" title="Chat History">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 3V11A4 4 0 0 0 7 15H17L21 19V3H3Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
              <button id="settings-btn" class="icon-btn" title="Settings">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" stroke-width="2"/>
                </svg>
              </button>
            </div>
          </header>
          
          <!-- Main Content -->
          <main class="main-content">
            <div class="activity-section">
              <div id="activity-log" class="activity-log">
                <div class="loading-message" style="text-align: center; padding: 20px; color: #666;">
                  <div>Connecting to VibeSurf...</div>
                </div>
              </div>
            </div>
            <div id="control-panel" class="control-panel hidden"></div>
          </main>
          
          <!-- Input Section -->
          <footer class="input-section">
            <div class="input-container">
              <div class="input-main">
                <div class="textarea-container">
                  <textarea id="task-input" class="task-input" data-i18n-placeholder="inputPlaceholder" placeholder="Ask anything (/ for skills, @ to specify tab)" rows="3"></textarea>
                  <div class="input-actions">
                    <button id="attach-file-btn" class="action-btn attach-btn" title="Attach Files">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M21.44 11.05L12.25 20.24C11.1242 21.3658 9.59722 21.9983 8.005 21.9983C6.41278 21.9983 4.88583 21.3658 3.76 20.24C2.63417 19.1142 2.00166 17.5872 2.00166 15.995C2.00166 14.4028 2.63417 12.8758 3.76 11.75L12.33 3.18C13.0806 2.42944 14.0986 2.00696 15.16 2.00696C16.2214 2.00696 17.2394 2.42944 17.99 3.18C18.7406 3.93056 19.163 4.94859 19.163 6.01C19.163 7.07141 18.7406 8.08944 17.99 8.84L10.07 16.76C9.69469 17.1353 9.1897 17.3442 8.665 17.3442C8.1403 17.3442 7.63531 17.1353 7.26 16.76C6.88469 16.3847 6.67581 15.8797 6.67581 15.355C6.67581 14.8303 6.88469 14.3253 7.26 13.95L15.19 6.02" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </button>
                    <button id="send-btn" class="action-btn send-btn" title="Send Task">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              <div class="input-footer">
                <select id="llm-profile-select" class="llm-select compact"></select>
              </div>
            </div>
            <input type="file" id="file-input" class="hidden" multiple accept="*/*">
          </footer>
        </div>
      `;
      
      // Reset state
      this.isInitialized = false;
      this.apiClient = null;
      this.sessionManager = null;
      this.uiManager = null;
      
      // Retry initialization
      await this.initialize();
      
    } catch (error) {
      console.error('[VibeSurf] Retry initialization failed:', error);
      this.handleInitializationError(error);
    }
  }

  // Settings management
  async updateSettings(newSettings) {
    this.settings = { ...this.settings, ...newSettings };
    
    try {
      await chrome.storage.local.set({ settings: this.settings });
      
      // Apply settings to components
      if (newSettings.backendUrl && this.apiClient) {
        this.apiClient.setBaseURL(newSettings.backendUrl);
        
        // Re-check backend connection
        await this.checkBackendConnection();
      }
      
      if (newSettings.pollingFrequency && this.sessionManager) {
        this.sessionManager.pollingFrequency = newSettings.pollingFrequency;
      }
      
      console.log('[VibeSurf] Settings updated:', newSettings);
      
    } catch (error) {
      console.error('[VibeSurf] Failed to update settings:', error);
      throw error;
    }
  }

  // Current tab context
  async getCurrentTabContext() {
    try {
      const tabInfo = await chrome.runtime.sendMessage({ type: 'GET_CURRENT_TAB' });
      return tabInfo;
    } catch (error) {
      console.error('[VibeSurf] Failed to get current tab context:', error);
      return null;
    }
  }

  // Cleanup method
  destroy() {
    // Prevent multiple cleanup calls
    if (this.isDestroying || !this.isInitialized) {
      console.log('[VibeSurf] Cleanup already in progress or app not initialized, skipping...');
      return;
    }
    
    this.isDestroying = true;
    console.log('[VibeSurf] Cleaning up application...');
    
    try {
      if (this.uiManager) {
        this.uiManager.destroy();
        this.uiManager = null;
      }
      
      if (this.sessionManager) {
        this.sessionManager.destroy();
        this.sessionManager = null;
      }
      
      if (this.apiClient) {
        this.apiClient = null;
      }
      
      this.isInitialized = false;
      console.log('[VibeSurf] Application cleanup complete');
    } catch (error) {
      console.error('[VibeSurf] Error during cleanup:', error);
    } finally {
      this.isDestroying = false;
    }
  }

  // Get application status
  getStatus() {
    return {
      initialized: this.isInitialized,
      hasActiveSession: this.sessionManager?.isSessionActive() || false,
      hasActiveTask: this.sessionManager?.hasActiveTask() || false,
      currentSessionId: this.sessionManager?.getCurrentSessionId() || null,
      backendUrl: this.settings.backendUrl || 'Not configured',
      taskStatus: this.sessionManager?.getTaskStatus() || null
    };
  }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
  console.log('[VibeSurf] DOM loaded, initializing application...');

  // Check if i18n is available
  if (typeof window.i18n === 'undefined') {
    console.error('[VibeSurf] ERROR: window.i18n is not defined! i18n-helper.js may not have loaded properly.');
  } else {
    console.log('[VibeSurf] window.i18n is available:', typeof window.i18n);
  }

  // Create global app instance
  window.vibeSurfApp = new VibeSurfApp();

  try {
    await window.vibeSurfApp.initialize();
  } catch (error) {
    console.error('[VibeSurf] Failed to initialize app:', error);
  }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
  if (window.vibeSurfApp && window.vibeSurfApp.isInitialized && !window.vibeSurfApp.isDestroying) {
    console.log('[VibeSurf] Page unloading, cleaning up...');
    window.vibeSurfApp.destroy();
  }
});

// Handle visibility change to prevent unnecessary cleanup
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    console.log('[VibeSurf] Page hidden, but not cleaning up (might be tab switch)');
  } else if (document.visibilityState === 'visible') {
    console.log('[VibeSurf] Page visible again');
  }
});

// Make app accessible for debugging
if (typeof window !== 'undefined') {
  window.VibeSurfApp = VibeSurfApp;
}

// Handle messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[VibeSurf] Received message from background:', message.type);
  
  if (window.vibeSurfApp) {
    switch (message.type) {
      case 'GET_APP_STATUS':
        sendResponse(window.vibeSurfApp.getStatus());
        break;
        
      case 'UPDATE_SETTINGS':
        window.vibeSurfApp.updateSettings(message.data)
          .then(() => sendResponse({ success: true }))
          .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // Keep message channel open for async response
        
      case 'MICROPHONE_PERMISSION_RESULT':
        console.log('[VibeSurf] Received microphone permission result:', message);
        // This message is typically handled by voice recorder, just acknowledge
        sendResponse({ acknowledged: true });
        break;

      // Ignore known messages that are handled elsewhere but might broadcast
      case 'CUSTOM_CLICK_EVENT':
      case 'CUSTOM_INPUT_EVENT':
      case 'CUSTOM_KEY_EVENT':
      case 'PAGE_CONTEXT_UPDATE':
        // These are handled by background/recorder, just ignore in main.js
        break;
        
      default:
        console.warn('[VibeSurf] Unknown message type:', message.type);
    }
  }
});

console.log('[VibeSurf] Main script loaded');