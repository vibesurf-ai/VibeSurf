// Voice Recording Manager - Handles voice input functionality
// Provides recording capabilities and integration with ASR API

class VibeSurfVoiceRecorder {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.recordingStartTime = null;
    this.maxRecordingDuration = 60000; // 30 seconds max
    this.recordingTimeout = null;
    this.durationInterval = null;
    this.onDurationUpdate = null;
    
    // Recording state callbacks
    this.onRecordingStart = null;
    this.onRecordingStop = null;
    this.onTranscriptionComplete = null;
    this.onTranscriptionError = null;
    
    console.log('[VoiceRecorder] Voice recorder initialized');
  }

  // Check if browser supports media recording
  isSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  // Enhanced permission request with Chrome extension support
  async requestMicrophonePermission() {
    try {
      console.log('[VoiceRecorder] Requesting microphone permission...');
      console.log('[VoiceRecorder] Current location:', window.location.href);
      console.log('[VoiceRecorder] User agent:', navigator.userAgent);
      
      // For Chrome extensions, use iframe injection method
      if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id) {
        console.log('[VoiceRecorder] Detected Chrome extension context');
        console.log('[VoiceRecorder] Extension ID:', chrome.runtime.id);
        
        // Check if we have the microphone permission declared
        try {
          const manifest = chrome.runtime.getManifest();
          const hasMicrophonePermission = manifest.permissions && manifest.permissions.includes('microphone');
          console.log('[VoiceRecorder] Extension manifest microphone permission:', hasMicrophonePermission);
          
          if (!hasMicrophonePermission) {
            throw new Error('Microphone permission not declared in extension manifest');
          }
        } catch (manifestError) {
          console.warn('[VoiceRecorder] Could not check manifest permissions:', manifestError);
        }
        
        // Use iframe injection method (more reliable than tab approach)
        return new Promise((resolve) => {
          this.requestMicrophonePermissionViaIframe(resolve);
        });
      }
      
      // Fallback: Direct permission request (for non-extension contexts or when tab method fails)
      console.log('[VoiceRecorder] Using direct permission request');
      
      const constraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        },
        video: false
      };
      
      console.log('[VoiceRecorder] Attempting getUserMedia with constraints:', constraints);
      
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (firstError) {
        console.warn('[VoiceRecorder] Standard getUserMedia failed:', firstError);
        
        // Try with minimal constraints
        try {
          const minimalConstraints = { audio: true, video: false };
          console.log('[VoiceRecorder] Trying minimal constraints:', minimalConstraints);
          stream = await navigator.mediaDevices.getUserMedia(minimalConstraints);
        } catch (secondError) {
          console.warn('[VoiceRecorder] Minimal constraints failed:', secondError);
          throw firstError;
        }
      }
      
      // Stop the stream immediately after getting permission
      stream.getTracks().forEach(track => {
        try {
          track.stop();
        } catch (e) {
          console.warn('[VoiceRecorder] Error stopping track:', e);
        }
      });
      
      console.log('[VoiceRecorder] Direct microphone permission granted');
      return true;
      
    } catch (error) {
      console.error('[VoiceRecorder] Microphone permission denied:', error);
      
      // Enhanced error logging for Chrome extension context
      console.error('[VoiceRecorder] Detailed error analysis:', {
        errorName: error.name,
        errorMessage: error.message,
        errorStack: error.stack,
        isNotAllowedError: error.name === 'NotAllowedError',
        isSecurityError: error.name === 'SecurityError',
        isNotFoundError: error.name === 'NotFoundError',
        isNotReadableError: error.name === 'NotReadableError',
        extensionContext: typeof chrome !== 'undefined' && chrome.runtime,
        sidePanelContext: window.location.href.includes('sidepanel')
      });
      
      // Provide more detailed error information
      let errorMessage = 'Microphone permission denied';
      let userAction = '';
      
      if (error.name === 'NotAllowedError') {
        errorMessage = 'Microphone access was denied by the browser.';
        userAction = 'Please check your browser permissions and try again. For Chrome extensions, you may need to allow microphone access in Chrome settings.';
      } else if (error.name === 'NotFoundError') {
        errorMessage = 'No microphone found on this device.';
        userAction = 'Please ensure a microphone is connected and recognized by your system.';
      } else if (error.name === 'NotReadableError') {
        errorMessage = 'Microphone is already in use by another application.';
        userAction = 'Please close other applications that might be using the microphone.';
      } else if (error.name === 'SecurityError') {
        errorMessage = 'Security restrictions prevent microphone access.';
        userAction = 'This might be due to browser security settings. For Chrome extensions, ensure the extension has microphone permissions in Chrome settings.';
      } else {
        errorMessage = `Microphone access error: ${error.message}`;
        userAction = 'Please check your browser settings and ensure microphone access is allowed. For Chrome extensions, check extension permissions.';
      }
      
      // Create a custom error with detailed message
      const permissionError = new Error(`${errorMessage} ${userAction}`);
      permissionError.name = 'MicrophonePermissionError';
      permissionError.originalError = error;
      permissionError.userAction = userAction;
      
      throw permissionError;
    }
  }

  // Request microphone permission via iframe injection (more reliable method)
  async requestMicrophonePermissionViaIframe(resolve) {
    console.log('[VoiceRecorder] Using iframe injection method for microphone permission');
    
    try {
      console.log('[VoiceRecorder] Requesting content script to inject permission iframe...');
      
      // First, try to get current active tab to inject iframe
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tabs || tabs.length === 0) {
        throw new Error('No active tab found for iframe injection');
      }
      
      const activeTab = tabs[0];
      console.log('[VoiceRecorder] Active tab found:', activeTab.url);
      
      // Check if we can inject into this tab
      if (activeTab.url.startsWith('chrome://') ||
          activeTab.url.startsWith('chrome-extension://') ||
          activeTab.url.startsWith('edge://') ||
          activeTab.url.startsWith('moz-extension://')) {
        console.warn('[VoiceRecorder] Cannot inject into restricted tab, falling back to new tab method');
        return this.showMicrophonePermissionTab(resolve);
      }
      
      // Send message to content script to inject iframe
      console.log('[VoiceRecorder] Sending iframe injection request to content script...');
      const response = await chrome.tabs.sendMessage(activeTab.id, {
        type: 'INJECT_MICROPHONE_PERMISSION_IFRAME'
      });
      
      console.log('[VoiceRecorder] Iframe injection response:', response);
      
      if (response && response.success) {
        // Set up listener for permission result from content script
        const messageHandler = (message, sender, sendResponse) => {
          console.log('[VoiceRecorder] Message handler received:', message.type, message);
          
          if (message.type === 'MICROPHONE_PERMISSION_RESULT' && message.source === 'iframe') {
            console.log('[VoiceRecorder] Received iframe permission result:', message);
            console.log('[VoiceRecorder] Permission granted:', message.granted);
            console.log('[VoiceRecorder] Success status:', message.success);
            
            // Clean up listener
            chrome.runtime.onMessage.removeListener(messageHandler);
            
            // Resolve with result - use success status if granted is undefined
            const permissionGranted = message.granted !== undefined ? message.granted : message.success;
            console.log('[VoiceRecorder] Final permission result:', permissionGranted);
            resolve(permissionGranted || false);
          }
        };
        
        chrome.runtime.onMessage.addListener(messageHandler);
        
        // Set timeout to clean up
        setTimeout(() => {
          console.log('[VoiceRecorder] Iframe permission request timeout, cleaning up...');
          chrome.runtime.onMessage.removeListener(messageHandler);
          
          // Try to remove iframe
          chrome.tabs.sendMessage(activeTab.id, {
            type: 'REMOVE_MICROPHONE_PERMISSION_IFRAME'
          }).catch(() => {});
          
          resolve(false);
        }, 35000); // 35 second timeout (longer than iframe timeout)
        
      } else {
        throw new Error('Failed to inject permission iframe: ' + (response?.error || 'Unknown error'));
      }
      
    } catch (error) {
      console.error('[VoiceRecorder] Iframe permission request failed:', error);
      console.log('[VoiceRecorder] Falling back to tab method...');
      
      // Fallback to the tab-based method
      this.showMicrophonePermissionTab(resolve);
    }
  }
  
  // Fallback: Show microphone permission using new tab approach
  showMicrophonePermissionTab(resolve) {
    console.log('[VoiceRecorder] Using fallback tab method for microphone permission');
    
    try {
      const permissionUrl = chrome.runtime.getURL('permission-request.html');
      console.log('[VoiceRecorder] Opening permission tab with URL:', permissionUrl);
      
      // Open new tab with permission page
      chrome.tabs.create({
        url: permissionUrl,
        active: true
      }, (tab) => {
        if (chrome.runtime.lastError) {
          console.error('[VoiceRecorder] Failed to create permission tab:', chrome.runtime.lastError);
          this.requestDirectMicrophonePermission(resolve);
          return;
        }
        
        console.log('[VoiceRecorder] Permission tab opened successfully:', tab.id);
        
        // Set up message listener for permission result
        const messageHandler = (message, sender, sendResponse) => {
          console.log('[VoiceRecorder] Tab method - received message:', message.type, message);
          
          if (message.type === 'MICROPHONE_PERMISSION_RESULT') {
            console.log('[VoiceRecorder] Received permission result:', message.granted);
            console.log('[VoiceRecorder] Success status:', message.success);
            
            // Remove the message listener
            chrome.runtime.onMessage.removeListener(messageHandler);
            
            // Close the permission tab
            chrome.tabs.remove(tab.id).catch(() => {});
            
            // Resolve the promise - use success status if granted is undefined
            const permissionGranted = message.granted !== undefined ? message.granted : message.success;
            console.log('[VoiceRecorder] Tab method - final permission result:', permissionGranted);
            resolve(permissionGranted || false);
          }
        };
        
        chrome.runtime.onMessage.addListener(messageHandler);
        
        // Set timeout to clean up
        setTimeout(() => {
          console.log('[VoiceRecorder] Permission request timeout, cleaning up...');
          chrome.runtime.onMessage.removeListener(messageHandler);
          chrome.tabs.remove(tab.id).catch(() => {});
          resolve(false);
        }, 30000); // 30 second timeout
      });
      
    } catch (error) {
      console.error('[VoiceRecorder] Failed to open permission tab:', error);
      // Final fallback to direct permission request
      this.requestDirectMicrophonePermission(resolve);
    }
  }

  // Direct microphone permission request (simplified approach)
  async requestDirectMicrophonePermission(resolve) {
    console.log('[VoiceRecorder] Trying direct microphone permission request');
    
    try {
      // Immediately try to get microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false
      });
      
      console.log('[VoiceRecorder] Direct microphone permission granted!');
      
      // Stop the stream immediately (we just need permission)
      stream.getTracks().forEach(track => track.stop());
      
      resolve(true);
      
    } catch (error) {
      console.error('[VoiceRecorder] Direct microphone permission denied:', error);
      resolve(false);
    }
  }

  // Start voice recording
  async startRecording() {
    if (this.isRecording) {
      console.warn('[VoiceRecorder] Already recording');
      return false;
    }

    if (!this.isSupported()) {
      console.error('[VoiceRecorder] Voice recording not supported in this browser');
      throw new Error('Voice recording is not supported in your browser');
    }

    try {
      console.log('[VoiceRecorder] Starting voice recording...');
      
      // Request microphone access with enhanced error handling for Chrome extensions
      let stream;
      
      try {
        console.log('[VoiceRecorder] Attempting standard getUserMedia approach...');
        console.log('[VoiceRecorder] MediaDevices available:', !!navigator.mediaDevices);
        console.log('[VoiceRecorder] getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
        
        // Try standard approach first
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 44100
          }
        });
        console.log('[VoiceRecorder] Standard getUserMedia successful!');
      } catch (recordingError) {
        console.warn('[VoiceRecorder] Standard recording approach failed:', recordingError);
        console.warn('[VoiceRecorder] Error name:', recordingError.name);
        console.warn('[VoiceRecorder] Error message:', recordingError.message);
        
        // For Chrome extensions, try background script approach
        if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id) {
          try {
            console.log('[VoiceRecorder] Trying background script approach for recording');
            const backgroundResult = await new Promise((resolve, reject) => {
              chrome.runtime.sendMessage(
                { type: 'REQUEST_MICROPHONE_PERMISSION' },
                (response) => {
                  if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                  } else if (response && response.success) {
                    resolve(response);
                  } else {
                    reject(new Error(response?.error || 'Background permission request failed'));
                  }
                }
              );
            });
            
            console.log('[VoiceRecorder] Background script permission result:', backgroundResult);
            if (backgroundResult && backgroundResult.success) {
              // Try getUserMedia again after background permission
              stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                  echoCancellation: true,
                  noiseSuppression: true,
                  sampleRate: 44100
                }
              });
            } else {
              throw recordingError;
            }
          } catch (backgroundError) {
            console.warn('[VoiceRecorder] Background script approach failed:', backgroundError);
            throw recordingError; // Throw the original error
          }
        } else {
          throw recordingError;
        }
      }

      // Create MediaRecorder
      const options = {
        mimeType: 'audio/webm;codecs=opus'
      };

      // Fallback for browsers that don't support webm
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'audio/ogg;codecs=opus';
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          options.mimeType = 'audio/wav';
        }
      }

      this.mediaRecorder = new MediaRecorder(stream, options);
      this.audioChunks = [];
      this.recordingStartTime = Date.now();

      // Set up event handlers
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        this.handleRecordingStop();
      };

      this.mediaRecorder.onerror = (event) => {
        console.error('[VoiceRecorder] MediaRecorder error:', event.error);
        this.stopRecording();
        this.handleRecordingError(event.error);
      };

      // Start recording
      this.mediaRecorder.start();
      this.isRecording = true;

      // Set up duration updates
      this.startDurationUpdates();

      // Set up maximum recording duration
      this.recordingTimeout = setTimeout(() => {
        if (this.isRecording) {
          console.log('[VoiceRecorder] Maximum recording duration reached, stopping automatically');
          this.stopRecording();
        }
      }, this.maxRecordingDuration);

      // Notify callback
      if (this.onRecordingStart) {
        this.onRecordingStart();
      }

      console.log('[VoiceRecorder] Voice recording started');
      return true;

    } catch (error) {
      console.error('[VoiceRecorder] Failed to start recording:', error);
      this.handleRecordingError(error);
      throw error;
    }
  }

  // Stop voice recording
  stopRecording() {
    if (!this.isRecording || !this.mediaRecorder) {
      console.warn('[VoiceRecorder] Not currently recording');
      return false;
    }

    try {
      console.log('[VoiceRecorder] Stopping voice recording...');
      
      // Clear the timeout
      if (this.recordingTimeout) {
        clearTimeout(this.recordingTimeout);
        this.recordingTimeout = null;
      }

      // Stop the MediaRecorder
      this.mediaRecorder.stop();
      
      // Stop all tracks in the stream
      const stream = this.mediaRecorder.stream;
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }

      this.isRecording = false;
      console.log('[VoiceRecorder] Voice recording stopped');

      return true;

    } catch (error) {
      console.error('[VoiceRecorder] Error stopping recording:', error);
      this.handleRecordingError(error);
      return false;
    }
  }

  // Handle recording stop event
  async handleRecordingStop() {
    try {
      if (this.audioChunks.length === 0) {
        console.warn('[VoiceRecorder] No audio data recorded');
        this.handleRecordingError(new Error('No audio data recorded'));
        return;
      }

      // Create audio blob
      const audioBlob = new Blob(this.audioChunks, { 
        type: this.mediaRecorder.mimeType 
      });

      const recordingDuration = Date.now() - this.recordingStartTime;
      console.log(`[VoiceRecorder] Recorded ${audioBlob.size} bytes in ${recordingDuration}ms`);

      // Notify callback
      if (this.onRecordingStop) {
        this.onRecordingStop(audioBlob, recordingDuration);
      }

      // Transcribe the audio
      await this.transcribeAudio(audioBlob);

    } catch (error) {
      console.error('[VoiceRecorder] Error handling recording stop:', error);
      this.handleRecordingError(error);
    }
  }

  // Start duration updates
  startDurationUpdates() {
    this.stopDurationUpdates(); // Clear any existing interval
    
    this.durationInterval = setInterval(() => {
      const duration = this.getRecordingDuration();
      const formattedDuration = this.formatDuration(duration);
      
      if (this.onDurationUpdate) {
        this.onDurationUpdate(formattedDuration, duration);
      }
    }, 1000); // Update every second
  }

  // Stop duration updates
  stopDurationUpdates() {
    if (this.durationInterval) {
      clearInterval(this.durationInterval);
      this.durationInterval = null;
    }
  }

  // Format duration in MM:SS format
  formatDuration(milliseconds) {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  // Transcribe audio using ASR API
  async transcribeAudio(audioBlob) {
    try {
      console.log('[VoiceRecorder] Transcribing audio...');
      
      // Get available ASR profiles
      const asrProfiles = await this.apiClient.getASRProfiles(true);
      
      if (!asrProfiles.profiles || asrProfiles.profiles.length === 0) {
        throw new Error('No active ASR profiles found. Please configure an ASR profile in settings.');
      }

      // Use the first available ASR profile
      const voiceProfileName = asrProfiles.profiles[0].voice_profile_name;
      console.log(`[VoiceRecorder] Using ASR profile: ${voiceProfileName}`);

      // Call the ASR API
      const result = await this.apiClient.transcribeAudio(audioBlob, voiceProfileName);
      
      if (result.success && result.recognized_text) {
        console.log(`[VoiceRecorder] Transcription successful: "${result.recognized_text}"`);
        
        // Notify callback with transcription result
        if (this.onTranscriptionComplete) {
          this.onTranscriptionComplete(result.recognized_text, result);
        }
      } else {
        throw new Error(result.message || 'Transcription failed');
      }

    } catch (error) {
      console.error('[VoiceRecorder] Transcription error:', error);
      this.handleTranscriptionError(error);
    }
  }

  // Handle recording errors
  handleRecordingError(error) {
    this.isRecording = false;
    this.cleanup();
    
    const errorMessage = error.message || 'Voice recording failed';
    console.error('[VoiceRecorder] Recording error:', errorMessage);
    
    if (this.onTranscriptionError) {
      this.onTranscriptionError(errorMessage, 'recording');
    }
  }

  // Handle transcription errors
  handleTranscriptionError(error) {
    const errorMessage = error.message || 'Audio transcription failed';
    console.error('[VoiceRecorder] Transcription error:', errorMessage);
    
    if (this.onTranscriptionError) {
      this.onTranscriptionError(errorMessage, 'transcription');
    }
  }

  // Cleanup resources
  cleanup() {
    if (this.recordingTimeout) {
      clearTimeout(this.recordingTimeout);
      this.recordingTimeout = null;
    }

    if (this.mediaRecorder) {
      if (this.mediaRecorder.state !== 'inactive') {
        try {
          this.mediaRecorder.stop();
        } catch (error) {
          console.warn('[VoiceRecorder] Error stopping MediaRecorder during cleanup:', error);
        }
      }

      // Stop all tracks in the stream
      const stream = this.mediaRecorder.stream;
      if (stream) {
        stream.getTracks().forEach(track => {
          try {
            track.stop();
          } catch (error) {
            console.warn('[VoiceRecorder] Error stopping track during cleanup:', error);
          }
        });
      }

      this.mediaRecorder = null;
    }

    this.audioChunks = [];
    this.isRecording = false;
    this.recordingStartTime = null;
  }

  // Get recording duration
  getRecordingDuration() {
    if (!this.isRecording || !this.recordingStartTime) {
      return 0;
    }
    return Date.now() - this.recordingStartTime;
  }

  // Check if currently recording
  isCurrentlyRecording() {
    return this.isRecording;
  }

  // Set callbacks
  setCallbacks(callbacks) {
    if (callbacks.onRecordingStart) this.onRecordingStart = callbacks.onRecordingStart;
    if (callbacks.onRecordingStop) this.onRecordingStop = callbacks.onRecordingStop;
    if (callbacks.onTranscriptionComplete) this.onTranscriptionComplete = callbacks.onTranscriptionComplete;
    if (callbacks.onTranscriptionError) this.onTranscriptionError = callbacks.onTranscriptionError;
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfVoiceRecorder = VibeSurfVoiceRecorder;
}