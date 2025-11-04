// Background Script - VibeSurf Extension
// Handles extension lifecycle, side panel management, and cross-context communication

// Load configuration using importScripts for service worker
try {
  importScripts('./config.js');
  console.log('[VibeSurf] Configuration loaded');
} catch (error) {
  console.error('[VibeSurf] Failed to load configuration:', error);
  // Fallback configuration
  self.VIBESURF_CONFIG = {
    BACKEND_URL: 'http://127.0.0.1:9335',
    SOCIAL_LINKS: {
      github: "https://github.com/vibesurf-ai/VibeSurf",
      discord: "https://discord.gg/86SPfhRVbk",
      x: "https://x.com/warmshao",
      reportBug: "https://github.com/vibesurf-ai/VibeSurf/issues/new/choose",
      website: "https://vibe-surf.com/"
    }
  };
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
      try {
        await chrome.notifications.create({
          type: 'basic',
          iconUrl: '', // Use empty string to avoid icon issues
          title: 'VibeSurf',
          message: 'Side panel failed. Please update Chrome to the latest version or try right-clicking the extension icon.'
        });
      } catch (notifError) {
        console.warn('[VibeSurf] Notification failed:', notifError);
        // Don't throw, just log the warning
      }
      
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
    console.log('[VibeSurf] Received message:', message.type);
    
    // Handle async messages properly
    (async () => {
      try {
        let result;
        
        console.log('[VibeSurf] Processing message type:', message.type);
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
            
          case 'COPY_TO_CLIPBOARD':
            result = await this.copyToClipboard(message.text);
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
            
          case 'GET_ALL_TABS':
            result = await this.getAllTabs();
            break;
            
          case 'REQUEST_MICROPHONE_PERMISSION':
            result = await this.requestMicrophonePermission();
            break;
            
          case 'REQUEST_MICROPHONE_PERMISSION_WITH_UI':
            console.log('[VibeSurf] Handling REQUEST_MICROPHONE_PERMISSION_WITH_UI');
            result = await this.requestMicrophonePermissionWithUI();
            break;
            
          case 'MICROPHONE_PERMISSION_RESULT':
            console.log('[VibeSurf] Received MICROPHONE_PERMISSION_RESULT:', message);
            console.log('[VibeSurf] Permission granted:', message.granted);
            console.log('[VibeSurf] Permission error:', message.error);
            
            // Handle permission result from URL parameter approach
            if (message.granted !== undefined) {
              console.log('[VibeSurf] Processing permission result with granted:', message.granted);
              
              // Store the result for the original tab to retrieve
              chrome.storage.local.set({
                microphonePermissionResult: {
                  granted: message.granted,
                  error: message.error,
                  timestamp: Date.now()
                }
              });
              
              // Also send to any waiting listeners
              console.log('[VibeSurf] Broadcasting permission result to all tabs...');
              chrome.runtime.sendMessage({
                type: 'MICROPHONE_PERMISSION_RESULT',
                granted: message.granted,
                error: message.error
              }).then(() => {
                console.log('[VibeSurf] Permission result broadcast successful');
              }).catch((err) => {
                console.log('[VibeSurf] Permission result broadcast failed (no listeners):', err);
              });
            }
            result = { acknowledged: true };
            break;
            
          default:
            console.warn('[VibeSurf] Unknown message type:', message.type, 'Available handlers:', [
              'GET_CURRENT_TAB', 'UPDATE_BADGE', 'SHOW_NOTIFICATION', 'COPY_TO_CLIPBOARD',
              'HEALTH_CHECK', 'GET_BACKEND_STATUS', 'STORE_SESSION_DATA', 'GET_SESSION_DATA',
              'OPEN_FILE_URL', 'OPEN_FILE_SYSTEM', 'GET_ALL_TABS', 'REQUEST_MICROPHONE_PERMISSION',
              'REQUEST_MICROPHONE_PERMISSION_WITH_UI', 'MICROPHONE_PERMISSION_RESULT'
            ]);
            result = { error: 'Unknown message type', receivedType: message.type };
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
    // Load configuration from service worker global
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
    const { title, message, type = 'info', iconUrl } = data;
    
    // Map custom types to valid Chrome notification types
    const validType = ['basic', 'image', 'list', 'progress'].includes(type) ? type : 'basic';
    
    // Simplified icon handling - try available icons without validation
    let finalIconUrl = '';
    
    // Try to use extension icons in order of preference, but don't validate with fetch
    const iconCandidates = [
      iconUrl ? chrome.runtime.getURL(iconUrl) : null,
      chrome.runtime.getURL('icons/logo.png')
    ].filter(Boolean);
    
    // Use the first candidate, or empty string as fallback
    finalIconUrl = iconCandidates[0] || '';
    
    try {
      const notificationId = await chrome.notifications.create({
        type: validType,
        iconUrl: finalIconUrl,
        title: title || 'VibeSurf',
        message
      });
      
      return { notificationId };
    } catch (error) {
      console.warn('[VibeSurf] Notification with icon failed, trying without icon:', error);
      // Try once more with empty icon URL
      try {
        const notificationId = await chrome.notifications.create({
          type: validType,
          iconUrl: '', // Empty string will use browser default
          title: title || 'VibeSurf',
          message
        });
        return { notificationId };
      } catch (fallbackError) {
        console.error('[VibeSurf] Fallback notification also failed:', fallbackError);
        throw new Error(`Failed to create notification: ${error.message}`);
      }
    }
  }

  async showWelcomeNotification() {
    try {
      await chrome.notifications.create({
        type: 'basic',
        iconUrl: '', // Use empty string to avoid icon issues
        title: 'Welcome to VibeSurf!',
        message: 'Click the VibeSurf icon in the toolbar to start automating your browsing tasks.'
      });
    } catch (error) {
      console.warn('[VibeSurf] Welcome notification failed:', error);
      // Don't throw, just log the warning
    }
  }

  async checkBackendStatus(backendUrl = null) {
    // Use configuration file value as default from service worker global
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

    // Add a unique request ID to track duplicate calls
    const requestId = Date.now() + Math.random();
    console.log(`[VibeSurf] openFileUrl called with ID: ${requestId}, URL: ${fileUrl}`);

    try {
      // Validate URL format before attempting to open
      try {
        new URL(fileUrl);
      } catch (urlError) {
        console.warn('[VibeSurf] Invalid URL format:', fileUrl, urlError);
        return { success: false, error: 'Invalid file URL format' };
      }
      
      // Check if this is an HTTP/HTTPS URL and handle it appropriately
      if (fileUrl.startsWith('http://') || fileUrl.startsWith('https://')) {
        console.log(`[VibeSurf] Detected HTTP(S) URL, creating tab for: ${fileUrl}`);
        
        // Try to create a new tab with the URL
        const tab = await chrome.tabs.create({
          url: fileUrl,
          active: true
        });
        
        if (tab && tab.id) {
          console.log(`[VibeSurf] Successfully opened HTTP(S) URL in tab: ${tab.id} (request: ${requestId})`);
          return { success: true, tabId: tab.id };
        } else {
          console.warn(`[VibeSurf] Tab creation returned but no tab ID for request: ${requestId}`);
          return { success: false, error: 'Failed to create tab - no tab ID returned' };
        }
      }
      
      // For file:// URLs, try the original approach
      console.log(`[VibeSurf] Attempting to open file URL: ${fileUrl} (request: ${requestId})`);
      
      // Try to create a new tab with the file URL
      const tab = await chrome.tabs.create({
        url: fileUrl,
        active: true
      });
      
      if (tab && tab.id) {
        console.log(`[VibeSurf] Successfully opened file in tab: ${tab.id} (request: ${requestId})`);
        return { success: true, tabId: tab.id };
      } else {
        console.warn(`[VibeSurf] Tab creation returned but no tab ID for request: ${requestId}`);
        return { success: false, error: 'Failed to create tab - no tab ID returned' };
      }
      
    } catch (error) {
      console.error(`[VibeSurf] Error opening file URL (request: ${requestId}):`, error);
      
      // Provide more specific error messages
      let errorMessage = error.message || 'Unknown error opening file';
      if (error.message && error.message.includes('file://')) {
        errorMessage = 'Browser security restricts opening local files. Try copying the file path and opening manually.';
      }
      
      return {
        success: false,
        error: errorMessage
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

  async copyToClipboard(text) {
    console.log('[VibeSurf] Handling clipboard request, text length:', text?.length);
    
    try {
      // For Chrome extensions running in service worker context,
      // clipboard access is limited. We need to inject script into active tab.
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab) {
        throw new Error('No active tab found');
      }
      
      // Check if we can inject script into this tab
      if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://') ||
          tab.url.startsWith('edge://') || tab.url.startsWith('moz-extension://')) {
        throw new Error('Cannot access clipboard from this type of page');
      }
      
      // Inject script to handle clipboard operation
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (textToCopy) => {
          try {
            // Method 1: Try modern clipboard API
            if (navigator.clipboard && navigator.clipboard.writeText) {
              return navigator.clipboard.writeText(textToCopy).then(() => {
                return { success: true, method: 'modern' };
              }).catch((error) => {
                console.warn('Modern clipboard API failed:', error);
                // Fall back to execCommand
                return fallbackCopy();
              });
            } else {
              // Method 2: Fall back to execCommand
              return Promise.resolve(fallbackCopy());
            }
            
            function fallbackCopy() {
              try {
                const textArea = document.createElement('textarea');
                textArea.value = textToCopy;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                textArea.style.opacity = '0';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                textArea.setSelectionRange(0, textArea.value.length);
                
                const success = document.execCommand('copy');
                document.body.removeChild(textArea);
                
                return { success: success, method: 'execCommand' };
              } catch (error) {
                return { success: false, error: error.message };
              }
            }
          } catch (error) {
            return { success: false, error: error.message };
          }
        },
        args: [text]
      });
      
      const result = await results[0].result;
      console.log('[VibeSurf] Clipboard operation result:', result);
      
      if (result.success) {
        return { success: true, method: result.method };
      } else {
        throw new Error(result.error || 'Clipboard operation failed');
      }
      
    } catch (error) {
      console.error('[VibeSurf] Clipboard operation failed:', error);
      return { success: false, error: error.message };
    }
  }

  // Request microphone permission through background script
  async requestMicrophonePermission() {
    try {
      console.log('[VibeSurf] Requesting microphone permission through background script');
      
      // Get the active tab to inject script
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab) {
        throw new Error('No active tab found');
      }
      
      // Check if we can inject script into this tab
      if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://') ||
          tab.url.startsWith('edge://') || tab.url.startsWith('moz-extension://')) {
        throw new Error('Cannot access microphone from this type of page');
      }
      
      // Inject script to request microphone permission
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          return new Promise((resolve, reject) => {
            try {
              // Check if mediaDevices is available
              if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                reject(new Error('Media devices not supported'));
                return;
              }
              
              // Request microphone with minimal constraints
              const constraints = { audio: true, video: false };
              
              navigator.mediaDevices.getUserMedia(constraints)
                .then(stream => {
                  // Stop the stream immediately after getting permission
                  stream.getTracks().forEach(track => track.stop());
                  resolve({ success: true, hasPermission: true });
                })
                .catch(error => {
                  reject(new Error(`Microphone permission denied: ${error.name} - ${error.message}`));
                });
            } catch (error) {
              reject(new Error(`Failed to request microphone permission: ${error.message}`));
            }
          });
        }
      });
      
      const result = await results[0].result;
      console.log('[VibeSurf] Microphone permission result:', result);
      return result;
      
    } catch (error) {
      console.error('[VibeSurf] Failed to request microphone permission:', error);
      return { success: false, error: error.message };
    }
  }

  // Create a proper permission request page that opens in a new tab
  async requestMicrophonePermissionWithUI() {
    try {
      console.log('[VibeSurf] Opening permission request page in new tab');
      
      // Use the existing permission-request.html file
      const permissionPageUrl = chrome.runtime.getURL('permission-request.html');
      
      // Create a tab with the permission page
      const permissionTab = await chrome.tabs.create({
        url: permissionPageUrl,
        active: true
      });
      
      console.log('[VibeSurf] Created permission tab:', permissionTab.id);
      
      // Return a promise that resolves when we get the permission result
      return new Promise((resolve) => {
        const messageHandler = (message, sender, sendResponse) => {
          if (message.type === 'MICROPHONE_PERMISSION_RESULT') {
            console.log('[VibeSurf] Received permission result:', message);
            
            // Clean up the message listener
            chrome.runtime.onMessage.removeListener(messageHandler);
            
            // Close the permission tab
            chrome.tabs.remove(permissionTab.id).catch(() => {
              // Tab might already be closed
            });
            
            // Resolve the promise
            if (message.granted) {
              resolve({ success: true, hasPermission: true });
            } else {
              resolve({ success: false, error: message.error || 'Permission denied by user' });
            }
          }
        };
        
        // Add the message listener
        chrome.runtime.onMessage.addListener(messageHandler);
        
        // Set a timeout to clean up if the tab is closed without response
        setTimeout(() => {
          chrome.runtime.onMessage.removeListener(messageHandler);
          chrome.tabs.remove(permissionTab.id).catch(() => {});
          resolve({ success: false, error: 'Permission request timed out' });
        }, 30000); // 30 second timeout
      });
      
    } catch (error) {
      console.error('[VibeSurf] Failed to create permission UI:', error);
      return { success: false, error: error.message };
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