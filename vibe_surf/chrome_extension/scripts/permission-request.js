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
    console.log('[PermissionPage] Current URL:', window.location.href);
    console.log('[PermissionPage] Media devices available:', !!navigator.mediaDevices);
    console.log('[PermissionPage] getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
    console.log('[PermissionPage] Is secure context:', window.isSecureContext);
    console.log('[PermissionPage] Chrome runtime available:', !!(typeof chrome !== 'undefined' && chrome.runtime));
    
    statusEl.className = 'loading';
    statusEl.textContent = 'Requesting microphone access...';
    
    try {
        // Check if media devices are available
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Media devices not supported in this context');
        }
        
        console.log('[PermissionPage] Requesting getUserMedia...');
        console.log('[PermissionPage] About to call getUserMedia with constraints: {audio: true, video: false}');
        
        // This will trigger Chrome's standard permission popup in the address bar
        const stream = await navigator.mediaDevices.getUserMedia({audio: true, video: false});
        
        console.log('[PermissionPage] Permission granted, stream received');
        console.log('[PermissionPage] Stream tracks:', stream.getTracks().length);
        
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
        console.error('[PermissionPage] Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack
        });
        
        statusEl.className = 'error';
        
        // Provide more user-friendly error messages
        let errorMessage = '';
        let debugInfo = '';
        
        if (error.name === 'NotAllowedError') {
            errorMessage = 'Microphone access was denied. Please check your browser permissions.';
            debugInfo = 'Try clicking the microphone icon in your browser\'s address bar to allow access.';
        } else if (error.name === 'NotFoundError') {
            errorMessage = 'No microphone found on this device.';
            debugInfo = 'Please ensure a microphone is connected and try again.';
        } else if (error.name === 'NotReadableError') {
            errorMessage = 'Microphone is already in use by another application.';
            debugInfo = 'Please close other applications that might be using the microphone.';
        } else if (error.name === 'SecurityError') {
            errorMessage = 'Security restrictions prevent microphone access.';
            debugInfo = 'This might be due to browser security settings or the page context.';
        } else {
            errorMessage = `Permission denied: ${error.message}`;
            debugInfo = `Error type: ${error.name}`;
        }
        
        statusEl.textContent = errorMessage;
        
        // Add debug info to the page
        const debugDiv = document.createElement('div');
        debugDiv.style.marginTop = '10px';
        debugDiv.style.fontSize = '12px';
        debugDiv.style.color = '#666';
        debugDiv.textContent = debugInfo;
        statusEl.appendChild(debugDiv);
        
        // Send error message to voice recorder
        chrome.runtime.sendMessage({
            type: "MICROPHONE_PERMISSION_RESULT",
            granted: false,
            error: error.message,
            errorName: error.name,
            userMessage: errorMessage
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