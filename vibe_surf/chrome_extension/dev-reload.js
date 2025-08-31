// Development Auto-Reload Script for VibeSurf Extension
// This script enables automatic reloading when files change

(function() {
  'use strict';
  
  // Only run in development mode
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) {
    const manifest = chrome.runtime.getManifest();
    
    // Check if this is a development extension (unpacked)
    const isDevelopment = !('update_url' in manifest);
    
    if (isDevelopment) {
      console.log('[VibeSurf Dev] Auto-reload enabled');
      
      // Check for file changes every 2 seconds
      setInterval(() => {
        fetch(chrome.runtime.getURL('manifest.json'))
          .then(response => response.text())
          .then(content => {
            const currentTime = new Date().getTime();
            const storageKey = 'vibesurf_last_reload';
            
            chrome.storage.local.get([storageKey], (result) => {
              const lastReload = result[storageKey] || 0;
              
              // Check if manifest was modified (simple content check)
              const contentHash = content.length + content.charCodeAt(0);
              const lastHash = localStorage.getItem('vibesurf_content_hash');
              
              if (lastHash && lastHash !== contentHash.toString()) {
                console.log('[VibeSurf Dev] Files changed, reloading extension...');
                chrome.runtime.reload();
              }
              
              localStorage.setItem('vibesurf_content_hash', contentHash.toString());
              chrome.storage.local.set({ [storageKey]: currentTime });
            });
          })
          .catch(error => {
            // Silently ignore errors (extension might be reloading)
          });
      }, 2000);
    }
  }
})();