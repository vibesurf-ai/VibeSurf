// Content Script - VibeSurf Extension
// Runs in the context of web pages and can interact with page content

(function() {
  'use strict';
  
  // Avoid running multiple times
  if (window.vibeSurfContentLoaded) {
    return;
  }
  window.vibeSurfContentLoaded = true;
  
  console.log('[VibeSurf Content] Content script loaded on:', window.location.href);
  
  class VibeSurfContent {
    constructor() {
      this.initialized = false;
      this.pageContext = null;
      this.isRecording = false;
      this.setupMessageListener();
      this.collectPageContext();
      this.setupEventListeners();
      
      // Query recording state from background on initialization
      this.queryRecordingState();
    }
    
    // Query if recording is active when content script loads
    async queryRecordingState() {
      try {
        console.log('[VibeSurf Content] Querying recording state from background...');
        const response = await chrome.runtime.sendMessage({ type: 'GET_RECORDING_STATUS' });
        if (response && response.isRecording) {
          this.isRecording = true;
          console.log('[VibeSurf Content] ✅ Recording is ACTIVE - event capture ENABLED');
        } else {
          console.log('[VibeSurf Content] ❌ Recording is INACTIVE - event capture DISABLED');
        }
      } catch (error) {
        console.warn('[VibeSurf Content] Failed to query recording state:', error);
      }
    }
    
    setupMessageListener() {
      // Listen for messages from background script or side panel
      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        console.log('[VibeSurf Content] Received message:', message.type);
        
        switch (message.type) {
          case 'START_RECORDING_CONTENT':
            this.isRecording = true;
            console.log('[VibeSurf Content] Recording enabled');
            sendResponse({ success: true });
            break;
            
          case 'STOP_RECORDING_CONTENT':
            this.isRecording = false;
            console.log('[VibeSurf Content] Recording disabled');
            sendResponse({ success: true });
            break;
            
          case 'GET_PAGE_CONTEXT':
            sendResponse(this.getPageContext());
            break;
            
          case 'SCROLL_TO_ELEMENT':
            this.scrollToElement(message.data?.selector);
            sendResponse({ success: true });
            break;
            
          case 'HIGHLIGHT_ELEMENT':
            this.highlightElement(message.data?.selector);
            sendResponse({ success: true });
            break;
            
          case 'GET_PAGE_TEXT':
            sendResponse({ text: this.getPageText() });
            break;
            
          case 'GET_PAGE_LINKS':
            sendResponse({ links: this.getPageLinks() });
            break;
            
          case 'CLICK_ELEMENT':
            const clickResult = this.clickElement(message.data?.selector);
            sendResponse(clickResult);
            break;
            
          case 'INJECT_MICROPHONE_PERMISSION_IFRAME':
            this.injectMicrophonePermissionIframe()
              .then(result => sendResponse(result))
              .catch(error => sendResponse({ success: false, error: error.message }));
            return true; // Will respond asynchronously
            
          case 'REMOVE_MICROPHONE_PERMISSION_IFRAME':
            this.removeMicrophonePermissionIframe();
            sendResponse({ success: true });
            break;
            
          default:
            console.warn('[VibeSurf Content] Unknown message type:', message.type);
        }
      });
      
      // Listen for postMessage from iframe
      window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'MICROPHONE_PERMISSION_RESULT') {
          console.log('[VibeSurf Content] Received permission result from iframe:', event.data);
          
          // Forward to extension
          chrome.runtime.sendMessage({
            type: 'MICROPHONE_PERMISSION_RESULT',
            ...event.data
          }).catch(() => {
            // Ignore if no listeners
          });
        }
      });
    }
    
    collectPageContext() {
      this.pageContext = {
        url: window.location.href,
        title: document.title,
        domain: window.location.hostname,
        timestamp: Date.now(),
        meta: this.getPageMeta(),
        hasForm: document.querySelector('form') !== null,
        hasTable: document.querySelector('table') !== null,
        linkCount: document.querySelectorAll('a[href]').length,
        imageCount: document.querySelectorAll('img').length,
        inputCount: document.querySelectorAll('input, textarea, select').length
      };
    }
    
    getPageContext() {
      // Refresh context data
      this.collectPageContext();
      return this.pageContext;
    }
    
    getPageMeta() {
      const meta = {};
      
      // Get meta tags
      const metaTags = document.querySelectorAll('meta');
      metaTags.forEach(tag => {
        const name = tag.getAttribute('name') || tag.getAttribute('property');
        const content = tag.getAttribute('content');
        if (name && content) {
          meta[name] = content;
        }
      });
      
      return meta;
    }
    
    getPageText() {
      // Get main content text, excluding scripts and styles
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: function(node) {
            const parent = node.parentElement;
            if (parent && (
              parent.tagName === 'SCRIPT' ||
              parent.tagName === 'STYLE' ||
              parent.tagName === 'NOSCRIPT'
            )) {
              return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      
      let text = '';
      let node;
      while (node = walker.nextNode()) {
        const textContent = node.textContent.trim();
        if (textContent) {
          text += textContent + ' ';
        }
      }
      
      return text.trim();
    }
    
    getPageLinks() {
      const links = [];
      const linkElements = document.querySelectorAll('a[href]');
      
      linkElements.forEach((link, index) => {
        const href = link.getAttribute('href');
        const text = link.textContent.trim();
        
        if (href && text) {
          links.push({
            index,
            href: this.resolveURL(href),
            text,
            title: link.getAttribute('title') || '',
            target: link.getAttribute('target') || '_self'
          });
        }
      });
      
      return links;
    }
    
    resolveURL(url) {
      try {
        return new URL(url, window.location.href).href;
      } catch (error) {
        return url;
      }
    }
    
    scrollToElement(selector) {
      try {
        const element = document.querySelector(selector);
        if (element) {
          element.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
          });
          return true;
        }
      } catch (error) {
        console.error('[VibeSurf Content] Scroll error:', error);
      }
      return false;
    }
    
    highlightElement(selector) {
      try {
        // Remove previous highlights
        this.removeHighlights();
        
        const element = document.querySelector(selector);
        if (element) {
          // Add highlight styling
          element.style.outline = '3px solid #007acc';
          element.style.outlineOffset = '2px';
          element.setAttribute('data-vibesurf-highlight', 'true');
          
          // Auto-remove highlight after 5 seconds
          setTimeout(() => {
            this.removeHighlights();
          }, 5000);
          
          return true;
        }
      } catch (error) {
        console.error('[VibeSurf Content] Highlight error:', error);
      }
      return false;
    }
    
    removeHighlights() {
      const highlighted = document.querySelectorAll('[data-vibesurf-highlight]');
      highlighted.forEach(element => {
        element.style.outline = '';
        element.style.outlineOffset = '';
        element.removeAttribute('data-vibesurf-highlight');
      });
    }
    
    clickElement(selector) {
      try {
        const element = document.querySelector(selector);
        if (element) {
          // Scroll to element first
          element.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
          });
          
          // Wait a bit for scroll, then click
          setTimeout(() => {
            element.click();
          }, 500);
          
          return { success: true, message: 'Element clicked' };
        } else {
          return { success: false, message: 'Element not found' };
        }
      } catch (error) {
        console.error('[VibeSurf Content] Click error:', error);
        return { success: false, message: error.message };
      }
    }
    
    // Inject hidden iframe for microphone permission request
    async injectMicrophonePermissionIframe() {
      try {
        console.log('[VibeSurf Content] Injecting microphone permission iframe...');
        
        // Check if iframe already exists
        const existingIframe = document.getElementById('vibesurf-permission-iframe');
        if (existingIframe) {
          console.log('[VibeSurf Content] Permission iframe already exists');
          return { success: true, alreadyExists: true };
        }
        
        // Create the iframe element
        const iframe = document.createElement('iframe');
        iframe.setAttribute('id', 'vibesurf-permission-iframe');
        iframe.setAttribute('allow', 'microphone');
        iframe.setAttribute('hidden', 'hidden');
        iframe.style.display = 'none';
        iframe.style.width = '0px';
        iframe.style.height = '0px';
        iframe.style.border = 'none';
        iframe.style.position = 'fixed';
        iframe.style.top = '-9999px';
        iframe.style.left = '-9999px';
        iframe.style.zIndex = '-1';
        
        // Set the source to our permission iframe page
        const iframeUrl = chrome.runtime.getURL('permission-iframe.html');
        iframe.src = iframeUrl;
        
        console.log('[VibeSurf Content] Creating iframe with URL:', iframeUrl);
        
        // Return a promise that resolves when permission is granted/denied
        return new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            console.log('[VibeSurf Content] Permission iframe timeout');
            this.removeMicrophonePermissionIframe();
            reject(new Error('Permission request timeout'));
          }, 30000); // 30 second timeout
          
          // Listen for permission result
          const messageHandler = (event) => {
            if (event.data && event.data.type === 'MICROPHONE_PERMISSION_RESULT') {
              console.log('[VibeSurf Content] Received permission result:', event.data);
              
              clearTimeout(timeout);
              window.removeEventListener('message', messageHandler);
              
              if (event.data.success) {
                resolve({
                  success: true,
                  granted: event.data.granted,
                  source: 'iframe'
                });
              } else {
                resolve({
                  success: false,
                  granted: false,
                  error: event.data.error || 'Permission denied',
                  userMessage: event.data.userMessage
                });
              }
              
              // Clean up iframe after a short delay
              setTimeout(() => {
                this.removeMicrophonePermissionIframe();
              }, 1000);
            }
          };
          
          window.addEventListener('message', messageHandler);
          
          // Handle iframe load
          iframe.onload = () => {
            console.log('[VibeSurf Content] Permission iframe loaded successfully');
            
            // Send message to iframe to start permission request
            setTimeout(() => {
              if (iframe.contentWindow) {
                iframe.contentWindow.postMessage({
                  type: 'REQUEST_MICROPHONE_PERMISSION'
                }, '*');
              }
            }, 100);
          };
          
          iframe.onerror = (error) => {
            console.error('[VibeSurf Content] Permission iframe load error:', error);
            clearTimeout(timeout);
            window.removeEventListener('message', messageHandler);
            this.removeMicrophonePermissionIframe();
            reject(new Error('Failed to load permission iframe'));
          };
          
          // Append to document body
          document.body.appendChild(iframe);
          console.log('[VibeSurf Content] Permission iframe injected into page');
        });
        
      } catch (error) {
        console.error('[VibeSurf Content] Failed to inject permission iframe:', error);
        throw error;
      }
    }
    
    // Remove microphone permission iframe
    removeMicrophonePermissionIframe() {
      try {
        const iframe = document.getElementById('vibesurf-permission-iframe');
        if (iframe) {
          console.log('[VibeSurf Content] Removing permission iframe');
          iframe.remove();
          return true;
        }
        return false;
      } catch (error) {
        console.error('[VibeSurf Content] Error removing permission iframe:', error);
        return false;
      }
    }
    
    // Setup event listeners for recording
    setupEventListeners() {
      console.log('[VibeSurf Content] Setting up event listeners');
      
      // Click events
      document.addEventListener('click', (event) => {
        console.log('[VibeSurf Content] Click detected, isRecording:', this.isRecording);
        if (!this.isRecording) return;
        
        const target = event.target;
        if (!target) return;
        
        const data = {
          targetText: this.getElementText(target),
          selector: this.getSelector(target),
          coordinates: { x: event.clientX, y: event.clientY }
        };
        
        console.log('[VibeSurf Content] Sending CUSTOM_CLICK_EVENT:', data);
        chrome.runtime.sendMessage({
          type: 'CUSTOM_CLICK_EVENT',
          data: data
        }).catch((err) => {
          console.error('[VibeSurf Content] Failed to send click event:', err);
        });
      }, true);
      
      // Input events
      document.addEventListener('input', (event) => {
        if (!this.isRecording) return;
        
        const target = event.target;
        if (!target || (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA')) return;
        
        const data = {
          targetText: target.placeholder || target.name || this.getSelector(target),
          selector: this.getSelector(target),
          value: target.type === 'password' ? '********' : target.value
        };
        
        chrome.runtime.sendMessage({
          type: 'CUSTOM_INPUT_EVENT',
          data: data
        }).catch(() => {});
      }, true);
      
      // Key events
      document.addEventListener('keydown', (event) => {
        if (!this.isRecording) return;
        
        if (event.key === 'Enter' || event.key === 'Tab' || event.key === 'Escape') {
          const data = {
            key: event.key,
            modifiers: []
          };
          
          if (event.ctrlKey) data.modifiers.push('Ctrl');
          if (event.metaKey) data.modifiers.push('Meta');
          if (event.shiftKey) data.modifiers.push('Shift');
          if (event.altKey) data.modifiers.push('Alt');
          
          chrome.runtime.sendMessage({
            type: 'CUSTOM_KEY_EVENT',
            data: data
          }).catch(() => {});
        }
      }, true);
    }
    
    // Get readable text from element
    getElementText(element) {
      if (!element) return '';
      
      // For buttons and links, use text content
      if (element.tagName === 'BUTTON' || element.tagName === 'A') {
        return element.textContent?.trim().substring(0, 100) || '';
      }
      
      // For inputs, use label or placeholder
      if (element.tagName === 'INPUT') {
        const label = document.querySelector(`label[for="${element.id}"]`);
        if (label) return label.textContent?.trim() || '';
        return element.placeholder || element.name || '';
      }
      
      return element.textContent?.trim().substring(0, 100) || '';
    }
    
    // Get CSS selector for element
    getSelector(element) {
      if (!element) return '';
      
      if (element.id) return `#${element.id}`;
      if (element.name) return `[name="${element.name}"]`;
      
      let path = [];
      let current = element;
      
      while (current && current.nodeType === Node.ELEMENT_NODE && path.length < 4) {
        let selector = current.nodeName.toLowerCase();
        
        if (current.className && typeof current.className === 'string') {
          const classes = current.className.trim().split(/\s+/);
          if (classes.length > 0 && classes[0]) {
            selector += '.' + classes[0];
          }
        }
        
        path.unshift(selector);
        current = current.parentNode;
      }
      
      return path.join(' > ');
    }
    
    // Utility method to send context updates to background
    sendContextUpdate() {
      try {
        chrome.runtime.sendMessage({
          type: 'PAGE_CONTEXT_UPDATE',
          data: this.getPageContext()
        });
      } catch (error) {
        // Silently handle errors (extension might be reloading)
      }
    }
  }
  
  // Initialize content script
  const vibeSurfContent = new VibeSurfContent();
  
  // Send initial context when page loads
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      vibeSurfContent.sendContextUpdate();
    });
  } else {
    vibeSurfContent.sendContextUpdate();
  }
  
  // Send context updates on navigation
  let lastUrl = window.location.href;
  const observer = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      vibeSurfContent.collectPageContext();
      vibeSurfContent.sendContextUpdate();
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    vibeSurfContent.removeHighlights();
    observer.disconnect();
  });
  
  console.log('[VibeSurf Content] Content script initialized');
  
})();