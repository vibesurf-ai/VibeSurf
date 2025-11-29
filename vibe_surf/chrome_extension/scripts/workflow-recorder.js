// Workflow Recorder Module
// Handles workflow recording infrastructure for browser automation

class WorkflowRecorder {
  constructor() {
    // Session storage
    this.sessionLogs = new Map(); // Map<tabId, Array<events>>
    this.tabInfo = new Map(); // Map<tabId, {url, title}>
    this.recentUserInteractions = new Map(); // Map<tabId, Array<timestamps>>
    this.isRecordingEnabled = false;
    this.recordingStartTime = null;
    this.recordingTabId = null;
    
    // Event types
    this.EVENT_TYPES = {
      CUSTOM_CLICK: 'CUSTOM_CLICK_EVENT',
      CUSTOM_INPUT: 'CUSTOM_INPUT_EVENT',
      CUSTOM_KEY: 'CUSTOM_KEY_EVENT',
      RRWEB: 'RRWEB_EVENT',
      EXTRACTION: 'EXTRACTION_STEP'
    };
    
    // Navigation event tracking
    this.initialPageLoads = new Set(); // Track initial page loads only
    
    console.log('[WorkflowRecorder] Initialized');
  }
  
  // Start recording workflow
  startRecording(tabId = null) {
    console.log('[WorkflowRecorder] Starting recording', { tabId });
    
    this.isRecordingEnabled = true;
    this.recordingStartTime = Date.now();
    this.recordingTabId = tabId;
    
    // Clear previous session data
    if (tabId) {
      this.sessionLogs.set(tabId, []);
      this.recentUserInteractions.set(tabId, []);
    } else {
      this.sessionLogs.clear();
      this.recentUserInteractions.clear();
      this.tabInfo.clear();
    }
    
    this.initialPageLoads.clear();
    
    return {
      success: true,
      startTime: this.recordingStartTime,
      message: 'Recording started successfully'
    };
  }
  
  // Stop recording workflow
  stopRecording() {
    console.log('[WorkflowRecorder] Stopping recording');
    
    if (!this.isRecordingEnabled) {
      return {
        success: false,
        message: 'Recording is not active'
      };
    }
    
    this.isRecordingEnabled = false;
    const workflowData = this.getRecordingData();
    
    console.log('[WorkflowRecorder] Recording stopped', {
      eventCount: this.getTotalEventCount(),
      duration: Date.now() - this.recordingStartTime
    });
    
    return {
      success: true,
      workflow: workflowData,
      message: 'Recording stopped successfully'
    };
  }
  
  // Get current recording data
  getRecordingData() {
    const allEvents = this.getAllEvents();
    const steps = this.convertStoredEventsToSteps(allEvents);
    
    return {
      steps: steps,
      metadata: {
        recordingStartTime: this.recordingStartTime,
        recordingDuration: this.isRecordingEnabled ? Date.now() - this.recordingStartTime : 0,
        tabCount: this.sessionLogs.size,
        eventCount: allEvents.length
      }
    };
  }
  
  // Get all events from all tabs
  getAllEvents() {
    const allEvents = [];
    
    for (const [tabId, events] of this.sessionLogs.entries()) {
      const tabData = this.tabInfo.get(tabId) || { url: '', title: '' };
      
      events.forEach(event => {
        allEvents.push({
          ...event,
          tabId: tabId,
          tabUrl: tabData.url,
          tabTitle: tabData.title
        });
      });
    }
    
    // Sort by timestamp
    return allEvents.sort((a, b) => a.timestamp - b.timestamp);
  }
  
  // Get total event count
  getTotalEventCount() {
    let count = 0;
    for (const events of this.sessionLogs.values()) {
      count += events.length;
    }
    return count;
  }
  
  // Convert stored events to workflow steps
  convertStoredEventsToSteps(events) {
    const steps = [];
    let stepIndex = 0;
    
    for (const event of events) {
      const step = this.convertEventToStep(event, stepIndex);
      if (step) {
        steps.push(step);
        stepIndex++;
      }
    }
    
    return steps;
  }
  
