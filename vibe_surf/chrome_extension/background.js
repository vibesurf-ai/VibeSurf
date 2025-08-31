// Background Script - VibeSurf Extension
// Handles extension lifecycle, side panel management, and cross-context communication

// Import configuration using importScripts for service worker
try {
  importScripts('config.js');
  console.log('[VibeSurf] Configuration loaded');
} catch (error) {
  console.error('[VibeSurf] Failed to load configuration:', error);
}

class VibeSurfBackground {
  constructor() {
    this.isInitialized = false;
    this.setupEventListeners();
    this.initDevMode();
  }

  initDevMode() {
    // Enable auto-reload in development mode
    try {
      const manifest = chrome.runtime.getManifest();
      const isDevelopment = !('update_url' in manifest);
      
      if (isDevelopment) {
        // Simple reload check every 3 seconds
        setInterval(() => {
          fetch(chrome.runtime.getURL('manifest.json'))
            .then(() => {
              // File accessible, extension is working
            })
            .catch(() => {
              // If we can't access our own files, extension might need reload
            });
        }, 3000);
      }
    } catch (error) {
      // Ignore errors in dev mode setup
    }
  }

  setupEventListeners() {
    // Extension installation and startup
    chrome.runtime.onInstalled.addListener(this.handleInstalled.bind(this));
    chrome.runtime.onStartup.addListener(this.handleStartup.bind(this));

    // Action button click (toolbar icon)
    chrome.action.onClicked.addListener(this.handleActionClick.bind(this));

    // Context menu setup (backup method)
    chrome.runtime.onInstalled.addListener(() => {
      chrome.contextMenus.create({
        id: 'open-vibesurf',
        title: 'Open VibeSurf Panel',
        contexts: ['action']
      });
    });
    
    chrome.contextMenus.onClicked.addListener((info, tab) => {
      if (info.menuItemId === 'open-vibesurf') {
        this.handleActionClick(tab);
      }
    });

    // Message handling between contexts
    chrome.runtime.onMessage.addListener(this.handleMessage.bind(this));

    // Tab updates for context awareness
    chrome.tabs.onActivated.addListener(this.handleTabActivated.bind(this));
    chrome.tabs.onUpdated.addListener(this.handleTabUpdated.bind(this));

  }

  async handleInstalled(details) {
    
    try {
      // Check Chrome version and API availability
      
      // Initialize default settings
      await this.initializeSettings();
      
      // Set default badge
      await chrome.action.setBadgeText({ text: '' });
      await chrome.action.setBadgeBackgroundColor({ color: '#007acc' });
      
      // Show welcome notification on fresh install
      if (details.reason === 'install') {
        await this.showWelcomeNotification();
      }
      
      this.isInitialized = true;
    } catch (error) {
      console.error('[VibeSurf] Initialization failed:', error);
    }
  }

  async handleStartup() {
    await this.initializeSettings();
    this.isInitialized = true;
  }

  async handleActionClick(tab) {
    
    try {
      // Check if sidePanel API is available
      if (chrome.sidePanel && chrome.sidePanel.open) {
        // Open side panel for the current tab
        await chrome.sidePanel.open({ tabId: tab.id });
        
        // Update badge to indicate active state
        await chrome.action.setBadgeText({ text: '●', tabId: tab.id });
        await chrome.action.setBadgeBackgroundColor({ color: '#007acc', tabId: tab.id });
        
      } else {
        
        // Use test panel first
        await chrome.tabs.create({
          url: chrome.runtime.getURL('test-panel.html'),
          index: tab.index + 1
        });
        
      }
      
      // Store current tab info for context
      await chrome.storage.local.set({
        currentTab: {
          id: tab.id,
          url: tab.url,
          title: tab.title,
          timestamp: Date.now()
        }
      });
      
    } catch (error) {
      console.error('[VibeSurf] Failed to open side panel:', error);
      
      // Show notification with helpful message
      await chrome.notifications.create({
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icons/icon48.png') || '',
        title: 'VibeSurf',
        message: 'Side panel failed. Please update Chrome to the latest version or try right-clicking the extension icon.'
      });
      
      // Fallback: try to open in new tab
      try {
        await chrome.tabs.create({
          url: chrome.runtime.getURL('sidepanel.html'),
          index: tab.index + 1
        });
      } catch (fallbackError) {
        console.error('[VibeSurf] Fallback also failed:', fallbackError);
      }
    }
  }

