// Permission Request Page Script
// Handles microphone permission request in new tab

const statusEl = document.getElementById('status');

// Add debug logging
console.log('[PermissionPage] Permission page loaded');
console.log('[PermissionPage] Location:', window.location.href);
console.log('[PermissionPage] Media devices available:', !!navigator.mediaDevices);
console.log('[PermissionPage] getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));

document.getElementById('allowBtn').onclick = async function() {
    console.log('[PermissionPage] Allow button clicked');
    statusEl.className = 'loading';
    statusEl.textContent = 'Requesting microphone access...';
    
    try {
        // Check if media devices are available
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Media devices not supported in this context');
        }
        
        console.log('[PermissionPage] Requesting getUserMedia...');
        
        // This will trigger Chrome's standard permission popup in the address bar
        const stream = await navigator.mediaDevices.getUserMedia({audio: true, video: false});
        
        console.log('[PermissionPage] Permission granted, stream received');
        
        // Stop the stream immediately after getting permission
        stream.getTracks().forEach(track => track.stop());
        
        statusEl.className = 'success';
        statusEl.textContent = 'Permission granted! You can close this tab.';
        
        // Send success message to voice recorder
        console.log('[PermissionPage] Sending success message');
        chrome.runtime.sendMessage({
            type: "MICROPHONE_PERMISSION_RESULT", 
            granted: true
        });
        
        // Close tab after a short delay
        setTimeout(() => window.close(), 2000);
        
    } catch (error) {
        console.error('[PermissionPage] Permission error:', error);
        statusEl.className = 'error';
        statusEl.textContent = 'Permission denied: ' + error.message;
        
        // Send error message to voice recorder
        chrome.runtime.sendMessage({
            type: "MICROPHONE_PERMISSION_RESULT", 
            granted: false, 
            error: error.message
        });
    }
};

document.getElementById('denyBtn').onclick = function() {
    console.log('[PermissionPage] Deny button clicked');
    statusEl.className = 'error';
    statusEl.textContent = 'Permission denied by user';
    
    chrome.runtime.sendMessage({
        type: "MICROPHONE_PERMISSION_RESULT", 
        granted: false, 
        error: "User denied permission"
    });
    
    setTimeout(() => window.close(), 1500);
};