  // Convert individual event to step
  convertEventToStep(event, index) {
    const baseStep = {
      index: index,
      timestamp: event.timestamp,
      tabId: event.tabId,
      tabUrl: event.tabUrl,
      tabTitle: event.tabTitle
    };
    
    switch (event.type) {
      case this.EVENT_TYPES.CUSTOM_CLICK:
        return {
          ...baseStep,
          type: 'click',
          action: 'click',
          target_text: event.data?.targetText || event.data?.elementText || event.data?.elementTag || 'Unknown Element',
          target_selector: event.data?.selector || '',
          coordinates: event.data?.coordinates || { x: 0, y: 0 },
          screenshot: event.data?.screenshot || null,
          url: event.data?.url || event.tabUrl,
          frameUrl: event.data?.frameUrl || '',
          xpath: event.data?.xpath || '',
          cssSelector: event.data?.selector || '',
          elementTag: event.data?.elementTag || '',
          elementText: event.data?.elementText || '',
          radioButtonInfo: event.data?.radioButtonInfo
        };
        
      case this.EVENT_TYPES.CUSTOM_INPUT:
        return {
          ...baseStep,
          type: 'input',
          action: 'type',
          target_text: event.data?.targetText || event.data?.elementTag || 'Input Field',
          target_selector: event.data?.selector || '',
          value: event.data?.value || '',
          screenshot: event.data?.screenshot || null,
          url: event.data?.url || event.tabUrl,
          frameUrl: event.data?.frameUrl || '',
          xpath: event.data?.xpath || '',
          cssSelector: event.data?.selector || '',
          elementTag: event.data?.elementTag || ''
        };
        
      case this.EVENT_TYPES.CUSTOM_KEY:
        return {
          ...baseStep,
          type: 'keypress',
          action: 'press',
          key: event.data?.key || '',
          modifiers: event.data?.modifiers || [],
          screenshot: event.data?.screenshot || null,
          elementTag: event.data?.elementTag
        };
        
      case this.EVENT_TYPES.RRWEB:
        return this.convertRRWebEvent(event, baseStep);
        
      case this.EVENT_TYPES.EXTRACTION:
        return {
          ...baseStep,
          type: 'extraction',
          action: 'extract',
          extractionType: event.data?.extractionType || 'text',
          selector: event.data?.selector || '',
          value: event.data?.value || '',
          screenshot: event.data?.screenshot || null
        };
        
      default:
        console.warn('[WorkflowRecorder] Unknown event type:', event.type);
        return null;
    }
  }
  
  // Convert RRWeb event to step
  convertRRWebEvent(event, baseStep) {
    const rrwebType = event.data?.type || event.data?.event?.type;
    
    switch (rrwebType) {
      case 'navigation':
      case 'page_load':
        return {
          ...baseStep,
          type: 'navigate',
          action: 'navigate',
          url: event.data?.url || event.tabUrl,
          title: event.data?.title || event.tabTitle
        };
        
      case 'scroll':
        return {
          ...baseStep,
          type: 'scroll',
          action: 'scroll',
          scrollX: event.data?.scrollX || 0,
          scrollY: event.data?.scrollY || 0
        };
        
      default:
        // Generic RRWeb event
        return {
          ...baseStep,
          type: 'rrweb',
          action: rrwebType || 'unknown',
          data: event.data
        };
    }
  }
  
  // Store custom click event
  storeClickEvent(tabId, data) {
    if (!this.isRecordingEnabled) return;
    
    const event = {
      type: this.EVENT_TYPES.CUSTOM_CLICK,
      timestamp: Date.now(),
      data: data
    };
    
    this.storeEvent(tabId, event);
    this.trackUserInteraction(tabId);
    
    console.log('[WorkflowRecorder] Click event stored', { tabId, data });
  }
  
  // Store custom input event - with debouncing/merging
  storeInputEvent(tabId, data) {
    if (!this.isRecordingEnabled) return;
    
    // Check if we should merge with the previous event
    const events = this.sessionLogs.get(tabId);
    if (events && events.length > 0) {
      const lastEvent = events[events.length - 1];
      
      // Merge if:
      // 1. Last event was also an input event
      // 2. It was on the same element (selector matches)
      // 3. It happened recently (e.g., within 2 seconds)
      if (lastEvent.type === this.EVENT_TYPES.CUSTOM_INPUT &&
          lastEvent.data.selector === data.selector &&
          (Date.now() - lastEvent.timestamp) < 2000) {
            
        console.log('[WorkflowRecorder] Merging input event with previous', {
          previousValue: lastEvent.data.value,
          newValue: data.value
        });
        
        // Update the last event with new value and timestamp
        lastEvent.data.value = data.value;
        lastEvent.timestamp = Date.now();
        
        // Also update screenshot if the new one has one (usually the later one is better)
        if (data.screenshot) {
          lastEvent.data.screenshot = data.screenshot;
        }
        
        this.trackUserInteraction(tabId);
        this.broadcastWorkflowDataUpdate();
        return;
      }
    }
    
    const event = {
      type: this.EVENT_TYPES.CUSTOM_INPUT,
      timestamp: Date.now(),
      data: data
    };
    
    this.storeEvent(tabId, event);
    this.trackUserInteraction(tabId);
    
    console.log('[WorkflowRecorder] Input event stored', { tabId, data });
  }
  