  handleMessage(message, sender, sendResponse) {
    
    // Handle async messages properly
    (async () => {
      try {
        let result;
        
        switch (message.type) {
          case 'GET_CURRENT_TAB':
            result = await this.getCurrentTabInfo();
            break;
            
          case 'UPDATE_BADGE':
            result = await this.updateBadge(message.data);
            break;
            
          case 'SHOW_NOTIFICATION':
            result = await this.showNotification(message.data);
            break;
            
          case 'HEALTH_CHECK':
            result = { status: 'healthy', timestamp: Date.now() };
            break;
            
          case 'GET_BACKEND_STATUS':
            result = await this.checkBackendStatus(message.data?.backendUrl);
            break;
            
          case 'STORE_SESSION_DATA':
            result = await this.storeSessionData(message.data);
            break;
            
          case 'GET_SESSION_DATA':
            result = await this.getSessionData(message.data?.sessionId);
            break;
            
          case 'OPEN_FILE_URL':
            result = await this.openFileUrl(message.data?.fileUrl);
            break;
            
          case 'OPEN_FILE_SYSTEM':
            result = await this.openFileSystem(message.data?.filePath);
            break;
            
          default:
            console.warn('[VibeSurf] Unknown message type:', message.type);
            result = { error: 'Unknown message type' };
        }
        
        sendResponse(result);
        
      } catch (error) {
        console.error('[VibeSurf] Message handling error:', error);
        sendResponse({ error: error.message });
      }
    })();
    
    // Return true to indicate async response
    return true;
  }

  async handleTabActivated(activeInfo) {
    // Update current tab context when user switches tabs
    const tab = await chrome.tabs.get(activeInfo.tabId);
    
    await chrome.storage.local.set({
      currentTab: {
        id: tab.id,
        url: tab.url,
        title: tab.title,
        timestamp: Date.now()
      }
    });
  }

  async handleTabUpdated(tabId, changeInfo, tab) {
    // Update context when tab URL changes
    if (changeInfo.url) {
      const { currentTab } = await chrome.storage.local.get('currentTab');
      
      if (currentTab && currentTab.id === tabId) {
        await chrome.storage.local.set({
          currentTab: {
            ...currentTab,
            url: tab.url,
            title: tab.title,
            timestamp: Date.now()
          }
        });
      }
    }
  }

  async initializeSettings() {
    // Load configuration (use self instead of window in service worker)
    const config = self.VIBESURF_CONFIG || {};
    
    const defaultSettings = {
      backendUrl: config.BACKEND_URL || 'http://localhost:9335',
      defaultSessionPrefix: config.DEFAULT_SESSION_PREFIX || 'vibesurf_',
      notifications: config.NOTIFICATIONS || {
        enabled: true,
        taskComplete: true,
        taskError: true
      },
      ui: config.UI || {
        theme: 'auto',
        autoScroll: true,
        compactMode: false
      },
      debug: config.DEBUG || false
    };

    const { settings } = await chrome.storage.local.get('settings');
    
    if (!settings) {
      await chrome.storage.local.set({ settings: defaultSettings });
    } else {
      // Merge with defaults for any missing keys
      const mergedSettings = { ...defaultSettings, ...settings };
      await chrome.storage.local.set({ settings: mergedSettings });
    }
  }

