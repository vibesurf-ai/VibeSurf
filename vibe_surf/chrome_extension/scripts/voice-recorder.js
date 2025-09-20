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

  // Simplified permission request for Chrome extension
  async requestMicrophonePermission() {
    try {
      console.log('[VoiceRecorder] Requesting microphone permission...');
      
      // For Chrome extensions, try direct permission first
      if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id) {
        try {
          // Try direct getUserMedia first (works if permission already granted)
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(track => track.stop());
          console.log('[VoiceRecorder] Direct permission granted');
          return true;
        } catch (directError) {
          console.log('[VoiceRecorder] Direct permission failed, using iframe method');
          return new Promise((resolve) => {
            this.requestMicrophonePermissionViaIframe(resolve);
          });
        }
      }
      
      // Fallback: Direct permission request for non-extension contexts
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      console.log('[VoiceRecorder] Permission granted');
      return true;
      
    } catch (error) {
      console.error('[VoiceRecorder] Microphone permission denied:', error);
      
      let errorMessage = 'Microphone permission denied';
      if (error.name === 'NotAllowedError') {
        errorMessage = 'Microphone access was denied. Please allow access and try again.';
      } else if (error.name === 'NotFoundError') {
        errorMessage = 'No microphone found. Please connect a microphone.';
      } else if (error.name === 'NotReadableError') {
        errorMessage = 'Microphone is in use by another application.';
      }
      
      const permissionError = new Error(errorMessage);
      permissionError.name = 'MicrophonePermissionError';
      permissionError.originalError = error;
      throw permissionError;
    }
  }

  // Simplified iframe permission request
  async requestMicrophonePermissionViaIframe(resolve) {
    console.log('[VoiceRecorder] Using iframe injection method');
    
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tabs || tabs.length === 0) {
        throw new Error('No active tab found');
      }
      
      const activeTab = tabs[0];
      
      // Check if we can inject into this tab
      if (activeTab.url.startsWith('chrome://') ||
          activeTab.url.startsWith('chrome-extension://')) {
        console.log('[VoiceRecorder] Cannot inject into restricted tab, using tab method');
        return this.showMicrophonePermissionTab(resolve);
      }
      
      // Inject iframe
      const response = await chrome.tabs.sendMessage(activeTab.id, {
        type: 'INJECT_MICROPHONE_PERMISSION_IFRAME'
      });
      
      if (response && response.success) {
        // Listen for permission result
        const messageHandler = (message) => {
          if (message.type === 'MICROPHONE_PERMISSION_RESULT' && message.source === 'iframe') {
            chrome.runtime.onMessage.removeListener(messageHandler);
            resolve(message.granted || message.success || false);
          }
        };
        
        chrome.runtime.onMessage.addListener(messageHandler);
        
        // Timeout cleanup
        setTimeout(() => {
          chrome.runtime.onMessage.removeListener(messageHandler);
          resolve(false);
        }, 30000);
      } else {
        throw new Error('Failed to inject iframe');
      }
      
    } catch (error) {
      console.error('[VoiceRecorder] Iframe method failed:', error);
      this.showMicrophonePermissionTab(resolve);
    }
  }
  
  // Simplified tab permission request
  showMicrophonePermissionTab(resolve) {
    console.log('[VoiceRecorder] Using tab method for permission');
    
    try {
      const permissionUrl = chrome.runtime.getURL('permission-request.html');
      
      chrome.tabs.create({ url: permissionUrl, active: true }, (tab) => {
        if (chrome.runtime.lastError) {
          console.error('[VoiceRecorder] Failed to create tab:', chrome.runtime.lastError);
          resolve(false);
          return;
        }
        
        // Listen for permission result
        const messageHandler = (message) => {
          if (message.type === 'MICROPHONE_PERMISSION_RESULT') {
            chrome.runtime.onMessage.removeListener(messageHandler);
            chrome.tabs.remove(tab.id).catch(() => {});
            resolve(message.granted || false);
          }
        };
        
        chrome.runtime.onMessage.addListener(messageHandler);
        
        // Timeout cleanup
        setTimeout(() => {
          chrome.runtime.onMessage.removeListener(messageHandler);
          chrome.tabs.remove(tab.id).catch(() => {});
          resolve(false);
        }, 30000);
      });
      
    } catch (error) {
      console.error('[VoiceRecorder] Tab method failed:', error);
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
      
      // Check for ASR profiles BEFORE starting recording
      const asrProfiles = await this.apiClient.getASRProfiles(true);
      if (!asrProfiles.profiles || asrProfiles.profiles.length === 0) {
        console.log('[VoiceRecorder] No ASR profiles found, showing configuration modal');
        this.handleNoVoiceProfileError();
        return false;
      }
      
      console.log(`[VoiceRecorder] Found ${asrProfiles.profiles.length} ASR profile(s)`);
      
      // Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        }
      });

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
        // Show voice profile required modal instead of generic error
        this.handleNoVoiceProfileError();
        return;
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

  // Handle no voice profile error with modal
  handleNoVoiceProfileError() {
    console.log('[VoiceRecorder] No voice profiles configured');
    
    // Send message to UI manager to show voice profile required modal
    if (typeof window !== 'undefined' && window.vibeSurfUIManager) {
      try {
        window.vibeSurfUIManager.showVoiceProfileRequiredModal('configure');
      } catch (error) {
        console.error('[VoiceRecorder] Failed to show voice profile modal:', error);
        // Fallback to generic error handling
        this.handleTranscriptionError(new Error('No active ASR profiles found. Please configure an ASR profile in Settings > Voice.'));
      }
    } else {
      // Fallback to generic error handling
      this.handleTranscriptionError(new Error('No active ASR profiles found. Please configure an ASR profile in Settings > Voice.'));
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

  // Check if voice recording should be disabled due to missing ASR profiles
  async isVoiceRecordingAvailable() {
    try {
      const asrProfiles = await this.apiClient.getASRProfiles(true);
      return asrProfiles.profiles && asrProfiles.profiles.length > 0;
    } catch (error) {
      console.error('[VoiceRecorder] Error checking ASR profiles availability:', error);
      return false;
    }
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