  // Store custom key event
  storeKeyEvent(tabId, data) {
    if (!this.isRecordingEnabled) return;
    
    const event = {
      type: this.EVENT_TYPES.CUSTOM_KEY,
      timestamp: Date.now(),
      data: data
    };
    
    this.storeEvent(tabId, event);
    this.trackUserInteraction(tabId);
    
    console.log('[WorkflowRecorder] Key event stored', { tabId, data });
  }
  
  // Store RRWeb event (scroll, navigation, etc.)
  storeRRWebEvent(tabId, data) {
    if (!this.isRecordingEnabled) return;
    
    // Filter navigation events - only store initial page loads
    if (data.type === 'navigation' || data.type === 'page_load') {
      if (this.initialPageLoads.has(tabId)) {
        console.log('[WorkflowRecorder] Skipping duplicate navigation event', { tabId });
        return;
      }
      this.initialPageLoads.add(tabId);
    }
    
    const event = {
      type: this.EVENT_TYPES.RRWEB,
      timestamp: Date.now(),
      data: data
    };
    
    this.storeEvent(tabId, event);
    
    console.log('[WorkflowRecorder] RRWeb event stored', { tabId, type: data.type });
  }
  
  // Store extraction step event
  storeExtractionEvent(tabId, data) {
    if (!this.isRecordingEnabled) return;
    
    const event = {
      type: this.EVENT_TYPES.EXTRACTION,
      timestamp: Date.now(),
      data: data
    };
    
    this.storeEvent(tabId, event);
    
    console.log('[WorkflowRecorder] Extraction event stored', { tabId, data });
  }
  
  // Generic event storage
  storeEvent(tabId, event) {
    if (!this.sessionLogs.has(tabId)) {
      this.sessionLogs.set(tabId, []);
    }
    
    this.sessionLogs.get(tabId).push(event);
    
    // Broadcast update to listeners
    this.broadcastWorkflowDataUpdate();
  }
  
  // Track user interaction timestamp
  trackUserInteraction(tabId) {
    if (!this.recentUserInteractions.has(tabId)) {
      this.recentUserInteractions.set(tabId, []);
    }
    
    const interactions = this.recentUserInteractions.get(tabId);
    interactions.push(Date.now());
    
    // Keep only last 10 interactions
    if (interactions.length > 10) {
      interactions.shift();
    }
  }
  
  // Update tab information
  updateTabInfo(tabId, url, title) {
    this.tabInfo.set(tabId, { url, title });
    console.log('[WorkflowRecorder] Tab info updated', { tabId, url, title });
  }
  
  // Broadcast workflow data update
  broadcastWorkflowDataUpdate() {
    // This can be used to notify listeners about workflow updates
    // For now, just return the current data
    return this.getRecordingData();
  }
  
  // Handle tab events
  handleTabCreated(tab) {
    if (!this.isRecordingEnabled) return;
    
    console.log('[WorkflowRecorder] Tab created', { tabId: tab.id, url: tab.url });
    
    // Skip chrome-extension:// and chrome:// URLs
    if (tab.url && !this.shouldSkipUrl(tab.url)) {
      this.updateTabInfo(tab.id, tab.url, tab.title || '');
      this.storeRRWebEvent(tab.id, {
        type: 'navigation',
        url: tab.url,
        title: tab.title || ''
      });
    }
  }
  
  handleTabUpdated(tabId, changeInfo, tab) {
    if (!this.isRecordingEnabled) return;
    
    // Only track complete navigation events
    if (changeInfo.status === 'complete' && tab.url) {
      // Skip chrome-extension:// and chrome:// URLs
      if (this.shouldSkipUrl(tab.url)) {
        console.log('[WorkflowRecorder] Skipping unsupported URL:', tab.url);
        return;
      }
      
      console.log('[WorkflowRecorder] Tab updated', { tabId, url: tab.url });
      
      this.updateTabInfo(tabId, tab.url, tab.title || '');
      
      // Only store if this is the first navigation for this tab
      if (!this.initialPageLoads.has(tabId)) {
        this.storeRRWebEvent(tabId, {
          type: 'navigation',
          url: tab.url,
          title: tab.title || ''
        });
      }
    }
  }
  
  handleTabActivated(activeInfo) {
    if (!this.isRecordingEnabled) return;
    
    console.log('[WorkflowRecorder] Tab activated', { tabId: activeInfo.tabId });
    // Could be used to track tab switching in the future
  }
  
  handleTabRemoved(tabId, removeInfo) {
    if (!this.isRecordingEnabled) return;
    
    console.log('[WorkflowRecorder] Tab removed', { tabId });
    
    // Clean up tab data
    this.sessionLogs.delete(tabId);
    this.tabInfo.delete(tabId);
    this.recentUserInteractions.delete(tabId);
    this.initialPageLoads.delete(tabId);
  }
  
  // Setup tab listeners (to be called from background.js)
  setupTabListeners() {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      console.warn('[WorkflowRecorder] Chrome tabs API not available');
      return;
    }
    
