// Permission Request Page Script
// Handles microphone permission request in new tab

// Helper function to get translated messages
function getMsg(key, substitutions = []) {
  if (typeof chrome !== 'undefined' && chrome.i18n) {
    return chrome.i18n.getMessage(key, substitutions);
  }
  return key;
}

// Translate the page on load
function translatePage() {
  // Translate static elements
  document.title = getMsg('appName');

  const h1 = document.querySelector('h1');
  if (h1 && h1.textContent.startsWith('__MSG_')) {
    h1.textContent = getMsg('microphonePermissionRequired');
  }

  const p = document.querySelector('p');
  if (p && p.textContent.startsWith('__MSG_')) {
    p.textContent = getMsg('microphonePermissionDescription');
  }

  const allowBtn = document.getElementById('allowBtn');
  if (allowBtn && allowBtn.textContent.startsWith('__MSG_')) {
    allowBtn.textContent = getMsg('allowMicrophone');
  }

  const denyBtn = document.getElementById('denyBtn');
  if (denyBtn && denyBtn.textContent.startsWith('__MSG_')) {
    denyBtn.textContent = getMsg('deny');
  }
}

const statusEl = document.getElementById('status');

// Add debug logging
console.log('[PermissionPage] Permission page loaded');
console.log('[PermissionPage] Location:', window.location.href);
console.log('[PermissionPage] Media devices available:', !!navigator.mediaDevices);
console.log('[PermissionPage] getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));

// Translate page on load
translatePage();

document.getElementById('allowBtn').onclick = async function() {
    console.log('[PermissionPage] Allow button clicked');
    console.log('[PermissionPage] Current URL:', window.location.href);
    console.log('[PermissionPage] Media devices available:', !!navigator.mediaDevices);
    console.log('[PermissionPage] getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
    console.log('[PermissionPage] Is secure context:', window.isSecureContext);
    console.log('[PermissionPage] Chrome runtime available:', !!(typeof chrome !== 'undefined' && chrome.runtime));

    statusEl.className = 'loading';
    statusEl.textContent = getMsg('requestingMicrophoneAccess') || 'Requesting microphone access...';
    
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
        statusEl.textContent = getMsg('permissionGranted') || 'Permission granted! You can close this tab.';

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
            errorMessage = getMsg('microphoneAccessDenied') || 'Microphone access was denied. Please check your browser permissions.';
            debugInfo = getMsg('tryMicrophoneIcon') || 'Try clicking the microphone icon in your browser\'s address bar to allow access.';
        } else if (error.name === 'NotFoundError') {
            errorMessage = getMsg('noMicrophoneFound') || 'No microphone found on this device.';
            debugInfo = getMsg('ensureMicrophoneConnected') || 'Please ensure a microphone is connected and try again.';
        } else if (error.name === 'NotReadableError') {
            errorMessage = getMsg('microphoneInUse') || 'Microphone is already in use by another application.';
            debugInfo = getMsg('closeOtherApps') || 'Please close other applications that might be using the microphone.';
        } else if (error.name === 'SecurityError') {
            errorMessage = getMsg('securityRestrictions') || 'Security restrictions prevent microphone access.';
            debugInfo = getMsg('securitySettings') || 'This might be due to browser security settings or the page context.';
        } else {
            errorMessage = (getMsg('permissionDenied') || 'Permission denied:') + ` ${error.message}`;
            debugInfo = `${getMsg('errorType') || 'Error type:'} ${error.name}`;
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
    statusEl.textContent = getMsg('permissionDeniedByUser') || 'Permission denied by user';

    chrome.runtime.sendMessage({
        type: "MICROPHONE_PERMISSION_RESULT",
        granted: false,
        error: "User denied permission"
    });

    setTimeout(() => window.close(), 1500);
};