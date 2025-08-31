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
      this.setupMessageListener();
      this.collectPageContext();
    }
    
    setupMessageListener() {
      // Listen for messages from background script or side panel
      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        console.log('[VibeSurf Content] Received message:', message.type);
        
        switch (message.type) {
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
            
          default:
            console.warn('[VibeSurf Content] Unknown message type:', message.type);
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