    // Tab created
    chrome.tabs.onCreated.addListener((tab) => {
      this.handleTabCreated(tab);
    });
    
    // Tab updated
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      this.handleTabUpdated(tabId, changeInfo, tab);
    });
    
    // Tab activated
    chrome.tabs.onActivated.addListener((activeInfo) => {
      this.handleTabActivated(activeInfo);
    });
    
    // Tab removed
    chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
      this.handleTabRemoved(tabId, removeInfo);
    });
    
    console.log('[WorkflowRecorder] Tab listeners set up');
  }
  
  // Handle messages from content scripts or UI
  handleEvent(message, sender) {
    const { type, data } = message;
    const tabId = sender?.tab?.id;
    
    console.log('[WorkflowRecorder] Handling event', { type, tabId });
    
    switch (type) {
      case 'START_RECORDING':
        return this.startRecording(data?.tabId);
        
      case 'STOP_RECORDING':
        return this.stopRecording();
        
      case 'GET_RECORDING_DATA':
        return {
          success: true,
          workflow: this.getRecordingData()
        };
        
      case 'GET_RECORDING_STATUS':
        console.log('[WorkflowRecorder] Status query - isRecording:', this.isRecordingEnabled);
        return {
          success: true,
          isRecording: this.isRecordingEnabled,
          startTime: this.recordingStartTime,
          eventCount: this.getTotalEventCount()
        };
        
      case 'ADD_EXTRACTION_STEP':
        if (tabId) {
          this.storeExtractionEvent(tabId, data);
        }
        return { success: true };
        
      case 'CUSTOM_CLICK_EVENT':
        if (tabId) {
          console.log('[WorkflowRecorder] 🖱️ CLICK event received from tab', tabId, 'Recording enabled:', this.isRecordingEnabled);
          this.storeClickEvent(tabId, data);
        } else {
          console.warn('[WorkflowRecorder] ⚠️ CLICK event has no tabId!');
        }
        return { success: true };
        
      case 'CUSTOM_INPUT_EVENT':
        if (tabId) {
          console.log('[WorkflowRecorder] ⌨️ INPUT event received from tab', tabId, 'Recording enabled:', this.isRecordingEnabled);
          this.storeInputEvent(tabId, data);
        } else {
          console.warn('[WorkflowRecorder] ⚠️ INPUT event has no tabId!');
        }
        return { success: true };
        
      case 'CUSTOM_KEY_EVENT':
        if (tabId) {
          this.storeKeyEvent(tabId, data);
        }
        return { success: true };
        
      case 'RRWEB_EVENT':
        if (tabId) {
          this.storeRRWebEvent(tabId, data);
        }
        return { success: true };
        
      default:
        console.warn('[WorkflowRecorder] Unknown event type:', type);
        return { success: false, error: 'Unknown event type' };
    }
  }
  
  // Capture screenshot for current event
  async captureScreenshot(tabId) {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      console.warn('[WorkflowRecorder] Chrome tabs API not available for screenshot');
      return null;
    }
    
    try {
      const dataUrl = await chrome.tabs.captureVisibleTab(null, {
        format: 'png',
        quality: 80
      });
      
      console.log('[WorkflowRecorder] Screenshot captured', { tabId });
      return dataUrl;
    } catch (error) {
      console.error('[WorkflowRecorder] Failed to capture screenshot:', error);
      return null;
    }
  }
  
  // Check if URL should be skipped from recording
  shouldSkipUrl(url) {
    if (!url) return true;
    
    // Skip chrome-extension://, chrome://, edge://, about: URLs
    const skipPatterns = [
      'chrome-extension://',
      'chrome://',
      'edge://',
      'about:',
      'chrome-search://'
    ];
    
    return skipPatterns.some(pattern => url.startsWith(pattern));
  }
  
  // Clear all recording data
  clearRecording() {
    this.sessionLogs.clear();
    this.tabInfo.clear();
    this.recentUserInteractions.clear();
    this.initialPageLoads.clear();
    this.isRecordingEnabled = false;
    this.recordingStartTime = null;
    this.recordingTabId = null;
    
    console.log('[WorkflowRecorder] Recording data cleared');
  }
  
  // Get recording status
  getStatus() {
    return {
      isRecording: this.isRecordingEnabled,
      startTime: this.recordingStartTime,
      duration: this.isRecordingEnabled ? Date.now() - this.recordingStartTime : 0,
      eventCount: this.getTotalEventCount(),
      tabCount: this.sessionLogs.size
    };
  }
}

// ES6 module export for type: "module" in manifest.json
export { WorkflowRecorder };

// Export for Chrome extension context (for backward compatibility)
if (typeof window !== 'undefined') {
  window.WorkflowRecorder = WorkflowRecorder;
}

// Node.js environment compatibility (if needed)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { WorkflowRecorder };
}