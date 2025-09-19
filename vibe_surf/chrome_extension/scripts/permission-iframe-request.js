// Permission iframe request script
// This script runs inside the iframe to request microphone permissions

(function() {
    'use strict';
    
    console.log('[PermissionIframe] Permission iframe script loaded');
    console.log('[PermissionIframe] Current URL:', window.location.href);
    console.log('[PermissionIframe] Parent origin:', window.parent.location.origin);
    console.log('[PermissionIframe] Is secure context:', window.isSecureContext);
    
    const statusEl = document.getElementById('status');
    
    // Function to request microphone permission
    async function requestMicrophonePermission() {
        try {
            console.log('[PermissionIframe] Starting microphone permission request...');
            console.log('[PermissionIframe] Window location:', window.location.href);
            console.log('[PermissionIframe] Is top window:', window === window.top);
            console.log('[PermissionIframe] Document domain:', document.domain);
            
            // Check if media devices are available
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('Media devices not supported in this context');
            }
            
            console.log('[PermissionIframe] Media devices available, requesting getUserMedia...');
            statusEl.textContent = 'Requesting microphone access...';
            statusEl.className = 'status loading';
            
            // Request microphone access with minimal constraints
            console.log('[PermissionIframe] About to call getUserMedia...');
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false
            });
            
            console.log('[PermissionIframe] Permission granted! Stream received');
            console.log('[PermissionIframe] Stream tracks:', stream.getTracks().length);
            
            // Stop all tracks immediately after getting permission
            stream.getTracks().forEach(track => {
                console.log('[PermissionIframe] Stopping track:', track.kind);
                track.stop();
            });
            
            // Update status
            statusEl.textContent = 'Microphone access granted!';
            statusEl.className = 'status success';
            
            // Send success message to parent window
            console.log('[PermissionIframe] Sending success message to parent...');
            console.log('[PermissionIframe] Parent window:', window.parent);
            
            // First try to send to parent window
            try {
                window.parent.postMessage({
                    type: 'MICROPHONE_PERMISSION_RESULT',
                    success: true,
                    granted: true,
                    source: 'iframe'
                }, '*');
                console.log('[PermissionIframe] PostMessage to parent sent successfully');
            } catch (postMessageError) {
                console.error('[PermissionIframe] Failed to send postMessage to parent:', postMessageError);
            }
            
            // Also try to send to extension if available
            if (typeof chrome !== 'undefined' && chrome.runtime) {
                try {
                    chrome.runtime.sendMessage({
                        type: 'MICROPHONE_PERMISSION_RESULT',
                        success: true,
                        granted: true,
                        source: 'iframe'
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            console.log('[PermissionIframe] Chrome runtime error:', chrome.runtime.lastError);
                        } else {
                            console.log('[PermissionIframe] Extension message sent successfully:', response);
                        }
                    });
                } catch (e) {
                    console.error('[PermissionIframe] Could not send to extension:', e);
                }
            }
            
            return true;
            
        } catch (error) {
            console.error('[PermissionIframe] Permission request failed:', error);
            console.error('[PermissionIframe] Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            
            // Update status with error
            let errorMessage = '';
            let userMessage = '';
            
            if (error.name === 'NotAllowedError') {
                errorMessage = 'Microphone access denied';
                userMessage = 'Please allow microphone access when prompted by your browser';
            } else if (error.name === 'NotFoundError') {
                errorMessage = 'No microphone found';
                userMessage = 'Please ensure a microphone is connected';
            } else if (error.name === 'NotReadableError') {
                errorMessage = 'Microphone in use';
                userMessage = 'Please close other apps using the microphone';
            } else if (error.name === 'SecurityError') {
                errorMessage = 'Security restriction';
                userMessage = 'Cannot access microphone due to security settings';
            } else {
                errorMessage = 'Permission failed';
                userMessage = error.message;
            }
            
            statusEl.textContent = `${errorMessage}: ${userMessage}`;
            statusEl.className = 'status error';
            
            // Send error message to parent window
            console.log('[PermissionIframe] Sending error message to parent...');
            console.log('[PermissionIframe] Error details:', { name: error.name, message: error.message });
            
            // First try to send to parent window
            try {
                window.parent.postMessage({
                    type: 'MICROPHONE_PERMISSION_RESULT',
                    success: false,
                    granted: false,
                    error: error.message,
                    errorName: error.name,
                    userMessage: userMessage,
                    source: 'iframe'
                }, '*');
                console.log('[PermissionIframe] Error postMessage to parent sent successfully');
            } catch (postMessageError) {
                console.error('[PermissionIframe] Failed to send error postMessage to parent:', postMessageError);
            }
            
            // Also try to send to extension if available
            if (typeof chrome !== 'undefined' && chrome.runtime) {
                try {
                    chrome.runtime.sendMessage({
                        type: 'MICROPHONE_PERMISSION_RESULT',
                        success: false,
                        granted: false,
                        error: error.message,
                        errorName: error.name,
                        userMessage: userMessage,
                        source: 'iframe'
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            console.log('[PermissionIframe] Chrome runtime error for error message:', chrome.runtime.lastError);
                        } else {
                            console.log('[PermissionIframe] Error extension message sent successfully:', response);
                        }
                    });
                } catch (e) {
                    console.error('[PermissionIframe] Could not send error to extension:', e);
                }
            }
            
            return false;
        }
    }
    
    // Start permission request when iframe loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', requestMicrophonePermission);
    } else {
        requestMicrophonePermission();
    }
    
    // Also listen for messages from parent requesting permission
    window.addEventListener('message', (event) => {
        console.log('[PermissionIframe] Received message from parent:', event.data);
        
        if (event.data && event.data.type === 'REQUEST_MICROPHONE_PERMISSION') {
            console.log('[PermissionIframe] Parent requested permission, starting request...');
            requestMicrophonePermission();
        }
    });
    
    console.log('[PermissionIframe] Permission iframe script initialized');
    
})();