  async getCurrentTabInfo() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      return {
        id: tab.id,
        url: tab.url,
        title: tab.title,
        favIconUrl: tab.favIconUrl
      };
    } catch (error) {
      console.error('[VibeSurf] Failed to get current tab:', error);
      return null;
    }
  }

  async updateBadge(data) {
    const { text, color, tabId } = data;
    
    if (text !== undefined) {
      await chrome.action.setBadgeText({ text, tabId });
    }
    
    if (color) {
      await chrome.action.setBadgeBackgroundColor({ color, tabId });
    }
    
    return { success: true };
  }

  async showNotification(data) {
    const { title, message, type = 'info', iconUrl = 'icons/icon48.png' } = data;
    
    // Map custom types to valid Chrome notification types
    const validType = ['basic', 'image', 'list', 'progress'].includes(type) ? type : 'basic';
    
    const notificationId = await chrome.notifications.create({
      type: validType,
      iconUrl,
      title: title || 'VibeSurf',
      message
    });
    
    return { notificationId };
  }

  async showWelcomeNotification() {
    await chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'Welcome to VibeSurf!',
      message: 'Click the VibeSurf icon in the toolbar to start automating your browsing tasks.'
    });
  }

  async checkBackendStatus(backendUrl = null) {
    // Use configuration file value as default (use self instead of window in service worker)
    const config = self.VIBESURF_CONFIG || {};
    backendUrl = backendUrl || config.BACKEND_URL || 'http://localhost:9335';
    try {
      const response = await fetch(`${backendUrl}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      
      if (response.ok) {
        const data = await response.json();
        return {
          status: 'connected',
          backend: data,
          timestamp: Date.now()
        };
      } else {
        return {
          status: 'error',
          error: `HTTP ${response.status}`,
          timestamp: Date.now()
        };
      }
    } catch (error) {
      console.error('[VibeSurf] Backend health check failed:', error);
      return {
        status: 'disconnected',
        error: error.message,
        timestamp: Date.now()
      };
    }
  }

  async storeSessionData(data) {
    const { sessionId, ...sessionData } = data;
    const key = `session_${sessionId}`;
    
    // Store session data
    await chrome.storage.local.set({
      [key]: {
        ...sessionData,
        lastUpdated: Date.now()
      }
    });
    
    // Update sessions list
    const { sessionsList = [] } = await chrome.storage.local.get('sessionsList');
    
    if (!sessionsList.includes(sessionId)) {
      sessionsList.unshift(sessionId); // Add to beginning
      
      // Keep only last 50 sessions
      if (sessionsList.length > 50) {
        const removedSessions = sessionsList.splice(50);
        
        // Clean up old session data
        const keysToRemove = removedSessions.map(id => `session_${id}`);
        await chrome.storage.local.remove(keysToRemove);
      }
      
      await chrome.storage.local.set({ sessionsList });
    }
    
    return { success: true };
  }

  async getSessionData(sessionId) {
    try {
      if (!sessionId) {
        // Return all sessions
        const { sessionsList = [] } = await chrome.storage.local.get('sessionsList');
        const sessionKeys = sessionsList.map(id => `session_${id}`);
        
        if (sessionKeys.length === 0) {
          console.log('[VibeSurf] No sessions found in storage');
          return { sessions: [] };
        }
        
        const sessionsData = await chrome.storage.local.get(sessionKeys);
        const sessions = sessionsList
          .map(id => {
            const data = sessionsData[`session_${id}`];
            if (data) {
              return {
                sessionId: id,
                ...data
              };
            }
            return null;
          })
          .filter(session => session !== null); // Remove null entries
        
        return { sessions };
      } else {
        // Return specific session
        const { [`session_${sessionId}`]: sessionData } = await chrome.storage.local.get(`session_${sessionId}`);
        
        if (sessionData) {
          return { sessionData };
        } else {
          return { sessionData: null, error: 'Session not found in storage' };
        }
      }
    } catch (error) {
      console.error('[VibeSurf] Error retrieving session data:', error);
      return { sessionData: null, error: error.message };
    }
  }

  async openFileUrl(fileUrl) {
    if (!fileUrl) {
      return { success: false, error: 'No file URL provided' };
    }

    try {
      
      // Try to create a new tab with the file URL
      const tab = await chrome.tabs.create({
        url: fileUrl,
        active: true
      });
      
      if (tab && tab.id) {
        return { success: true, tabId: tab.id };
      } else {
        return { success: false, error: 'Failed to create tab' };
      }
      
    } catch (error) {
      console.error('[VibeSurf] Error opening file URL:', error);
      return {
        success: false,
        error: error.message || 'Unknown error opening file'
      };
    }
  }

  async openFileSystem(filePath) {
    if (!filePath) {
      return { success: false, error: 'No file path provided' };
    }

    try {
      
      // For macOS, we can try using shell command via executeScript in content script
      // This is a workaround since Chrome extensions can't directly execute system commands
      
      // Try to create a temporary download link approach
      const fileUrl = filePath.startsWith('/') ? `file://${filePath}` : `file:///${filePath}`;
      
      // Method 1: Try to open in new tab first (might work on some systems)
      try {
        const tab = await chrome.tabs.create({
          url: fileUrl,
          active: false
        });
        
        // Check if tab was created successfully
        if (tab && tab.id) {
          
          // Close the tab after a short delay (system should have picked it up)
          setTimeout(async () => {
            try {
              await chrome.tabs.remove(tab.id);
            } catch (e) {
              // Tab might already be closed by system
            }
          }, 1000);
          
          return { success: true, method: 'system_tab', tabId: tab.id };
        }
      } catch (tabError) {
      }
      
      // Method 2: Try using the downloads API to force system open
      try {
        // Create a data URL that triggers download/open
        const response = await fetch(fileUrl);
        if (response.ok) {
          return { success: true, method: 'accessible', filePath };
        }
      } catch (fetchError) {
      }
      
      // If all methods fail
      return {
        success: false,
        error: 'Unable to open file with system default application',
        suggestion: 'Try copying the file path and opening manually'
      };
      
    } catch (error) {
      console.error('[VibeSurf] Error in openFileSystem:', error);
      return {
        success: false,
        error: error.message || 'Unknown error opening file'
      };
    }
  }

  // Cleanup method for extension unload
  async cleanup() {
    
    // Clear any active badges
    await chrome.action.setBadgeText({ text: '' });
    
    // Could add other cleanup tasks here
  }
}

// Initialize background service
const vibeSurfBackground = new VibeSurfBackground();

// Handle extension unload
chrome.runtime.onSuspend.addListener(() => {
  vibeSurfBackground.cleanup();
});

// Export for potential use in tests or other contexts
self.VibeSurfBackground = VibeSurfBackground;