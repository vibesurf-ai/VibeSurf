// UI Manager - Core UI management and session interaction
// Coordinates with specialized modules for settings, history, files, and modals

class VibeSurfUIManager {
  constructor(sessionManager, apiClient) {
    this.sessionManager = sessionManager;
    this.apiClient = apiClient;
    this.elements = {};
    this.state = {
      isLoading: false,
      isTaskRunning: false,
      taskInfo: null
    };
    
    // Initialize specialized managers
    this.settingsManager = null;
    this.historyManager = null;
    this.fileManager = null;
    this.modalManager = null;
    this.voiceRecorder = null;

    // Initialize user settings storage
    this.userSettingsStorage = null;

    // Track if we're currently restoring selections to prevent override
    this.isRestoringSelections = false;

    this.bindElements();
    this.initializeTabSelector(); // Initialize tab selector before binding events
    this.initializeSkillSelector(); // Initialize skill selector
    this.initializeManagers();
    this.bindEvents();
    this.setupSessionListeners();
    this.initializeSocialLinks();
  }

  bindElements() {
    // Main UI elements
    this.elements = {
      // Header elements
      newSessionBtn: document.getElementById('new-session-btn'),
      upgradeBtn: document.getElementById('upgrade-btn'),
      historyBtn: document.getElementById('history-btn'),
      settingsBtn: document.getElementById('settings-btn'),

      // Session info
      sessionId: document.getElementById('session-id'),
      copySessionBtn: document.getElementById('copy-session-btn'),

      // Activity area
      activityLog: document.getElementById('activity-log'),

      // Control panel
      controlPanel: document.getElementById('control-panel'),
      cancelBtn: document.getElementById('cancel-btn'),
      resumeBtn: document.getElementById('resume-btn'),
      terminateBtn: document.getElementById('terminate-btn'),

      // Input area
      llmProfileSelect: document.getElementById('llm-profile-select'),
      agentModeSelect: document.getElementById('agent-mode-select'),
      taskInput: document.getElementById('task-input'),
      sendBtn: document.getElementById('send-btn'),
      voiceRecordBtn: document.getElementById('voice-record-btn'),

      // Tab selector elements
      tabSelectorDropdown: document.getElementById('tab-selector-dropdown'),
      tabSelectorCancel: document.getElementById('tab-selector-cancel'),
      tabSelectorConfirm: document.getElementById('tab-selector-confirm'),
      selectAllTabs: document.getElementById('select-all-tabs'),
      tabOptionsList: document.getElementById('tab-options-list'),

      // Skill selector elements
      skillSelectorDropdown: document.getElementById('skill-selector-dropdown'),
      skillOptionsList: document.getElementById('skill-options-list'),

      // Loading
      loadingOverlay: document.getElementById('loading-overlay')
    };

    // Validate critical elements
    const criticalElements = ['activityLog', 'taskInput', 'sendBtn', 'sessionId'];
    for (const key of criticalElements) {
      if (!this.elements[key]) {
        console.error(`[UIManager] Critical element not found: ${key}`);
      }
    }
  }

  initializeManagers() {
    try {
      // Initialize modal manager first (others may depend on it)
      this.modalManager = new VibeSurfModalManager();

      // Initialize user settings storage
      this.userSettingsStorage = new VibeSurfUserSettingsStorage();

      // Initialize voice recorder
      this.voiceRecorder = new VibeSurfVoiceRecorder(this.apiClient);
      this.setupVoiceRecorderCallbacks();

      // Initialize other managers
      this.settingsManager = new VibeSurfSettingsManager(this.apiClient);
      this.historyManager = new VibeSurfHistoryManager(this.apiClient);
      this.fileManager = new VibeSurfFileManager(this.sessionManager);

      // Set up inter-manager communication
      this.setupManagerEvents();


    } catch (error) {
      console.error('[UIManager] Failed to initialize managers:', error);
      this.showNotification('Failed to initialize UI components', 'error');
    }
  }

  setupManagerEvents() {
    // Settings Manager Events
    this.settingsManager.on('profilesUpdated', () => {
      // Only update the profile select if we're not in the middle of restoring selections
      // This prevents the profilesUpdated event from overriding user selections during initialization
      if (!this.isRestoringSelections) {
        this.updateLLMProfileSelect();
      }

      // Also update voice button state when profiles are updated (ASR profiles might have changed)
      this.updateVoiceButtonState();
    });

    this.settingsManager.on('notification', (data) => {
      this.showNotification(data.message, data.type);
    });

    this.settingsManager.on('loading', (data) => {
      if (data.hide) {
        this.hideLoading();
      } else {
        this.showLoading(data.message);
      }
    });

    this.settingsManager.on('error', (data) => {
      console.error('[UIManager] Settings error:', data.error);
      this.showNotification(data.message || 'Settings error occurred', 'error');
    });

    this.settingsManager.on('confirmDeletion', (data) => {
      this.modalManager.showConfirmModal(
        'Delete Profile',
        `Are you sure you want to delete the ${data.type} profile "${data.profileId}"? This action cannot be undone.`,
        {
          confirmText: 'Delete',
          cancelText: 'Cancel',
          type: 'danger',
          onConfirm: () => {
            if (data.callback) data.callback();
          }
        }
      );
    });

    this.settingsManager.on('selectNewDefault', (data) => {
      const options = data.otherProfiles.map(profile =>
        `<option value="${profile.profile_name}">${profile.profile_name}</option>`
      ).join('');

      const modalData = this.modalManager.createModal(`
        <div class="select-default-modal">
          <p>You are deleting the default LLM profile. Please select a new default profile:</p>
          <select id="new-default-select" class="form-select">
            ${options}
          </select>
          <div class="modal-footer">
            <button class="btn-secondary cancel-btn">Cancel</button>
            <button class="btn-primary confirm-btn">Set as Default & Delete</button>
          </div>
        </div>
      `, {
        title: 'Select New Default Profile'
      });

      const select = document.getElementById('new-default-select');
      const confirmBtn = modalData.modal.querySelector('.confirm-btn');
      const cancelBtn = modalData.modal.querySelector('.cancel-btn');

      confirmBtn.addEventListener('click', () => {
        const newDefaultId = select.value;
        if (newDefaultId && data.callback) {
          data.callback(newDefaultId);
        }
        modalData.close();
      });

      cancelBtn.addEventListener('click', () => {
        modalData.close();
      });
    });

    // History Manager Events
    this.historyManager.on('loadSession', (data) => {
      this.loadSession(data.sessionId);
    });

    this.historyManager.on('loading', (data) => {
      if (data.hide) {
        this.hideLoading();
      } else {
        this.showLoading(data.message);
      }
    });

    this.historyManager.on('notification', (data) => {
      this.showNotification(data.message, data.type);
    });

    this.historyManager.on('error', (data) => {
      console.error('[UIManager] History error:', data.error);
      this.showNotification(data.message || 'History error occurred', 'error');
    });

    // File Manager Events
    this.fileManager.on('loading', (data) => {
      if (data.hide) {
        this.hideLoading();
      } else {
        this.showLoading(data.message);
      }
    });

    this.fileManager.on('notification', (data) => {
      this.showNotification(data.message, data.type);
    });

    this.fileManager.on('error', (data) => {
      console.error('[UIManager] File error:', data.error);
      this.showNotification(data.message || 'File error occurred', 'error');
    });

    // Modal Manager Events (if needed for future extensions)
    this.modalManager.on('modalClosed', (data) => {
      // Handle modal close events if needed
    });
  }

  // Voice Recorder Callbacks
  setupVoiceRecorderCallbacks() {
    this.voiceRecorder.setCallbacks({
      onRecordingStart: () => {
        console.log('[UIManager] Voice recording started');
        this.updateVoiceRecordingUI(true);
      },
      onRecordingStop: (audioBlob, duration) => {
        console.log(`[UIManager] Voice recording stopped after ${duration}ms`);
        this.updateVoiceRecordingUI(false);
      },
      onTranscriptionComplete: (transcribedText, result) => {
        console.log(`[UIManager] Transcription completed: "${transcribedText}"`);
        this.handleTranscriptionComplete(transcribedText);
      },
      onTranscriptionError: (errorMessage, errorType) => {
        console.error(`[UIManager] Transcription error: ${errorMessage}`);
        this.handleTranscriptionError(errorMessage, errorType);
      },
      onDurationUpdate: (formattedDuration, durationMs) => {
        this.updateRecordingDuration(formattedDuration, durationMs);
      }
    });
  }

  // Update voice recording UI state
  updateVoiceRecordingUI(isRecording) {
    if (this.elements.voiceRecordBtn) {
      if (isRecording) {
        this.elements.voiceRecordBtn.classList.add('recording');
        this.elements.voiceRecordBtn.setAttribute('title', 'Stop Recording');
        this.elements.voiceRecordBtn.setAttribute('data-tooltip', 'Recording... Click to stop');
      } else {
        this.elements.voiceRecordBtn.classList.remove('recording');
        this.elements.voiceRecordBtn.setAttribute('title', 'Voice Input');
        this.elements.voiceRecordBtn.setAttribute('data-tooltip', 'Click to start voice recording');

        // Clear duration display
        this.updateRecordingDuration('0:00', 0);
      }
    }
  }

  // Update recording duration display
  updateRecordingDuration(formattedDuration, durationMs) {
    if (this.elements.voiceRecordBtn) {
      // Update the tooltip with duration
      this.elements.voiceRecordBtn.setAttribute('data-tooltip', `Recording... ${formattedDuration} - Click to stop`);

      // Create or update duration display element
      let durationElement = this.elements.voiceRecordBtn.querySelector('.recording-duration');
      if (!durationElement) {
        durationElement = document.createElement('div');
        durationElement.className = 'recording-duration';
        this.elements.voiceRecordBtn.appendChild(durationElement);
      }

      durationElement.textContent = formattedDuration;
    }
  }

  // Handle transcription completion
  handleTranscriptionComplete(transcribedText) {
    if (!this.elements.taskInput) {
      console.error('[UIManager] Task input element not found');
      return;
    }

    // Insert transcribed text into the input field
    const currentValue = this.elements.taskInput.value;
    const cursorPosition = this.elements.taskInput.selectionStart;

    // Insert at cursor position or append to end
    const beforeCursor = currentValue.substring(0, cursorPosition);
    const afterCursor = currentValue.substring(cursorPosition);
    const newValue = beforeCursor + transcribedText + afterCursor;

    this.elements.taskInput.value = newValue;

    // Trigger input change event for validation and auto-resize
    this.handleTaskInputChange({ target: this.elements.taskInput });

    // Set cursor position after the inserted text
    const newCursorPosition = cursorPosition + transcribedText.length;
    this.elements.taskInput.setSelectionRange(newCursorPosition, newCursorPosition);
    this.elements.taskInput.focus();

    this.showNotification('Voice transcription completed', 'success');
  }

  // Handle transcription errors
  handleTranscriptionError(errorMessage, errorType) {
    let userMessage = 'Voice transcription failed';

    if (errorType === 'recording') {
      userMessage = `Recording failed: ${errorMessage}`;
    } else if (errorType === 'transcription') {
      if (errorMessage.includes('No active ASR profiles')) {
        userMessage = 'No voice recognition profiles configured. Please set up an ASR profile in Settings > Voice.';
      } else {
        userMessage = `Transcription failed: ${errorMessage}`;
      }
    }

    this.showNotification(userMessage, 'error');
  }

  bindEvents() {
    // Header buttons
    this.elements.newSessionBtn?.addEventListener('click', this.handleNewSession.bind(this));
    this.elements.upgradeBtn?.addEventListener('click', this.handleUpgrade.bind(this));
    this.elements.historyBtn?.addEventListener('click', this.handleShowHistory.bind(this));
    this.elements.settingsBtn?.addEventListener('click', this.handleShowSettings.bind(this));

    // Session controls
    this.elements.copySessionBtn?.addEventListener('click', this.handleCopySession.bind(this));

    // Task controls
    this.elements.cancelBtn?.addEventListener('click', this.handleCancelTask.bind(this));
    this.elements.resumeBtn?.addEventListener('click', this.handleResumeTask.bind(this));
    this.elements.terminateBtn?.addEventListener('click', this.handleTerminateTask.bind(this));

    // Input handling
    this.elements.sendBtn?.addEventListener('click', this.handleSendTask.bind(this));
    this.elements.voiceRecordBtn?.addEventListener('click', this.handleVoiceRecord.bind(this));

    // Task input handling
    this.elements.taskInput?.addEventListener('keydown', this.handleTaskInputKeydown.bind(this));
    this.elements.taskInput?.addEventListener('input', this.handleTaskInputChange.bind(this));

    // LLM profile selection handling
    this.elements.llmProfileSelect?.addEventListener('change', this.handleLlmProfileChange.bind(this));

    // Agent mode selection handling
    this.elements.agentModeSelect?.addEventListener('change', this.handleAgentModeChange.bind(this));

    // Initialize auto-resize for textarea
    if (this.elements.taskInput) {
      this.autoResizeTextarea(this.elements.taskInput);
      // Set initial send button state
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }

    // Bind initial task suggestions if present
    this.bindTaskSuggestionEvents();
  }

  setupSessionListeners() {
    // Listen to session manager events
    this.sessionManager.on('sessionCreated', this.handleSessionCreated.bind(this));
    this.sessionManager.on('sessionLoaded', this.handleSessionLoaded.bind(this));
    this.sessionManager.on('taskSubmitted', this.handleTaskSubmitted.bind(this));
    this.sessionManager.on('taskPaused', this.handleTaskPaused.bind(this));
    this.sessionManager.on('taskResumed', this.handleTaskResumed.bind(this));
    this.sessionManager.on('taskStopped', this.handleTaskStopped.bind(this));
    this.sessionManager.on('taskCompleted', this.handleTaskCompleted.bind(this));
    this.sessionManager.on('newActivity', this.handleNewActivity.bind(this));
    this.sessionManager.on('pollingStarted', this.handlePollingStarted.bind(this));
    this.sessionManager.on('pollingStopped', this.handlePollingStopped.bind(this));
    this.sessionManager.on('sessionError', this.handleSessionError.bind(this));
    this.sessionManager.on('taskError', this.handleTaskError.bind(this));

    // Start periodic task status check
    this.startTaskStatusMonitoring();
  }

  // Session event handlers
  handleSessionCreated(data) {
    this.updateSessionDisplay(data.sessionId);
    this.clearActivityLog();
    this.showWelcomeMessage();
    this.updateControlPanel('ready');
  }

  handleSessionLoaded(data) {
    // Update session display
    this.updateSessionDisplay(data.sessionId);

    // Load and display activity logs
    const activityLogs = this.sessionManager.getActivityLogs();
    this.displayActivityLogs(activityLogs);

    // Update control panel
    const taskStatus = this.sessionManager.getTaskStatus();
    if (taskStatus) {
      this.updateControlPanel(taskStatus);
    }
  }

  handleTaskSubmitted(data) {

    this.updateControlPanel('running');
    this.clearTaskInput();
  }

  handleTaskPaused(data) {
    this.updateControlPanel('paused');
    // Force update UI for paused state - explicitly enable input
    this.forceUpdateUIForPausedState();
    this.showNotification('Task paused successfully', 'info');
  }

  handleTaskResumed(data) {
    this.updateControlPanel('running');
    // Force update UI for running state - disable input
    this.forceUpdateUIForRunningState();
    this.showNotification('Task resumed successfully', 'info');
  }

  handleTaskStopped(data) {
    this.updateControlPanel('ready');
    this.showNotification('Task stopped successfully', 'info');
  }

  handleTaskCompleted(data) {


    const message = data.status === 'done' ? 'Task completed successfully!' : 'Task completed with errors';
    const type = data.status === 'done' ? 'success' : 'error';

    // Check if we need to respect minimum visibility period
    if (this.controlPanelMinVisibilityActive) {

      const remainingTime = 1000;
      setTimeout(() => {

        this.updateControlPanel('ready');
      }, remainingTime);
    } else {

      this.updateControlPanel('ready');
    }

    this.showNotification(message, type);

    // Clear uploaded files when task is completed
    this.fileManager.clearUploadedFiles();
  }

  handleNewActivity(data) {
    this.addActivityLog(data.activity);
    this.scrollActivityToBottom();
  }

  handlePollingStarted(data) {
    // Could add polling indicator here
  }

  handlePollingStopped(data) {
    // Could remove polling indicator here
  }

  handleSessionError(data) {
    console.error('[UIManager] Session error:', data.error);
    this.showNotification(`Session error: ${data.error}`, 'error');
  }

  handleTaskError(data) {
    console.error('[UIManager] Task error:', data.error);


    // Check if this is an LLM connection failure
    if (data.error && typeof data.error === 'object' && data.error.error === 'llm_connection_failed') {

      // Show LLM connection failed modal instead of generic notification
      this.showLLMConnectionFailedModal(data.error);
      this.updateControlPanel('ready'); // Reset UI since task failed to start
      return;
    } else if (data.error && typeof data.error === 'string' && data.error.includes('llm_connection_failed')) {

      // Handle case where error is a string containing the error type
      this.showLLMConnectionFailedModal({
        message: data.error,
        llm_profile: 'unknown'
      });
      this.updateControlPanel('ready'); // Reset UI since task failed to start
      return;
    }

    // Default error handling for other types of errors
    this.showNotification(`Task error: ${data.error}`, 'error');

    this.updateControlPanel('error');

    // Optional: Verify task status after a delay
    setTimeout(() => {
      this.checkTaskStatus().then(status => {
        if (!status.isRunning) {

          this.updateControlPanel('ready');
        } else {

        }
      }).catch(err => {
        console.warn('[UIManager] Could not verify task status after error:', err);
      });
    }, 1000);
  }

  // Task Status Monitoring
  async checkTaskStatus() {
    try {
      const statusCheck = await this.apiClient.checkTaskRunning();
      const wasRunning = this.state.isTaskRunning;

      this.state.isTaskRunning = statusCheck.isRunning;
      this.state.taskInfo = statusCheck.taskInfo;

      // Update UI state when task status changes
      if (wasRunning !== statusCheck.isRunning) {
        this.updateUIForTaskStatus(statusCheck.isRunning);
      }

      return statusCheck;
    } catch (error) {
      console.error('[UIManager] Failed to check task status:', error);
      return { isRunning: false, taskInfo: null };
    }
  }

  startTaskStatusMonitoring() {
    // Check task status every 500ms
    this.taskStatusInterval = setInterval(() => {
      this.checkTaskStatus();
    }, 500);
  }

  stopTaskStatusMonitoring() {
    if (this.taskStatusInterval) {
      clearInterval(this.taskStatusInterval);
      this.taskStatusInterval = null;
    }
  }

  updateUIForTaskStatus(isRunning) {
    const taskStatus = this.sessionManager.getTaskStatus();
    const isPaused = taskStatus === 'paused';

    // Disable/enable input elements based on task status
    if (this.elements.taskInput) {
      // Allow input when paused or not running
      this.elements.taskInput.disabled = isRunning && !isPaused;
      if (isPaused) {
        this.elements.taskInput.placeholder = 'Add additional information or guidance...';
      } else if (isRunning) {
        this.elements.taskInput.placeholder = 'Task is running - please wait...';
      } else {
        this.elements.taskInput.placeholder = 'Ask anything (/ for skills, @ to specify tab)';
      }
    }

    if (this.elements.sendBtn) {
      // Enable send button when paused or when can submit new task
      this.elements.sendBtn.disabled = (isRunning && !isPaused) || (!isPaused && !this.canSubmitTask()) || (isPaused && !this.canAddNewTask());
    }

    if (this.elements.llmProfileSelect) {
      // Allow LLM profile change only when not running
      this.elements.llmProfileSelect.disabled = isRunning && !isPaused;
    }

    if (this.elements.agentModeSelect) {
      // Allow agent mode change only when not running
      this.elements.agentModeSelect.disabled = isRunning && !isPaused;
    }

    // Update voice record button state - disable during task execution unless paused
    if (this.elements.voiceRecordBtn) {
      const shouldDisableVoice = isRunning && !isPaused;
      this.elements.voiceRecordBtn.disabled = shouldDisableVoice;
      if (shouldDisableVoice) {
        this.elements.voiceRecordBtn.classList.add('task-running-disabled');
        this.elements.voiceRecordBtn.setAttribute('title', 'Voice input disabled while task is running');
      } else {
        this.elements.voiceRecordBtn.classList.remove('task-running-disabled');
        if (this.elements.voiceRecordBtn.classList.contains('recording')) {
          this.elements.voiceRecordBtn.setAttribute('title', 'Recording... Click to stop');
        } else {
          this.elements.voiceRecordBtn.setAttribute('title', 'Click to start voice recording');
        }
      }
    }

    // Update file manager state - keep disabled during pause (as per requirement)
    this.fileManager.setEnabled(!isRunning);

    // Also disable header buttons when task is running (but not when paused)
    const headerButtons = [
      this.elements.newSessionBtn,
      this.elements.historyBtn,
      this.elements.settingsBtn
    ];

    headerButtons.forEach(button => {
      if (button) {
        const shouldDisable = isRunning && !isPaused;
        button.disabled = shouldDisable;
        if (shouldDisable) {
          button.classList.add('task-running-disabled');
          button.setAttribute('title', 'Disabled while task is running');
        } else {
          button.classList.remove('task-running-disabled');
          button.removeAttribute('title');
        }
      }
    });
  }

  forceUpdateUIForPausedState() {

    // Enable input during pause
    if (this.elements.taskInput) {
      this.elements.taskInput.disabled = false;
      this.elements.taskInput.placeholder = 'Add additional information or guidance...';
    }

    if (this.elements.sendBtn) {
      const hasText = this.elements.taskInput?.value.trim().length > 0;
      this.elements.sendBtn.disabled = !hasText;
    }

    // Enable voice record button during pause
    if (this.elements.voiceRecordBtn) {
      this.elements.voiceRecordBtn.disabled = false;
      this.elements.voiceRecordBtn.classList.remove('task-running-disabled');
      this.elements.voiceRecordBtn.setAttribute('title', 'Click to start voice recording');
    }

    // Keep LLM profile disabled during pause (user doesn't need to change it)
    if (this.elements.llmProfileSelect) {
      this.elements.llmProfileSelect.disabled = true;
    }

    // Keep agent mode disabled during pause (user doesn't need to change it)
    if (this.elements.agentModeSelect) {
      this.elements.agentModeSelect.disabled = true;
    }

    // Keep file manager disabled during pause
    this.fileManager.setEnabled(false);

    // Keep header buttons disabled during pause (only input, send, and voice should be available)
    const headerButtons = [
      this.elements.newSessionBtn,
      this.elements.historyBtn,
      this.elements.settingsBtn
    ];

    headerButtons.forEach(button => {
      if (button) {
        button.disabled = true;
        button.classList.add('task-running-disabled');
        button.setAttribute('title', 'Disabled during pause - only input, send, and voice input are available');
      }
    });
  }

  forceUpdateUIForRunningState() {


    // Disable input during running
    if (this.elements.taskInput) {
      this.elements.taskInput.disabled = true;
      this.elements.taskInput.placeholder = 'Task is running - please wait...';
    }

    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = true;
    }

    if (this.elements.llmProfileSelect) {
      this.elements.llmProfileSelect.disabled = true;
    }

    if (this.elements.agentModeSelect) {
      this.elements.agentModeSelect.disabled = true;
    }

    // Disable voice record button during running
    if (this.elements.voiceRecordBtn) {
      this.elements.voiceRecordBtn.disabled = true;
      this.elements.voiceRecordBtn.classList.add('task-running-disabled');
      this.elements.voiceRecordBtn.setAttribute('title', 'Voice input disabled while task is running');
    }

    // Update file manager state
    this.fileManager.setEnabled(false);

    // Disable header buttons when task is running
    const headerButtons = [
      this.elements.newSessionBtn,
      this.elements.historyBtn,
      this.elements.settingsBtn
    ];

    headerButtons.forEach(button => {
      if (button) {
        button.disabled = true;
        button.classList.add('task-running-disabled');
        button.setAttribute('title', 'Disabled while task is running');
      }
    });
  }

  canSubmitTask() {
    const hasText = this.elements.taskInput?.value.trim().length > 0;
    const llmProfile = this.elements.llmProfileSelect?.value;
    const hasLlmProfile = llmProfile && llmProfile.trim() !== '';
    return hasText && hasLlmProfile && !this.state.isTaskRunning;
  }

  canAddNewTask() {
    const hasText = this.elements.taskInput?.value.trim().length > 0;
    return hasText;
  }

  async showTaskRunningWarning(action) {
    const taskInfo = this.state.taskInfo;
    const taskId = taskInfo?.task_id || 'unknown';
    const sessionId = taskInfo?.session_id || 'unknown';

    return this.modalManager.showConfirmModalAsync(
      'Task Currently Running',
      `A task is currently ${taskInfo?.status || 'running'}. You must stop the current task before you can ${action}.`,
      {
        confirmText: 'Stop Current Task',
        cancelText: 'Cancel',
        type: 'danger',
        onConfirm: async () => {
          try {
            await this.sessionManager.stopTask('User wants to perform new action');
            return true;
          } catch (error) {
            this.showNotification(`Failed to stop task: ${error.message}`, 'error');
            return false;
          }
        }
      }
    );
  }

  // UI Action Handlers
  async handleNewSession() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('create a new session');
      if (!canProceed) return;
    }

    try {
      this.showLoading('Creating new session...');

      const sessionId = await this.sessionManager.createSession();

      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      this.showNotification(`Failed to create session: ${error.message}`, 'error');
    }
  }

  async handleShowHistory() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('view session history');
      if (!canProceed) return;
    }

    this.historyManager.showHistory();
  }

  async handleShowSettings() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('access settings');
      if (!canProceed) return;
    }

    this.settingsManager.showSettings();
  }

  async handleShowLLMSettings() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('access settings');
      if (!canProceed) return;
    }

    // Show settings and navigate directly to LLM profiles tab
    this.settingsManager.showSettings();

    // Switch to LLM profiles tab after settings are shown
    setTimeout(() => {
      const llmTab = document.querySelector('.settings-tab[data-tab="llm-profiles"]');
      if (llmTab) {
        llmTab.click();
      }
    }, 100);
  }

  async handleCopySession() {
    const sessionId = this.sessionManager.getCurrentSessionId();

    if (!sessionId) {
      this.showNotification('No active session to copy', 'warning');
      return;
    }

    try {
      await navigator.clipboard.writeText(sessionId);
      this.showNotification('Session ID copied to clipboard!', 'success');
    } catch (error) {
      console.error('[UIManager] Failed to copy session ID:', error);
      this.showNotification('Failed to copy session ID', 'error');
    }
  }

  // Upgrade Handler
  async handleUpgrade() {
    try {
      console.log('[UIManager] Starting extension upgrade...');
      
      // Download the latest extension zip from GitHub releases
      const downloadUrl = 'https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip';
      
      // Open download URL in new tab
      const downloadResult = await chrome.runtime.sendMessage({
        type: 'OPEN_FILE_URL',
        data: { fileUrl: downloadUrl }
      });
      
      if (!downloadResult || !downloadResult.success) {
        throw new Error(downloadResult?.error || 'Failed to open download URL');
      }
      
      console.log('[UIManager] Successfully opened download tab:', downloadResult.tabId);
      
      // Also open chrome://extensions in a new tab
      const extensionsResult = await chrome.runtime.sendMessage({
        type: 'OPEN_FILE_URL',
        data: { fileUrl: 'chrome://extensions' }
      });
      
      if (!extensionsResult || !extensionsResult.success) {
        console.warn('[UIManager] Failed to open chrome://extensions:', extensionsResult?.error);
        // Don't throw error here as download was successful
      } else {
        console.log('[UIManager] Successfully opened chrome://extensions tab:', extensionsResult.tabId);
      }
      
      this.showNotification('Extension download started and chrome://extensions opened. Please follow the installation instructions.', 'info');
      
    } catch (error) {
      console.error('[UIManager] Upgrade failed:', error);
      this.showNotification(`Failed to start upgrade: ${error.message}`, 'error');
    }
  }

  // Voice Recording UI Handler
  async handleVoiceRecord() {
    // Check if voice recording is supported
    if (!this.voiceRecorder.isSupported()) {
      this.showNotification('Voice recording is not supported in your browser', 'error');
      return;
    }

    // Check if ASR profiles are available before allowing recording
    const isVoiceAvailable = await this.voiceRecorder.isVoiceRecordingAvailable();
    if (!isVoiceAvailable) {
      console.log('[UIManager] No ASR profiles available, showing configuration modal');
      this.showVoiceProfileRequiredModal('configure');
      return;
    }

    // Enhanced task status check - disable recording during task execution unless paused
    const taskStatus = this.sessionManager.getTaskStatus();
    const isTaskRunning = this.state.isTaskRunning;

    if (isTaskRunning && taskStatus !== 'paused') {
      this.showNotification('Cannot record voice while task is running. Stop the current task or wait for it to complete.', 'warning');
      return;
    }

    // Additional check: if task is paused, allow voice input but show info message
    if (isTaskRunning && taskStatus === 'paused') {
      console.log('[UIManager] Task is paused, allowing voice input');
    }

    // Check if voice button is disabled due to missing ASR profiles
    if (this.elements.voiceRecordBtn && this.elements.voiceRecordBtn.classList.contains('voice-disabled')) {
      console.log('[UIManager] Voice button is disabled due to missing ASR profiles, showing modal');
      this.showVoiceProfileRequiredModal('configure');
      return;
    }

    try {
      if (this.voiceRecorder.isCurrentlyRecording()) {
        // Stop recording
        console.log('[UIManager] Stopping voice recording');
        await this.voiceRecorder.stopRecording();
      } else {
        // Start recording
        console.log('[UIManager] Starting voice recording');

        // Request microphone permission first
        try {
          // For Chrome extensions, ensure we have proper user gesture context
          console.log('[UIManager] Requesting microphone permission with user gesture context');

          // Add a small delay to ensure user gesture is properly registered
          await new Promise(resolve => setTimeout(resolve, 100));

          const hasPermission = await this.voiceRecorder.requestMicrophonePermission();
          if (!hasPermission) {
            this.showNotification('Microphone permission denied. Please allow microphone access to use voice input.', 'error');
            return;
          }
        } catch (permissionError) {
          console.error('[UIManager] Microphone permission error:', permissionError);

          // Handle different types of permission errors with detailed guidance
          let errorMessage = 'Microphone permission denied';
          let detailedHelp = '';

          if (permissionError.name === 'MicrophonePermissionError') {
            errorMessage = permissionError.message;
            if (permissionError.userAction) {
              detailedHelp = permissionError.userAction;
            }
          } else if (permissionError.name === 'NotAllowedError') {
            errorMessage = 'Microphone access was denied by your browser.';
            detailedHelp = 'Please check your browser permissions and try again. You may need to allow microphone access in your browser settings.';
          } else {
            errorMessage = `Microphone access error: ${permissionError.message}`;
            detailedHelp = 'Please ensure your browser allows microphone access and that a microphone is connected.';
          }

          // Show detailed error message
          const fullMessage = detailedHelp ? `${errorMessage}\n\n${detailedHelp}` : errorMessage;
          this.showNotification(fullMessage, 'error');

          // Also log detailed error for debugging
          console.error('[UIManager] Detailed microphone permission error:', {
            name: permissionError.name,
            message: permissionError.message,
            userAction: permissionError.userAction,
            originalError: permissionError.originalError
          });

          this.updateVoiceRecordingUI(false);
          return;
        }

        // Start recording
        await this.voiceRecorder.startRecording();
      }
    } catch (error) {
      console.error('[UIManager] Voice recording error:', error);
      this.showNotification(`Voice recording failed: ${error.message}`, 'error');
      this.updateVoiceRecordingUI(false);
    }
  }

  async handleSendTask() {
    const taskDescription = this.elements.taskInput?.value.trim();

    if (!taskDescription) {
      this.showNotification('Please enter a task description', 'warning');
      this.elements.taskInput?.focus();
      return;
    }

    try {
      // Check task status from session manager first (more reliable than API check)
      const sessionTaskStatus = this.sessionManager.getTaskStatus();
      const isPaused = sessionTaskStatus === 'paused';

      console.log('[UIManager] handleSendTask - session task status:', sessionTaskStatus, 'isPaused:', isPaused);

      if (isPaused) {
        // Handle adding new task to paused execution

        await this.sessionManager.addNewTaskToPaused(taskDescription);

        // Clear the input after successful addition
        this.clearTaskInput();
        this.showNotification('Additional information added to the task', 'success');

        // Automatically resume the task after adding new information

        await this.sessionManager.resumeTask('Auto-resume after adding new task information');

        return;
      }

      // For non-paused states, check if any task is running
      const statusCheck = await this.checkTaskStatus();
      if (statusCheck.isRunning) {
        const canProceed = await this.showTaskRunningWarning('send a new task');
        if (!canProceed) {
          this.showNotification('Cannot send task while another task is running. Please stop the current task first.', 'warning');
          return;
        }
      }

      const llmProfile = this.elements.llmProfileSelect?.value;

      // Check if LLM profile is selected
      if (!llmProfile || llmProfile.trim() === '') {
        // Check if there are any LLM profiles available
        const profiles = this.settingsManager.getLLMProfiles();
        if (profiles.length === 0) {
          // No LLM profiles configured at all
          this.showLLMProfileRequiredModal('configure');
        } else {
          // LLM profiles exist but none selected
          this.showLLMProfileRequiredModal('select');
        }
        return;
      }

      // Immediately clear welcome message and show user request
      this.clearWelcomeMessage();

      const taskData = {
        task_description: taskDescription,
        llm_profile_name: llmProfile,
        agent_mode: this.elements.agentModeSelect?.value || 'thinking'
      };

      // Add uploaded files path if any
      const filePath = this.fileManager.getUploadedFilesForTask();
      if (filePath) {
        taskData.upload_files_path = filePath;

      }

      // Add selected tabs information if any
      const selectedTabsData = this.getSelectedTabsForTask();
      if (selectedTabsData) {
        taskData.selected_tabs = selectedTabsData;
      }

      // Add selected skills information if any
      const selectedSkillsData = this.getSelectedSkillsForTask();
      if (selectedSkillsData) {
        taskData.selected_skills = selectedSkillsData;
      }


      await this.sessionManager.submitTask(taskData);

      // Clear uploaded files after successful task submission
      this.fileManager.clearUploadedFiles();
    } catch (error) {
      // Check if this is an LLM connection failure from API response
      if (error.data && error.data.error === 'llm_connection_failed') {
        this.showLLMConnectionFailedModal(error.data);
      } else {
        this.showNotification(`Failed to submit task: ${error.message}`, 'error');
      }
    }
  }

  async handleCancelTask() {
    try {
      await this.sessionManager.pauseTask('User clicked cancel');
    } catch (error) {
      this.showNotification(`Failed to cancel task: ${error.message}`, 'error');
    }
  }

  async handleResumeTask() {
    try {
      await this.sessionManager.resumeTask('User clicked resume');
    } catch (error) {
      this.showNotification(`Failed to resume task: ${error.message}`, 'error');
    }
  }

  async handleTerminateTask() {
    try {
      // Temporarily stop task status monitoring during terminate to avoid conflicts
      const wasMonitoring = !!this.taskStatusInterval;
      if (wasMonitoring) {
        this.stopTaskStatusMonitoring();
      }

      await this.sessionManager.stopTask('User clicked terminate');

      // Restart monitoring after a brief delay if it was running
      if (wasMonitoring) {
        setTimeout(() => {
          this.startTaskStatusMonitoring();
        }, 1000);
      }
    } catch (error) {
      // Only show error notification for actual failures, not status conflicts
      if (!error.message.includes('status') && !error.message.includes('running')) {
        this.showNotification(`Failed to terminate task: ${error.message}`, 'error');
      }
    }
  }

  handleTaskInputKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.handleSendTask();
      return;
    }

    // Handle tab token deletion
    if (event.key === 'Backspace' || event.key === 'Delete') {
      if (this.handleTabTokenDeletion(event)) {
        event.preventDefault();
        return;
      }
      // Also handle skill token deletion
      if (this.handleSkillTokenDeletion(event)) {
        event.preventDefault();
        return;
      }
    }

    // Handle Tab key for skill auto-completion when only one skill matches
    if (event.key === 'Tab' && this.skillSelectorState.isVisible) {
      if (this.skillSelectorState.filteredSkills.length === 1) {
        event.preventDefault();
        this.selectSkill(this.skillSelectorState.filteredSkills[0]);
      }
    }
  }

  handleTabTokenDeletion(event) {
    const input = event.target;
    const cursorPos = input.selectionStart;
    const text = input.value;

    // Unicode markers for tab tokens
    const startMarker = '\u200B'; // Zero-width space
    const endMarker = '\u200C';   // Zero-width non-joiner

    let tokenStart = -1;
    let tokenEnd = -1;

    if (event.key === 'Backspace') {
      // Only delete if cursor is directly adjacent to end of token
      // Check if the character immediately before cursor is an endMarker
      if (cursorPos > 0 && text[cursorPos - 1] === endMarker) {
        tokenEnd = cursorPos; // Include the marker
        // Find the corresponding start marker backwards
        for (let j = cursorPos - 2; j >= 0; j--) {
          if (text[j] === startMarker) {
            tokenStart = j;
            break;
          }
        }
      }
    } else if (event.key === 'Delete') {
      // Only delete if cursor is directly adjacent to start of token
      // Check if the character immediately at cursor is a startMarker
      if (cursorPos < text.length && text[cursorPos] === startMarker) {
        tokenStart = cursorPos;
        // Find the corresponding end marker forwards
        for (let j = cursorPos + 1; j < text.length; j++) {
          if (text[j] === endMarker) {
            tokenEnd = j + 1; // Include the marker
            break;
          }
        }
      }
    }

    // If we found a complete token, delete it
    if (tokenStart !== -1 && tokenEnd !== -1) {
      const beforeToken = text.substring(0, tokenStart);
      const afterToken = text.substring(tokenEnd);
      input.value = beforeToken + afterToken;
      input.setSelectionRange(tokenStart, tokenStart);

      // Trigger input change event for validation
      this.handleTaskInputChange({ target: input });

      return true; // Prevent default behavior
    }

    return false; // Allow default behavior
  }

  handleSkillTokenDeletion(event) {
    const input = event.target;
    const cursorPos = input.selectionStart;
    const text = input.value;

    // Unicode markers for skill tokens
    const startMarker = '\u200D'; // Zero-width joiner
    const endMarker = '\u200E';   // Left-to-right mark

    let tokenStart = -1;
    let tokenEnd = -1;

    if (event.key === 'Backspace') {
      // Only delete if cursor is directly adjacent to end of token
      if (cursorPos > 0 && text[cursorPos - 1] === endMarker) {
        tokenEnd = cursorPos; // Include the marker
        // Find the corresponding start marker backwards
        for (let j = cursorPos - 2; j >= 0; j--) {
          if (text[j] === startMarker) {
            tokenStart = j;
            break;
          }
        }
      }
    } else if (event.key === 'Delete') {
      // Only delete if cursor is directly adjacent to start of token
      if (cursorPos < text.length && text[cursorPos] === startMarker) {
        tokenStart = cursorPos;
        // Find the corresponding end marker forwards
        for (let j = cursorPos + 1; j < text.length; j++) {
          if (text[j] === endMarker) {
            tokenEnd = j + 1; // Include the marker
            break;
          }
        }
      }
    }

    // If we found a complete token, delete it
    if (tokenStart !== -1 && tokenEnd !== -1) {
      const beforeToken = text.substring(0, tokenStart);
      const afterToken = text.substring(tokenEnd);
      input.value = beforeToken + afterToken;
      input.setSelectionRange(tokenStart, tokenStart);

      // Trigger input change event for validation
      this.handleTaskInputChange({ target: input });

      return true; // Prevent default behavior
    }

    return false; // Allow default behavior
  }

  async handleLlmProfileChange(event) {
    const selectedProfile = event.target.value;



    try {
      // Save the selected LLM profile to user settings storage
      if (this.userSettingsStorage) {

        await this.userSettingsStorage.setSelectedLlmProfile(selectedProfile);


        // Verify the save
        const verified = await this.userSettingsStorage.getSelectedLlmProfile();


        // Also save to localStorage as backup for browser restart scenarios
        localStorage.setItem('vibesurf-llm-profile-backup', selectedProfile);

      } else {
        console.warn('[UIManager] userSettingsStorage not available for LLM profile save');
      }
    } catch (error) {
      console.error('[UIManager] Failed to save LLM profile selection:', error);
    }

    // Re-validate send button state when LLM profile changes
    if (this.elements.taskInput) {
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }
  }

  async handleAgentModeChange(event) {
    const selectedMode = event.target.value;



    try {
      // Save the selected agent mode to user settings storage
      if (this.userSettingsStorage) {

        await this.userSettingsStorage.setSelectedAgentMode(selectedMode);


        // Verify the save
        const verified = await this.userSettingsStorage.getSelectedAgentMode();


        // Also save to localStorage as backup for browser restart scenarios
        localStorage.setItem('vibesurf-agent-mode-backup', selectedMode);

      } else {
        console.warn('[UIManager] userSettingsStorage not available for agent mode save');
      }
    } catch (error) {
      console.error('[UIManager] Failed to save agent mode selection:', error);
    }

    // Re-validate send button state when agent mode changes
    if (this.elements.taskInput) {
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }
  }

  handleTaskInputChange(event) {
    const hasText = event.target.value.trim().length > 0;
    const textarea = event.target;
    const llmProfile = this.elements.llmProfileSelect?.value;
    const hasLlmProfile = llmProfile && llmProfile.trim() !== '';
    const taskStatus = this.sessionManager.getTaskStatus();
    const isPaused = taskStatus === 'paused';

    // Check for @ character to trigger tab selector
    this.handleTabSelectorInput(event);

    // Check for / character to trigger skill selector
    this.handleSkillSelectorInput(event);

    // Update send button state - special handling for pause state
    if (this.elements.sendBtn) {
      if (isPaused) {
        // In pause state, only require text (no LLM profile needed for adding new info)
        this.elements.sendBtn.disabled = !hasText;
      } else {
        // In normal state, require both text and LLM profile and no running task
        this.elements.sendBtn.disabled = !(hasText && hasLlmProfile && !this.state.isTaskRunning);
      }
    }

    // Auto-resize textarea based on content
    this.autoResizeTextarea(textarea);
  }

  autoResizeTextarea(textarea) {
    if (!textarea) return;

    // Reset height to auto to get the natural scrollHeight
    textarea.style.height = 'auto';

    // Calculate the new height based on content
    const minHeight = 44; // Min height from CSS
    const maxHeight = 200; // Max height from CSS
    const newHeight = Math.max(minHeight, Math.min(maxHeight, textarea.scrollHeight));

    // Apply the new height
    textarea.style.height = newHeight + 'px';
  }

  // UI Display Methods
  updateSessionDisplay(sessionId) {

    if (this.elements.sessionId) {
      this.elements.sessionId.textContent = sessionId || '-';

    } else {
      console.error('[UIManager] Session ID element not found');
    }
  }

  updateControlPanel(status) {
    const panel = this.elements.controlPanel;
    const cancelBtn = this.elements.cancelBtn;
    const resumeBtn = this.elements.resumeBtn;
    const terminateBtn = this.elements.terminateBtn;

    console.log(`[UIManager] updateControlPanel called with status: ${status}`);

    if (!panel) {
      console.error('[UIManager] Control panel element not found');
      return;
    }

    // Clear any existing auto-hide timeout
    if (this.controlPanelTimeout) {
      clearTimeout(this.controlPanelTimeout);
      this.controlPanelTimeout = null;
    }

    switch (status) {
      case 'ready':

        panel.classList.add('hidden');
        panel.classList.remove('error-state');
        break;

      case 'running':

        panel.classList.remove('hidden');
        panel.classList.remove('error-state');
        cancelBtn?.classList.remove('hidden');
        resumeBtn?.classList.add('hidden');
        terminateBtn?.classList.add('hidden');

        // For fast-completing tasks, ensure minimum visibility duration
        this.ensureMinimumControlPanelVisibility();
        break;

      case 'paused':

        panel.classList.remove('hidden');
        panel.classList.remove('error-state');
        cancelBtn?.classList.add('hidden');
        resumeBtn?.classList.remove('hidden');
        terminateBtn?.classList.remove('hidden');
        break;

      case 'error':

        panel.classList.remove('hidden');
        panel.classList.add('error-state');
        cancelBtn?.classList.remove('hidden');
        resumeBtn?.classList.add('hidden');
        terminateBtn?.classList.remove('hidden');
        break;

      case 'done':
      case 'completed':
      case 'finished':
        console.log(`[UIManager] Task completed with status: ${status}, hiding panel after delay`);
        // Treat as ready state
        panel.classList.add('hidden');
        panel.classList.remove('error-state');
        break;

      default:
        console.log(`[UIManager] Unknown control panel status: ${status}, hiding panel`);
        panel.classList.add('hidden');
        panel.classList.remove('error-state');
    }
  }

  ensureMinimumControlPanelVisibility() {
    // Set a flag to prevent immediate hiding of control panel for fast tasks
    this.controlPanelMinVisibilityActive = true;

    // Clear the flag after minimum visibility period (2 seconds)
    setTimeout(() => {
      this.controlPanelMinVisibilityActive = false;

    }, 2000);
  }

  clearActivityLog() {
    if (this.elements.activityLog) {
      this.elements.activityLog.innerHTML = '';
    }
  }

  clearWelcomeMessage() {
    if (this.elements.activityLog) {
      const welcomeMsg = this.elements.activityLog.querySelector('.welcome-message');
      if (welcomeMsg) {
        welcomeMsg.remove();
      }
    }
  }

  showWelcomeMessage() {
    const welcomeHTML = `
      <div class="welcome-message">
        <div class="welcome-text">
          <h4>Welcome to VibeSurf</h4>
          <p>Let's vibe surfing the world with AI automation</p>
        </div>
        <div class="quick-tasks">
          <div class="task-suggestion" data-task="research">
            <div class="task-icon">🔍</div>
            <div class="task-content">
              <div class="task-title">Research Founders</div>
              <div class="task-description">Search information about AI browser assistant: VibeSurf, write a brief report</div>
            </div>
          </div>
          <div class="task-suggestion" data-task="news">
            <div class="task-icon">📰</div>
            <div class="task-content">
              <div class="task-title">HackerNews Summary</div>
              <div class="task-description">Get top 10 news from HackerNews and provide a summary</div>
            </div>
          </div>
          <div class="task-suggestion" data-task="analysis">
            <div class="task-icon">📈</div>
            <div class="task-content">
              <div class="task-title">Stock Market Analysis</div>
              <div class="task-description">Analyze recent week stock market trends for major tech companies</div>
            </div>
          </div>
        </div>
      </div>
    `;

    if (this.elements.activityLog) {
      this.elements.activityLog.innerHTML = welcomeHTML;
      this.bindTaskSuggestionEvents();
    }
  }

  bindTaskSuggestionEvents() {
    const taskSuggestions = document.querySelectorAll('.task-suggestion');

    taskSuggestions.forEach(suggestion => {
      suggestion.addEventListener('click', () => {
        const taskDescription = suggestion.querySelector('.task-description').textContent;

        // Populate task input with suggestion (only description, no title prefix)
        if (this.elements.taskInput) {
          this.elements.taskInput.value = taskDescription;
          this.elements.taskInput.focus();

          // Trigger input change event for validation and auto-resize
          this.handleTaskInputChange({ target: this.elements.taskInput });

          // Auto-send the task
          setTimeout(() => {
            this.handleSendTask();
          }, 100); // Small delay to ensure input processing is complete
        }
      });
    });
  }

  displayActivityLogs(logs) {
    this.clearActivityLog();

    if (logs.length === 0) {
      this.showWelcomeMessage();
      return;
    }

    logs.forEach(log => this.addActivityLog(log));

    // Bind link click handlers to all existing activity items after loading
    this.bindLinkHandlersToAllActivityItems();

    this.scrollActivityToBottom();
  }

  bindLinkHandlersToAllActivityItems() {
    // Bind link click handlers to all existing activity items
    const activityItems = this.elements.activityLog.querySelectorAll('.activity-item');
    activityItems.forEach(item => {
      this.bindLinkClickHandlers(item);
    });
  }

  addActivityLog(activityData) {
    // Filter out "done" status messages from UI display only
    const agentStatus = activityData.agent_status || activityData.status || '';

    // Filter done messages that are just status updates without meaningful content
    if (agentStatus.toLowerCase() === 'done') {
      return;
    }

    if (this.elements.activityLog) {
      // Remove welcome message if present
      const welcomeMsg = this.elements.activityLog.querySelector('.welcome-message');
      if (welcomeMsg) {
        welcomeMsg.remove();
      }

      // Check if this is a suggestion_tasks message
      if (agentStatus.toLowerCase() === 'suggestion_tasks') {
        // For suggestion_tasks, only show suggestion cards, not the normal message
        // But the message is still kept in session manager's logs for proper indexing
        this.addSuggestionTaskCards(activityData);
      } else {
        // For all other messages, show the normal activity item
        const activityItem = this.createActivityItem(activityData);
        this.elements.activityLog.appendChild(activityItem);
        activityItem.classList.add('fade-in');

        // Bind copy button functionality
        this.bindCopyButtonEvent(activityItem, activityData);

        // Bind link click handlers to prevent extension freezing
        this.bindLinkClickHandlers(activityItem);
      }
    }
  }

  addSuggestionTaskCards(activityData) {
    const agentMsg = activityData.agent_msg || activityData.message || '';

    if (!agentMsg || typeof agentMsg !== 'string') {
      return;
    }

    // Parse tasks by splitting on newlines and filtering empty lines
    const tasks = agentMsg.split('\n')
      .map(task => task.trim())
      .filter(task => task.length > 0);

    if (tasks.length === 0) {
      return;
    }

    // Create suggestion cards container
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'suggestion-tasks-container';

    // Add header for suggestion cards
    const headerElement = document.createElement('div');
    headerElement.className = 'suggestion-tasks-header';
    headerElement.innerHTML = `
      <h4>Suggestion Follow-Up Tasks</h4>
    `;
    suggestionsContainer.appendChild(headerElement);

    // Create cards container
    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'suggestion-cards';

    // Create individual task cards
    tasks.forEach((task, index) => {
      const taskCard = document.createElement('div');
      taskCard.className = 'suggestion-task-card';
      taskCard.setAttribute('data-task', task);
      taskCard.setAttribute('data-index', index);

      taskCard.innerHTML = `
        <div class="suggestion-card-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="suggestion-card-content">
          <div class="suggestion-task-text">${this.escapeHtml(task)}</div>
        </div>
        <div class="suggestion-card-arrow">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      `;

      // Add click event handler
      taskCard.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleSuggestionTaskClick(task);
      });

      cardsContainer.appendChild(taskCard);
    });

    suggestionsContainer.appendChild(cardsContainer);

    // Add the suggestions container to the activity log
    if (this.elements.activityLog) {
      this.elements.activityLog.appendChild(suggestionsContainer);
      suggestionsContainer.classList.add('fade-in');
    }
  }

  handleSuggestionTaskClick(taskDescription) {


    // First check if task is running
    if (this.state.isTaskRunning) {
      this.showNotification('Cannot submit task while another task is running', 'warning');
      return;
    }

    // Check if LLM profile is selected
    const llmProfile = this.elements.llmProfileSelect?.value;
    if (!llmProfile || llmProfile.trim() === '') {
      this.showLLMProfileRequiredModal('select');
      return;
    }

    // Set the task description in the input first
    if (!this.elements.taskInput) {
      console.error('[UIManager] Task input element not found');
      this.showNotification('Task input not available', 'error');
      return;
    }


    this.elements.taskInput.value = taskDescription;
    this.elements.taskInput.focus();

    // Trigger input change event for validation and auto-resize
    this.handleTaskInputChange({ target: this.elements.taskInput });

    // Auto-submit the task after a short delay
    setTimeout(() => {

      this.handleSendTask();
    }, 100);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  createActivityItem(data) {
    const item = document.createElement('div');

    // Extract activity data with correct keys
    const agentName = data.agent_name || 'system';
    const agentStatus = data.agent_status || data.status || 'info';
    const agentMsg = data.agent_msg || data.message || data.action_description || 'No description';

    // Use backend timestamp if available, otherwise generate frontend timestamp
    let timestamp;
    if (data.timestamp) {
      timestamp = new Date(data.timestamp).toLocaleString();
    } else {
      timestamp = new Date().toLocaleString();
    }

    // Extract token and cost information
    const totalTokens = data.total_tokens;
    const totalCost = data.total_cost;

    // Determine if this is a user message (should be on the right)
    const isUser = agentName.toLowerCase() === 'user';

    // Set CSS classes based on agent type and status
    item.className = `activity-item ${isUser ? 'user-message' : 'agent-message'} ${agentStatus}`;

    // Build metadata display (timestamp, tokens, cost)
    let metadataHtml = `<span class="message-time">${timestamp}</span>`;

    if (totalTokens !== undefined || totalCost !== undefined) {
      metadataHtml += '<span class="message-metrics">';
      if (totalTokens !== undefined) {
        metadataHtml += `<span class="metric-item">tokens: ${totalTokens}</span>`;
      }
      if (totalCost !== undefined) {
        // Format cost to 4 decimal places
        const formattedCost = typeof totalCost === 'number' ? totalCost.toFixed(4) : parseFloat(totalCost || 0).toFixed(4);
        metadataHtml += `<span class="metric-item">cost: $${formattedCost}</span>`;
      }
      metadataHtml += '</span>';
    }

    // Create the message structure similar to chat interface
    item.innerHTML = `
      <div class="message-container ${isUser ? 'user-container' : 'agent-container'}">
        <div class="message-header">
          <span class="agent-name">${agentName}</span>
          <div class="message-metadata">${metadataHtml}</div>
        </div>
        <div class="message-bubble ${isUser ? 'user-bubble' : 'agent-bubble'}">
          <div class="message-status">
            <span class="status-indicator ${agentStatus}">${this.getStatusIcon(agentStatus)}</span>
            <span class="status-text">${agentStatus}</span>
          </div>
          <div class="message-content">
            ${this.formatActivityContent(agentMsg)}
          </div>
          <button class="copy-message-btn" title="Copy message">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z" fill="currentColor"/>
            </svg>
          </button>
        </div>
      </div>
    `;

    return item;
  }

  bindCopyButtonEvent(activityItem, activityData) {
    const copyBtn = activityItem.querySelector('.copy-message-btn');

    if (copyBtn) {
      copyBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();

        await this.copyMessageToClipboard(activityData);
      });
    }
  }

  bindLinkClickHandlers(activityItem) {
    // Handle all link clicks within activity items to prevent extension freezing
    const links = activityItem.querySelectorAll('a');

    links.forEach(link => {
      // Check if handler is already attached to prevent double binding
      if (link.hasAttribute('data-link-handler-attached')) {
        return;
      }

      link.setAttribute('data-link-handler-attached', 'true');

      link.addEventListener('click', async (e) => {
        console.log('[VibeSurf] Link click event detected:', e);

        // Comprehensive event prevention
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation(); // Prevent any other handlers

        // Remove href temporarily to prevent default browser behavior
        const originalHref = link.getAttribute('href');
        const dataFilePath = link.getAttribute('data-file-path');
        link.setAttribute('href', '#');

        // Use data-file-path if available (for file:// links), otherwise use href
        const targetUrl = dataFilePath || originalHref;
        if (!targetUrl || (targetUrl === '#' && !dataFilePath)) return;

        // Debounce - prevent rapid repeated clicks
        if (link.hasAttribute('data-link-processing')) {
          console.log('[VibeSurf] Link already processing, ignoring duplicate click');
          return;
        }

        link.setAttribute('data-link-processing', 'true');

        try {
          console.log('[VibeSurf] Processing link:', targetUrl);

          // Handle file:// links using existing logic
          if (targetUrl.startsWith('file://')) {
            await this.handleFileLinkClick(targetUrl);
          }
          // Handle HTTP/HTTPS links
          else if (targetUrl.startsWith('http://') || targetUrl.startsWith('https://')) {
            await this.handleHttpLinkClick(targetUrl);
          }
          // Handle other protocols or relative URLs
          else {
            await this.handleOtherLinkClick(targetUrl);
          }

          console.log('[VibeSurf] Link processed successfully:', targetUrl);
        } catch (error) {
          console.error('[VibeSurf] Error handling link click:', error);
          this.showNotification(`Failed to open link: ${error.message}`, 'error');
        } finally {
          // Restore original href
          link.setAttribute('href', originalHref);

          // Remove processing flag after a short delay
          setTimeout(() => {
            link.removeAttribute('data-link-processing');
          }, 1000);
        }
      });
    });
  }

  async handleFileLinkClick(fileUrl) {
    console.log('[UIManager] Opening file URL:', fileUrl);

    // Use the background script to handle file URLs
    const result = await chrome.runtime.sendMessage({
      type: 'OPEN_FILE_URL',
      data: { fileUrl }
    });

    if (!result.success) {
      throw new Error(result.error || 'Failed to open file');
    }
  }

  async handleHttpLinkClick(url) {
    console.log('[VibeSurf] Opening HTTP URL:', url);

    try {
      // Open HTTP/HTTPS links in a new tab
      const result = await chrome.runtime.sendMessage({
        type: 'OPEN_FILE_URL',
        data: { fileUrl: url }
      });

      console.log('[VibeSurf] Background script response:', result);

      if (!result || !result.success) {
        throw new Error(result?.error || 'Failed to create tab for URL');
      }

      console.log('[VibeSurf] Successfully opened tab:', result.tabId);
    } catch (error) {
      console.error('[VibeSurf] Error opening HTTP URL:', error);
      throw error;
    }
  }

  async handleOtherLinkClick(url) {
    console.log('[UIManager] Opening other URL:', url);

    // For relative URLs or other protocols, try to open in new tab
    try {
      // Use the background script to handle URL opening
      const result = await chrome.runtime.sendMessage({
        type: 'OPEN_FILE_URL',
        data: { fileUrl: url }
      });

      if (!result.success) {
        throw new Error(result.error || 'Failed to open URL');
      }
    } catch (error) {
      // If the background script method fails, try to construct absolute URL
      if (!url.startsWith('http')) {
        try {
          const absoluteUrl = new URL(url, window.location.href).href;
          const result = await chrome.runtime.sendMessage({
            type: 'OPEN_FILE_URL',
            data: { fileUrl: absoluteUrl }
          });

          if (!result.success) {
            throw new Error(result.error || 'Failed to open absolute URL');
          }
        } catch (urlError) {
          throw new Error(`Failed to open URL: ${urlError.message}`);
        }
      } else {
        throw error;
      }
    }
  }

  async copyMessageToClipboard(activityData) {
    try {
      // Extract only the message content (no agent info or timestamps)
      const agentMsg = activityData.agent_msg || activityData.message || activityData.action_description || 'No description';

      // Convert to plain text
      let messageText = '';
      if (typeof agentMsg === 'object') {
        messageText = JSON.stringify(agentMsg, null, 2);
      } else {
        messageText = String(agentMsg);
        // Strip HTML tags for plain text copy
        messageText = messageText.replace(/<[^>]*>/g, '');
        // Decode HTML entities
        messageText = messageText
          .replace(/&amp;/g, '&')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
          .replace(/&nbsp;/g, ' ')
          .replace(/&#(\d+);/g, (match, dec) => String.fromCharCode(dec))
          .replace(/<br\s*\/?>/gi, '\n')  // Convert <br> tags to newlines
          .replace(/\s+/g, ' ')           // Normalize whitespace
          .trim();                        // Remove leading/trailing whitespace
      }

      // Check clipboard API availability




      // Try multiple clipboard methods
      let copySuccess = false;
      let lastError = null;

      // Method 1: Chrome extension messaging approach
      try {

        await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({
            type: 'COPY_TO_CLIPBOARD',
            text: messageText
          }, (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (response && response.success) {
              resolve();
            } else {
              reject(new Error('Extension messaging copy failed'));
            }
          });
        });
        copySuccess = true;

      } catch (extensionError) {
        console.warn('[UIManager] Chrome extension messaging failed:', extensionError);
        lastError = extensionError;
      }

      // Method 2: Modern clipboard API (if extension method failed)
      if (!copySuccess && navigator.clipboard && navigator.clipboard.writeText) {
        try {

          await navigator.clipboard.writeText(messageText);
          copySuccess = true;

        } catch (clipboardError) {
          console.warn('[UIManager] Modern clipboard API failed:', clipboardError);
          lastError = clipboardError;
        }
      }

      // Method 3: Fallback using execCommand
      if (!copySuccess) {
        try {

          const textArea = document.createElement('textarea');
          textArea.value = messageText;
          textArea.style.position = 'fixed';
          textArea.style.left = '-999999px';
          textArea.style.top = '-999999px';
          textArea.style.opacity = '0';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();
          textArea.setSelectionRange(0, textArea.value.length);

          const success = document.execCommand('copy');
          document.body.removeChild(textArea);

          if (success) {
            copySuccess = true;

          } else {
            console.warn('[UIManager] execCommand returned false');
          }
        } catch (execError) {
          console.warn('[UIManager] execCommand fallback failed:', execError);
          lastError = execError;
        }
      }

      if (copySuccess) {
        // Show visual feedback
        this.showCopyFeedback();

      } else {
        throw new Error(`All clipboard methods failed. Last error: ${lastError?.message || 'Unknown error'}`);
      }

    } catch (error) {
      console.error('[UIManager] Failed to copy message:', error);
      this.showNotification('Copy Fail: ' + error.message, 'error');
    }
  }

  showCopyFeedback() {
    // Show a brief success notification
    this.showNotification('Message copied to clipboard!', 'success');
  }

  getStatusIcon(status) {
    switch (status.toLowerCase()) {
      case 'working':
        return '⚙️';
      case 'thinking':
        return '🤔';
      case 'result':
      case 'done':
        return '✅';
      case 'error':
        return '❌';
      case 'paused':
        return '⏸️';
      case 'running':
        return '🔄';
      case 'request':
        return '💡';
      case 'additional_request':
        return '➕';
      default:
        return '💡';
    }
  }

  formatActivityContent(content) {
    if (!content) return 'No content';

    // Handle object content
    if (typeof content === 'object') {
      return `<pre class="json-content">${JSON.stringify(content, null, 2)}</pre>`;
    }

    // Convert content to string
    let formattedContent = String(content);

    // Use markdown-it library for proper markdown rendering if available
    if (typeof markdownit !== 'undefined') {
      try {
        // Create markdown-it instance with enhanced options
        const md = markdownit({
          html: true,         // Enable HTML tags in source
          breaks: true,       // Convert '\n' in paragraphs into <br>
          linkify: true,      // Autoconvert URL-like text to links
          typographer: true   // Enable some language-neutral replacement + quotes beautification
        });

        // Override link renderer to handle file:// protocol
        const defaultLinkRenderer = md.renderer.rules.link_open || function(tokens, idx, options, env, renderer) {
          return renderer.renderToken(tokens, idx, options);
        };

        md.renderer.rules.link_open = function (tokens, idx, options, env, renderer) {
          const token = tokens[idx];
          const href = token.attrGet('href');

          if (href && href.startsWith('file://')) {
            // Convert file:// links to our custom file-link format
            token.attrSet('href', '#');
            token.attrSet('class', 'file-link');
            token.attrSet('data-file-path', href);
            token.attrSet('title', `Click to open file: ${href}`);
          }

          return defaultLinkRenderer(tokens, idx, options, env, renderer);
        };

        // Add task list support manually (markdown-it doesn't have built-in task lists)
        formattedContent = this.preprocessTaskLists(formattedContent);

        // Pre-process both regular file paths and file:// markdown links
        const regularFilePathRegex = /\[([^\]]+)\]\(([^)]*\/[^)]*\.[^)]+)\)/g;
        const markdownFileLinkRegex = /\[([^\]]+)\]\((file:\/\/[^)]+)\)/g;

        // Handle regular file paths (convert to file:// format)
        formattedContent = formattedContent.replace(regularFilePathRegex, (match, linkText, filePath) => {
          // Only process if it looks like a file path (contains / and extension) and not already a URL
          if (!filePath.startsWith('http') && !filePath.startsWith('file://') && (filePath.includes('/') || filePath.includes('\\'))) {
            const fileUrl = filePath.startsWith('/') ? `file://${filePath}` : `file:///${filePath}`;
            return `<a href="${fileUrl}" class="file-link-markdown">${linkText}</a>`;
          }
          return match;
        });

        // Handle file:// links
        formattedContent = formattedContent.replace(markdownFileLinkRegex, (match, linkText, fileUrl) => {
          // Convert to HTML format that markdown-it will preserve
          return `<a href="${fileUrl}" class="file-link-markdown">${linkText}</a>`;
        });

        // Parse markdown
        const htmlContent = md.render(formattedContent);

        // Post-process to handle local file path links
        let processedContent = htmlContent;

        // Convert our pre-processed file:// links to proper file-link format
        const preProcessedFileLinkRegex = /<a href="(file:\/\/[^"]+)"[^>]*class="file-link-markdown"[^>]*>([^<]*)<\/a>/g;
        processedContent = processedContent.replace(preProcessedFileLinkRegex, (match, fileUrl, linkText) => {
          try {
            // Keep original URL but properly escape HTML attributes
            // Don't decode/encode to preserve original spaces and special characters
            const escapedUrl = fileUrl.replace(/"/g, '&quot;');

            return `<a href="#" class="file-link" data-file-path="${escapedUrl}" title="Click to open file: ${linkText}">${linkText}</a>`;
          } catch (error) {
            console.error('[UIManager] Error processing pre-processed file:// link:', error);
            return match;
          }
        });

        // Add custom classes and post-process
        return processedContent
          .replace(/<pre><code/g, '<pre class="code-block"><code')
          .replace(/<code>/g, '<code class="inline-code">')
          .replace(/<table>/g, '<table class="markdown-table">')
          .replace(/<blockquote>/g, '<blockquote class="markdown-quote">');

      } catch (error) {
        console.warn('[UIManager] markdown-it parsing failed, falling back to basic formatting:', error);
        // Fall through to basic formatting
      }
    }

    // Fallback: Enhanced basic markdown-like formatting
    formattedContent = this.preprocessTaskLists(formattedContent);

    // Bold text **text**
    formattedContent = formattedContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic text *text*
    formattedContent = formattedContent.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Code blocks ```code```
    formattedContent = formattedContent.replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>');

    // Inline code `code`
    formattedContent = formattedContent.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Headers
    formattedContent = formattedContent.replace(/^### (.*$)/gm, '<h3>$1</h3>');
    formattedContent = formattedContent.replace(/^## (.*$)/gm, '<h2>$1</h2>');
    formattedContent = formattedContent.replace(/^# (.*$)/gm, '<h1>$1</h1>');

    // Lists - regular
    formattedContent = formattedContent.replace(/^- (.*$)/gm, '<li>$1</li>');
    formattedContent = formattedContent.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Convert URLs to links
    const httpUrlRegex = /(https?:\/\/[^\s]+)/g;
    formattedContent = formattedContent.replace(httpUrlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');

    // Convert newlines to br tags
    formattedContent = formattedContent.replace(/\n/g, '<br>');

    return formattedContent;
  }

  preprocessTaskLists(content) {
    // Convert markdown task lists to HTML checkboxes
    // - [ ] unchecked task -> checkbox unchecked
    // - [x] checked task -> checkbox checked
    // - [X] checked task -> checkbox checked
    return content
      .replace(/^- \[ \] (.*)$/gm, '<div class="task-item"><input type="checkbox" disabled> $1</div>')
      .replace(/^- \[[xX]\] (.*)$/gm, '<div class="task-item"><input type="checkbox" checked disabled> $1</div>');
  }

  scrollActivityToBottom() {
    if (this.elements.activityLog) {
      this.elements.activityLog.scrollTop = this.elements.activityLog.scrollHeight;
    }
  }

  clearTaskInput() {
    if (this.elements.taskInput) {
      this.elements.taskInput.value = '';
    }

    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = true;
    }
  }

  async loadSession(sessionId) {
    // Check if task is running
    if (this.state.isTaskRunning) {
      const canProceed = await this.showTaskRunningWarning('load a different session');
      if (!canProceed) return;
    }

    try {
      this.showLoading('Loading session...');

      const success = await this.sessionManager.loadSession(sessionId);

      this.hideLoading();

      if (!success) {
        this.showNotification('Failed to load session', 'error');
      }
    } catch (error) {
      this.hideLoading();
      this.showNotification(`Failed to load session: ${error.message}`, 'error');
    }
  }

  async updateLLMProfileSelect() {
    if (!this.elements.llmProfileSelect) return;

    // Preserve current user selection if any (to avoid overriding during profile updates)
    const currentSelection = this.elements.llmProfileSelect.value;

    const profiles = this.settingsManager.getLLMProfiles();
    const select = this.elements.llmProfileSelect;
    select.innerHTML = '';

    if (profiles.length === 0) {
      // Add placeholder option when no profiles available
      const placeholderOption = document.createElement('option');
      placeholderOption.value = '';
      placeholderOption.textContent = 'No LLM profiles configured - Go to Settings';
      placeholderOption.disabled = true;
      placeholderOption.selected = true;
      select.appendChild(placeholderOption);
    } else {
      // Add default empty option
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = 'Select LLM Profile...';
      emptyOption.disabled = true;
      select.appendChild(emptyOption);

      // Determine selection priority: current selection > saved selection > default profile
      let targetSelection = currentSelection; // Preserve current selection first

      // If no current selection, get saved selection
      if (!targetSelection) {
        try {
          if (this.userSettingsStorage) {
            targetSelection = await this.userSettingsStorage.getSelectedLlmProfile();
          }
        } catch (error) {
          console.error('[UIManager] Failed to get saved LLM profile selection:', error);
        }
      }

      // Add actual profiles
      let hasSelectedProfile = false;
      let hasTargetProfile = false;

      profiles.forEach(profile => {
        const option = document.createElement('option');
        option.value = profile.profile_name;
        option.textContent = profile.profile_name;

        // Check if this profile matches our target selection
        if (targetSelection && profile.profile_name === targetSelection) {
          hasTargetProfile = true;
        }

        select.appendChild(option);
      });

      // Apply selection based on priority
      if (hasTargetProfile) {
        select.value = targetSelection;
        hasSelectedProfile = true;
      } else {
        // Fall back to default profile if target not available
        const defaultProfile = profiles.find(p => p.is_default);
        if (defaultProfile) {
          select.value = defaultProfile.profile_name;
          hasSelectedProfile = true;
        }
      }

    }

    // Update send button state if taskInput exists
    if (this.elements.taskInput) {
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }
  }

  showLLMProfileRequiredModal(action) {
    const isConfigureAction = action === 'configure';
    const title = isConfigureAction ? 'LLM Profile Required' : 'Please Select LLM Profile';
    const message = isConfigureAction
      ? 'No LLM profiles are configured. You need to configure at least one LLM profile before sending tasks.'
      : 'Please select an LLM profile from the dropdown to proceed with your task.';

    const options = isConfigureAction
      ? {
          confirmText: 'Open Settings',
          cancelText: 'Cancel',
          onConfirm: () => {
            this.handleShowLLMSettings();
          }
        }
      : {
          confirmText: 'OK',
          cancelText: 'Open Settings',
          onConfirm: () => {
            this.elements.llmProfileSelect?.focus();
          },
          onCancel: () => {
            this.handleShowLLMSettings();
          }
        };

    this.modalManager.showWarningModal(title, message, options);
  }

  showVoiceProfileRequiredModal(action) {
    const isConfigureAction = action === 'configure';
    const title = isConfigureAction ? 'Voice Profile Required' : 'Please Select Voice Profile';
    const message = isConfigureAction
      ? 'No voice recognition (ASR) profiles are configured. You need to configure at least one voice profile before using voice input.'
      : 'Please configure a voice recognition profile to use voice input functionality.';

    const options = isConfigureAction
      ? {
          confirmText: 'Open Voice Settings',
          cancelText: 'Cancel',
          onConfirm: () => {
            this.handleShowVoiceSettings();
          }
        }
      : {
          confirmText: 'Open Voice Settings',
          cancelText: 'Cancel',
          onConfirm: () => {
            this.handleShowVoiceSettings();
          }
        };

    this.modalManager.showWarningModal(title, message, options);
  }

  async handleShowVoiceSettings() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('access voice settings');
      if (!canProceed) return;
    }

    // Show settings and navigate directly to Voice profiles tab
    this.settingsManager.showSettings();

    // Switch to Voice profiles tab after settings are shown
    setTimeout(() => {
      const voiceTab = document.querySelector('.settings-tab[data-tab="voice-profiles"]');
      if (voiceTab) {
        voiceTab.click();
      }
    }, 100);
  }

  showLLMConnectionFailedModal(errorData) {


    const llmProfile = errorData.llm_profile || 'unknown';
    const errorMessage = errorData.message || 'Cannot connect to LLM API';

    const title = 'LLM Connection Failed';
    const message = `${errorMessage}\n\nThe LLM profile "${llmProfile}" cannot be reached. Please check your LLM configuration and API credentials.`;

    const options = {
      confirmText: 'Update LLM Profile',
      cancelText: 'Cancel',
      onConfirm: () => {
        // Navigate to the specific LLM profile edit page
        this.handleShowLLMProfileSettings(llmProfile);
      }
    };


    this.modalManager.showWarningModal(title, message, options);
  }

  async handleShowLLMProfileSettings(profileName) {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('access settings');
      if (!canProceed) return;
    }

    // Show settings and navigate to the specific LLM profile
    this.settingsManager.showSettings();

    // Navigate to LLM profiles section and edit the specific profile
    // We'll add a method to settings manager to handle this
    if (this.settingsManager.navigateToLLMProfile) {
      this.settingsManager.navigateToLLMProfile(profileName);
    }
  }

  // Loading and notifications
  showLoading(message = 'Loading...') {
    this.state.isLoading = true;

    if (this.elements.loadingOverlay) {
      const textElement = this.elements.loadingOverlay.querySelector('.loading-text');
      if (textElement) {
        textElement.textContent = message;
      }
      this.elements.loadingOverlay.classList.remove('hidden');
    }
  }

  hideLoading() {
    this.state.isLoading = false;

    if (this.elements.loadingOverlay) {
      this.elements.loadingOverlay.classList.add('hidden');
    }
  }

  showNotification(message, type = 'info') {
    // Map UI notification types to valid Chrome notification types
    if(type === "error") {
      const validTypes = {
        'info': 'basic',
        'success': 'basic',
        'warning': 'basic',
        'error': 'basic',
        'basic': 'basic',
        'image': 'image',
        'list': 'list',
        'progress': 'progress'
      };

      const chromeType = validTypes[type] || 'basic';

      // Send notification to background script for display
      chrome.runtime.sendMessage({
        type: 'SHOW_NOTIFICATION',
        data: {
          title: 'VibeSurf',
          message,
          type: chromeType
        }
      });
    }
  }

  // Restore LLM profile selection from user settings storage
  async restoreLlmProfileSelection() {
    try {
      if (this.userSettingsStorage && this.elements.llmProfileSelect) {
        // Check current options available
        const availableOptions = Array.from(this.elements.llmProfileSelect.options).map(opt => opt.value);

        const savedLlmProfile = await this.userSettingsStorage.getSelectedLlmProfile();

        if (savedLlmProfile && savedLlmProfile.trim() !== '') {
          // Check if the saved profile exists in the current options
          const option = this.elements.llmProfileSelect.querySelector(`option[value="${savedLlmProfile}"]`);

          if (option) {
            this.elements.llmProfileSelect.value = savedLlmProfile;
          } else {
            console.warn('[UIManager] Saved LLM profile not found in current options:', savedLlmProfile);
          }
        } else {
          // Check localStorage backup for browser restart scenarios
          const backupProfile = localStorage.getItem('vibesurf-llm-profile-backup');

          if (backupProfile) {
            const option = this.elements.llmProfileSelect.querySelector(`option[value="${backupProfile}"]`);
            if (option) {
              this.elements.llmProfileSelect.value = backupProfile;
              // Also save it back to Chrome storage
              await this.userSettingsStorage.setSelectedLlmProfile(backupProfile);
            } else {
              console.warn('[UIManager] Backup profile not found in current options:', backupProfile);
            }
          }
        }
      } else {
        console.warn('[UIManager] Required components not available - userSettingsStorage:', !!this.userSettingsStorage, 'llmProfileSelect:', !!this.elements.llmProfileSelect);
      }
    } catch (error) {
      console.error('[UIManager] Failed to restore LLM profile selection:', error);
    }
  }

  // Check and update voice button state based on ASR profile availability
  async updateVoiceButtonState() {
    if (!this.elements.voiceRecordBtn) return;

    try {
      const isVoiceAvailable = await this.voiceRecorder.isVoiceRecordingAvailable();

      if (!isVoiceAvailable) {
        // Add visual indication but keep button enabled for click handling
        this.elements.voiceRecordBtn.classList.add('voice-disabled');
        this.elements.voiceRecordBtn.setAttribute('title', 'Voice input disabled - No ASR profiles configured. Click to configure.');
        this.elements.voiceRecordBtn.setAttribute('data-tooltip', 'Voice input disabled - No ASR profiles configured. Click to configure.');
      } else {
        // Remove visual indication and restore normal tooltip
        this.elements.voiceRecordBtn.classList.remove('voice-disabled');
        if (!this.elements.voiceRecordBtn.classList.contains('recording')) {
          this.elements.voiceRecordBtn.setAttribute('title', 'Click to start voice recording');
          this.elements.voiceRecordBtn.setAttribute('data-tooltip', 'Click to start voice recording');
        }
      }
    } catch (error) {
      console.error('[UIManager] Error updating voice button state:', error);
      // Fallback: add visual indication but keep button enabled
      this.elements.voiceRecordBtn.classList.add('voice-disabled');
      this.elements.voiceRecordBtn.setAttribute('title', 'Voice input temporarily unavailable. Click for more info.');
      this.elements.voiceRecordBtn.setAttribute('data-tooltip', 'Voice input temporarily unavailable. Click for more info.');
    }
  }

  // Initialization
  async initialize() {
    try {
      // Check for microphone permission parameter first (like Doubao AI)
      const urlParams = new URLSearchParams(window.location.search);
      const enterParam = urlParams.get('enter');

      if (enterParam === 'mic-permission') {
        console.log('[UIManager] Detected microphone permission request parameter');
        this.showMicrophonePermissionRequest();
        return; // Skip normal initialization for permission request
      }

      this.showLoading('Initializing VibeSurf...');

      // Initialize user settings storage first
      if (this.userSettingsStorage) {

        await this.userSettingsStorage.initialize();

      } else {
        console.error('[UIManager] userSettingsStorage not available during initialization');
      }

      // Load settings data through settings manager

      await this.settingsManager.loadSettingsData();


      // Now restore user selections AFTER profiles are loaded but before any other initialization

      this.isRestoringSelections = true;

      try {
        // Restore LLM profile selection first
        await this.restoreLlmProfileSelection();

        // Restore agent mode selection
        await this.restoreAgentModeSelection();
      } finally {
        this.isRestoringSelections = false;
      }

      // Check and update voice button state based on ASR profile availability
      await this.updateVoiceButtonState();

      // Check version and show upgrade button if needed
      await this.checkVersionAndShowUpgrade();

      // Create initial session if none exists

      if (!this.sessionManager.getCurrentSession()) {

        await this.sessionManager.createSession();
      }

      this.hideLoading();

    } catch (error) {
      this.hideLoading();
      console.error('[UIManager] Initialization failed:', error);
      this.showNotification(`Initialization failed: ${error.message}`, 'error');
    }
  }

  // Show microphone permission request (like Doubao AI) - simplified approach
  showMicrophonePermissionRequest() {
    console.log('[UIManager] Showing simplified microphone permission request');
    console.log('[UIManager] Current URL:', window.location.href);
    console.log('[UIManager] URL params:', window.location.search);

    // Simple approach: just try to get permission directly
    this.requestMicrophonePermissionDirectly();
  }

  // Direct microphone permission request (simplified like Doubao AI)
  async requestMicrophonePermissionDirectly() {
    console.log('[UIManager] Requesting microphone permission directly');

    try {
      // Immediately try to get microphone permission
      console.log('[UIManager] Calling getUserMedia...');
      console.log('[UIManager] User agent:', navigator.userAgent);
      console.log('[UIManager] Location protocol:', window.location.protocol);
      console.log('[UIManager] Location href:', window.location.href);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false
      });

      console.log('[UIManager] Microphone permission granted!');

      // Stop the stream immediately (we just need permission)
      stream.getTracks().forEach(track => track.stop());

      // Send success message back to original tab
      console.log('[UIManager] Sending success message...');
      chrome.runtime.sendMessage({
        type: 'MICROPHONE_PERMISSION_RESULT',
        granted: true
      }, (response) => {
        console.log('[UIManager] Success message response:', response);
      });

      // Close this tab after a short delay
      setTimeout(() => {
        console.log('[UIManager] Closing tab...');
        window.close();
      }, 1000);

    } catch (error) {
      console.error('[UIManager] Microphone permission denied:', error);
      console.log('[UIManager] Error name:', error.name);
      console.log('[UIManager] Error message:', error.message);
      console.log('[UIManager] Error stack:', error.stack);

      // Send error message back to original tab
      console.log('[UIManager] Sending error message...');
      chrome.runtime.sendMessage({
        type: 'MICROPHONE_PERMISSION_RESULT',
        granted: false,
        error: error.message,
        errorName: error.name
      }, (response) => {
        console.log('[UIManager] Error message response:', response);
      });

      // Close this tab after a short delay
      setTimeout(() => {
        console.log('[UIManager] Closing tab after error...');
        window.close();
      }, 2000);
    }
  }
  // Restore agent mode selection from user settings storage
  async restoreAgentModeSelection() {
    try {

      if (this.userSettingsStorage && this.elements.agentModeSelect) {
        // Check current options available
        const availableOptions = Array.from(this.elements.agentModeSelect.options).map(opt => opt.value);

        const savedAgentMode = await this.userSettingsStorage.getSelectedAgentMode();

        if (savedAgentMode && savedAgentMode.trim() !== '') {
          // Restore any saved agent mode, including 'thinking'
          this.elements.agentModeSelect.value = savedAgentMode;
          // Ensure the option is actually selected
          const option = this.elements.agentModeSelect.querySelector(`option[value="${savedAgentMode}"]`);
          if (option) {
            option.selected = true;
            console.log('[UIManager] Restored agent mode selection:', savedAgentMode);
          } else {
            console.warn('[UIManager] Agent mode option not found:', savedAgentMode);
          }
        } else {
          // Check localStorage backup for browser restart scenarios
          const backupMode = localStorage.getItem('vibesurf-agent-mode-backup');

          if (backupMode) {
            const option = this.elements.agentModeSelect.querySelector(`option[value="${backupMode}"]`);
            if (option) {
              this.elements.agentModeSelect.value = backupMode;
              // Also save it back to Chrome storage
              await this.userSettingsStorage.setSelectedAgentMode(backupMode);
            } else {
              console.warn('[UIManager] Backup agent mode not found in current options:', backupMode);
            }
          }
        }
      } else {
        console.warn('[UIManager] Required components not available - userSettingsStorage:', !!this.userSettingsStorage, 'agentModeSelect:', !!this.elements.agentModeSelect);
      }
    } catch (error) {
      console.error('[UIManager] Failed to restore agent mode selection:', error);
    }
  }

  // Version checking and upgrade button management
  async checkVersionAndShowUpgrade() {
    try {
      console.log('[UIManager] Checking version for upgrade notification...');
      
      // Get extension version from version.js
      const extensionVersion = window.VIBESURF_EXTENSION_VERSION;
      if (!extensionVersion) {
        console.warn('[UIManager] Extension version not found');
        return;
      }
      
      console.log('[UIManager] Extension version:', extensionVersion);
      
      // Get VibeSurf backend version from API
      const versionResponse = await this.apiClient.getVibeSurfVersion();
      const backendVersion = versionResponse.version;
      
      if (!backendVersion) {
        console.warn('[UIManager] Backend version not found');
        return;
      }
      
      console.log('[UIManager] Backend version:', backendVersion);
      
      // Compare versions - show upgrade if extension version is different from backend
      const shouldShowUpgrade = this.compareVersions(extensionVersion, backendVersion);
      
      if (shouldShowUpgrade) {
        console.log('[UIManager] Extension version mismatch detected, showing upgrade button');
        this.showUpgradeButton();
      } else {
        console.log('[UIManager] Extension version is up to date');
        this.hideUpgradeButton();
      }
      
    } catch (error) {
      console.error('[UIManager] Failed to check version:', error);
      // Don't show upgrade button on error to avoid false positives
    }
  }
  
  // Compare versions - returns true if extension needs upgrade
  compareVersions(extensionVersion, backendVersion) {
    // Remove any +dev suffix from extension version for comparison
    const cleanExtensionVersion = extensionVersion.replace(/\+.*$/, '');
    const cleanBackendVersion = backendVersion.replace(/\+.*$/, '');
    
    console.log('[UIManager] Comparing versions:', cleanExtensionVersion, 'vs', cleanBackendVersion);
    
    // Simple string comparison - if they're different, show upgrade
    // This handles cases where extension is older, newer, or just different
    return cleanExtensionVersion !== cleanBackendVersion;
  }
  
  // Show upgrade button with animation
  showUpgradeButton() {
    if (this.elements.upgradeBtn) {
      this.elements.upgradeBtn.classList.remove('hidden');
      console.log('[UIManager] Upgrade button shown');
    }
  }
  
  // Hide upgrade button
  hideUpgradeButton() {
    if (this.elements.upgradeBtn) {
      this.elements.upgradeBtn.classList.add('hidden');
      console.log('[UIManager] Upgrade button hidden');
    }
  }

  // Cleanup
  destroy() {
    // Prevent multiple cleanup calls
    if (this.isDestroying) {
      console.log('[UIManager] Cleanup already in progress, skipping...');
      return;
    }

    this.isDestroying = true;
    console.log('[UIManager] Destroying UI manager...');

    try {
      // Stop task status monitoring
      this.stopTaskStatusMonitoring();

      // Cleanup voice recorder
      if (this.voiceRecorder) {
        this.voiceRecorder.cleanup();
        this.voiceRecorder = null;
      }

      // Cleanup managers with error handling
      if (this.settingsManager) {
        try {
          if (typeof this.settingsManager.destroy === 'function') {
            this.settingsManager.destroy();
          }
        } catch (error) {
          console.error('[UIManager] Error destroying settings manager:', error);
        }
        this.settingsManager = null;
      }

      if (this.historyManager) {
        try {
          if (typeof this.historyManager.destroy === 'function') {
            this.historyManager.destroy();
          }
        } catch (error) {
          console.error('[UIManager] Error destroying history manager:', error);
        }
        this.historyManager = null;
      }

      if (this.fileManager) {
        try {
          if (typeof this.fileManager.destroy === 'function') {
            this.fileManager.destroy();
          }
        } catch (error) {
          console.error('[UIManager] Error destroying file manager:', error);
        }
        this.fileManager = null;
      }

      if (this.modalManager) {
        try {
          if (typeof this.modalManager.destroy === 'function') {
            this.modalManager.destroy();
          }
        } catch (error) {
          console.error('[UIManager] Error destroying modal manager:', error);
        }
        this.modalManager = null;
      }

      // Clear state
      this.state = {
        isLoading: false,
        isTaskRunning: false,
        taskInfo: null
      };

      console.log('[UIManager] UI manager cleanup complete');
    } catch (error) {
      console.error('[UIManager] Error during destroy:', error);
    } finally {
      this.isDestroying = false;
    }
  }

  // Tab Selector Methods
  initializeTabSelector() {


    // Initialize tab selector state
    this.tabSelectorState = {
      isVisible: false,
      selectedTabs: [],
      allTabs: [],
      atPosition: -1 // Position where @ was typed
    };



    // Bind tab selector events
    this.bindTabSelectorEvents();
  }

  bindTabSelectorEvents() {



    // Select all radio button
    this.elements.selectAllTabs?.addEventListener('change', this.handleSelectAllTabs.bind(this));

    // Hide on click outside
    document.addEventListener('click', (event) => {
      if (this.tabSelectorState.isVisible &&
          this.elements.tabSelectorDropdown &&
          !this.elements.tabSelectorDropdown.contains(event.target) &&
          !this.elements.taskInput?.contains(event.target)) {
        this.hideTabSelector();
      }
    });


  }

  handleTabSelectorInput(event) {
    // Safety check - ensure tab selector state is initialized
    if (!this.tabSelectorState) {
      console.warn('[UIManager] Tab selector state not initialized');
      return;
    }

    const inputValue = event.target.value;
    const cursorPosition = event.target.selectionStart;



    // Check if @ was just typed
    if (inputValue[cursorPosition - 1] === '@') {

      this.tabSelectorState.atPosition = cursorPosition - 1;
      this.showTabSelector();
    } else if (this.tabSelectorState.isVisible) {
      // Check if @ was deleted - hide tab selector immediately
      if (this.tabSelectorState.atPosition >= 0 &&
          (this.tabSelectorState.atPosition >= inputValue.length ||
           inputValue[this.tabSelectorState.atPosition] !== '@')) {

        this.hideTabSelector();
        return;
      }

      // Hide tab selector if user continues typing after @
      const textAfterAt = inputValue.substring(this.tabSelectorState.atPosition + 1, cursorPosition);
      if (textAfterAt.length > 0 && !textAfterAt.match(/^[\s]*$/)) {

        this.hideTabSelector();
      }
    }
  }

  async showTabSelector() {



    if (!this.elements.tabSelectorDropdown || !this.elements.taskInput) {
      console.error('[UIManager] Tab selector elements not found', {
        dropdown: this.elements.tabSelectorDropdown,
        taskInput: this.elements.taskInput
      });
      return;
    }

    try {

      // Fetch tab data from backend
      await this.populateTabSelector();


      // Position the dropdown relative to the input
      this.positionTabSelector();


      // Show the dropdown with explicit visibility
      this.elements.tabSelectorDropdown.classList.remove('hidden');
      this.elements.tabSelectorDropdown.style.display = 'block';
      this.elements.tabSelectorDropdown.style.visibility = 'visible';
      this.elements.tabSelectorDropdown.style.opacity = '1';
      this.tabSelectorState.isVisible = true;





    } catch (error) {
      console.error('[UIManager] Failed to show tab selector:', error);
      this.showNotification('Failed to load browser tabs', 'error');
    }
  }

  hideTabSelector() {
    if (this.elements.tabSelectorDropdown) {
      this.elements.tabSelectorDropdown.classList.add('hidden');
      this.elements.tabSelectorDropdown.style.display = 'none'; // Ensure it's hidden
    }
    this.tabSelectorState.isVisible = false;
    this.tabSelectorState.selectedTabs = [];
    this.tabSelectorState.atPosition = -1;


  }

  positionTabSelector() {
    if (!this.elements.tabSelectorDropdown || !this.elements.taskInput) return;

    const inputRect = this.elements.taskInput.getBoundingClientRect();
    const dropdown = this.elements.tabSelectorDropdown;



    // Calculate 90% width of input
    const dropdownWidth = inputRect.width * 0.9;

    // Position dropdown ABOVE the input (not below)
    dropdown.style.position = 'fixed';
    dropdown.style.bottom = `${window.innerHeight - inputRect.top + 5}px`; // Above the input
    dropdown.style.left = `${inputRect.left + (inputRect.width - dropdownWidth) / 2}px`; // Centered
    dropdown.style.width = `${dropdownWidth}px`; // 80% of input width
    dropdown.style.zIndex = '9999';
    dropdown.style.maxHeight = '300px';
    dropdown.style.overflowY = 'auto';


  }

  async populateTabSelector() {
    try {

      // Get all tabs and active tab from backend
      const [allTabsResponse, activeTabResponse] = await Promise.all([
        this.apiClient.getAllBrowserTabs(),
        this.apiClient.getActiveBrowserTab()
      ]);



      const allTabs = allTabsResponse.tabs || allTabsResponse || {};
      const activeTab = activeTabResponse.tab || activeTabResponse || {};
      const activeTabId = Object.keys(activeTab)[0];



      this.tabSelectorState.allTabs = allTabs;

      // Clear existing options
      if (this.elements.tabOptionsList) {
        this.elements.tabOptionsList.innerHTML = '';

      } else {
        console.error('[UIManager] tabOptionsList element not found!');
        return;
      }

      // Add fallback test data if no tabs returned
      if (Object.keys(allTabs).length === 0) {
        console.warn('[UIManager] No tabs returned from API, adding test data for debugging');
        const testTabs = {
          'test-1': { title: 'Test Tab 1', url: 'https://example.com' },
          'test-2': { title: 'Test Tab 2', url: 'https://google.com' },
          'test-3': { title: 'Very Long Tab Title That Should Be Truncated', url: 'https://github.com' }
        };

        Object.entries(testTabs).forEach(([tabId, tabInfo]) => {
          const isActive = tabId === 'test-1';

          const option = this.createTabOption(tabId, tabInfo, isActive);
          this.elements.tabOptionsList.appendChild(option);
        });

        this.tabSelectorState.allTabs = testTabs;
      } else {
        // Add real tab options
        Object.entries(allTabs).forEach(([tabId, tabInfo]) => {
          const isActive = tabId === activeTabId;

          const option = this.createTabOption(tabId, tabInfo, isActive);
          this.elements.tabOptionsList.appendChild(option);
        });
      }

      // Reset select all checkbox
      if (this.elements.selectAllTabs) {
        this.elements.selectAllTabs.checked = false;
      }


    } catch (error) {
      console.error('[UIManager] Failed to populate tab selector:', error);
      throw error;
    }
  }

  createTabOption(tabId, tabInfo, isActive) {
    const option = document.createElement('div');
    option.className = `tab-option ${isActive ? 'active-tab' : ''}`;
    option.dataset.tabId = tabId;

    // Format title (first 20 characters)
    const displayTitle = tabInfo.title ?
      (tabInfo.title.length > 20 ? tabInfo.title.substring(0, 20) + '...' : tabInfo.title) :
      'Unknown Title';

    option.innerHTML = `
      <input type="radio" class="tab-radio" id="tab-${tabId}" name="tab-selection" value="${tabId}">
      <label for="tab-${tabId}" class="tab-label">
        <span class="tab-id">${tabId}:</span>
        <span class="tab-title">${this.escapeHtml(displayTitle)}</span>
        ${isActive ? '<span class="active-indicator">(Active)</span>' : ''}
      </label>
    `;

    // Add change event to radio button for auto-confirm
    const radio = option.querySelector('.tab-radio');
    radio?.addEventListener('change', this.handleTabSelection.bind(this));

    return option;
  }

  handleTabSelection(event) {
    const tabId = event.target.value;

    if (event.target.checked) {
      // For radio buttons, replace the selected tabs array with just this tab
      this.tabSelectorState.selectedTabs = [tabId];



      // Auto-confirm selection immediately
      this.confirmTabSelection();
    }
  }

  handleSelectAllTabs(event) {
    if (event.target.checked) {
      // "Select All" means list all tabs in the input
      const allTabIds = Object.keys(this.tabSelectorState.allTabs);
      this.tabSelectorState.selectedTabs = allTabIds;



      // Auto-confirm selection immediately
      this.confirmTabSelection();
    }
  }

  updateSelectAllState() {
    if (!this.elements.selectAllTabs || !this.elements.tabOptionsList) return;

    const checkboxes = this.elements.tabOptionsList.querySelectorAll('.tab-checkbox');
    const checkedBoxes = this.elements.tabOptionsList.querySelectorAll('.tab-checkbox:checked');

    if (checkboxes.length === 0) {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = false;
    } else if (checkedBoxes.length === checkboxes.length) {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = true;
    } else if (checkedBoxes.length > 0) {
      this.elements.selectAllTabs.indeterminate = true;
      this.elements.selectAllTabs.checked = false;
    } else {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = false;
    }
  }

  confirmTabSelection() {
    if (this.tabSelectorState.selectedTabs.length === 0) {
      this.showNotification('Please select at least one tab', 'warning');
      return;
    }

    // Replace @ with selected tabs information
    this.insertSelectedTabsIntoInput();

    // Hide the selector
    this.hideTabSelector();

    console.log(`[UIManager] ${this.tabSelectorState.selectedTabs.length} tab(s) selected and confirmed`);
  }

  insertSelectedTabsIntoInput() {
    if (!this.elements.taskInput) return;

    const input = this.elements.taskInput;
    const currentValue = input.value;
    const atPosition = this.tabSelectorState.atPosition;

    // Use special Unicode characters as boundaries for easy deletion
    const TAB_START_MARKER = '\u200B'; // Zero-width space
    const TAB_END_MARKER = '\u200C'; // Zero-width non-joiner

    // Create tab information string in new format: @ tab_id: title[:20]
    const selectedTabsInfo = this.tabSelectorState.selectedTabs.map(tabId => {
      const tabInfo = this.tabSelectorState.allTabs[tabId];
      const displayTitle = tabInfo?.title ?
        (tabInfo.title.length > 20 ? tabInfo.title.substring(0, 20) + '...' : tabInfo.title) :
        'Unknown';
      return `${TAB_START_MARKER}@ ${tabId}: ${displayTitle}${TAB_END_MARKER}`;
    }).join(' ');

    // Replace @ with tab selection (preserve the @ symbol)
    const beforeAt = currentValue.substring(0, atPosition);
    const afterAt = currentValue.substring(atPosition + 1);
    const newValue = `${beforeAt}${selectedTabsInfo} ${afterAt}`;

    input.value = newValue;

    // Trigger input change event for validation
    this.handleTaskInputChange({ target: input });

    // Set cursor position after the inserted text
    const newCursorPosition = beforeAt.length + selectedTabsInfo.length + 1; // Add space
    input.setSelectionRange(newCursorPosition, newCursorPosition);
    input.focus();
  }

  getSelectedTabsForTask() {
    // Return selected tabs information for task submission
    if (this.tabSelectorState.selectedTabs.length === 0) {
      return null;
    }

    const selectedTabsData = {};
    this.tabSelectorState.selectedTabs.forEach(tabId => {
      const tabInfo = this.tabSelectorState.allTabs[tabId];
      if (tabInfo) {
        selectedTabsData[tabId] = {
          url: tabInfo.url,
          title: tabInfo.title
        };
      }
    });

    return selectedTabsData;
  }

  // Skill Selector Methods
  initializeSkillSelector() {
    // Initialize skill selector state
    this.skillSelectorState = {
      isVisible: false,
      selectedSkills: [],
      allSkills: [],
      slashPosition: -1, // Position where / was typed
      currentFilter: '', // Current filter text after /
      filteredSkills: [] // Filtered skills based on current input
    };

    // Bind skill selector events
    this.bindSkillSelectorEvents();
  }

  bindSkillSelectorEvents() {
    // Hide on click outside
    document.addEventListener('click', (event) => {
      if (this.skillSelectorState.isVisible &&
          this.elements.skillSelectorDropdown &&
          !this.elements.skillSelectorDropdown.contains(event.target) &&
          !this.elements.taskInput?.contains(event.target)) {
        this.hideSkillSelector();
      }
    });
  }

  handleSkillSelectorInput(event) {
    // Safety check - ensure skill selector state is initialized
    if (!this.skillSelectorState) {
      console.warn('[UIManager] Skill selector state not initialized');
      return;
    }

    const inputValue = event.target.value;
    const cursorPosition = event.target.selectionStart;

    // Check if / was just typed
    if (inputValue[cursorPosition - 1] === '/') {
      this.skillSelectorState.slashPosition = cursorPosition - 1;
      this.skillSelectorState.currentFilter = '';
      this.showSkillSelector();
    } else if (this.skillSelectorState.isVisible) {
      // Check if / was deleted - hide skill selector immediately
      if (this.skillSelectorState.slashPosition >= 0 &&
          (this.skillSelectorState.slashPosition >= inputValue.length ||
           inputValue[this.skillSelectorState.slashPosition] !== '/')) {
        this.hideSkillSelector();
        return;
      }

      // Update filter based on text after /
      const textAfterSlash = inputValue.substring(this.skillSelectorState.slashPosition + 1, cursorPosition);

      // Only consider text up to the next space or special character
      const filterText = textAfterSlash.split(/[\s@]/)[0];

      if (this.skillSelectorState.currentFilter !== filterText) {
        this.skillSelectorState.currentFilter = filterText;
        this.filterSkills();
      }

      // Hide skill selector if user typed a space or moved past the skill context
      if (textAfterSlash.includes(' ') || textAfterSlash.includes('@')) {
        this.hideSkillSelector();
      }
    }
  }

  async showSkillSelector() {
    if (!this.elements.skillSelectorDropdown || !this.elements.taskInput) {
      console.error('[UIManager] Skill selector elements not found', {
        dropdown: this.elements.skillSelectorDropdown,
        taskInput: this.elements.taskInput
      });
      return;
    }

    try {
      // Fetch skill data from backend if not already cached
      if (this.skillSelectorState.allSkills.length === 0) {
        await this.populateSkillSelector();
      }

      // Filter skills based on current input
      this.filterSkills();

      // Position the dropdown relative to the input
      this.positionSkillSelector();

      // Show the dropdown with explicit visibility
      this.elements.skillSelectorDropdown.classList.remove('hidden');
      this.elements.skillSelectorDropdown.style.display = 'block';
      this.elements.skillSelectorDropdown.style.visibility = 'visible';
      this.elements.skillSelectorDropdown.style.opacity = '1';
      this.skillSelectorState.isVisible = true;

    } catch (error) {
      console.error('[UIManager] Failed to show skill selector:', error);
      this.showNotification('Failed to load skills', 'error');
    }
  }

  hideSkillSelector() {
    if (this.elements.skillSelectorDropdown) {
      this.elements.skillSelectorDropdown.classList.add('hidden');
      this.elements.skillSelectorDropdown.style.display = 'none';
    }
    this.skillSelectorState.isVisible = false;
    this.skillSelectorState.slashPosition = -1;
    this.skillSelectorState.currentFilter = '';
    this.skillSelectorState.filteredSkills = [];
  }

  positionSkillSelector() {
    if (!this.elements.skillSelectorDropdown || !this.elements.taskInput) return;

    const inputRect = this.elements.taskInput.getBoundingClientRect();
    const dropdown = this.elements.skillSelectorDropdown;

    // Calculate 90% width of input
    const dropdownWidth = inputRect.width * 0.9;

    // Position dropdown ABOVE the input (not below)
    dropdown.style.position = 'fixed';
    dropdown.style.bottom = `${window.innerHeight - inputRect.top + 5}px`; // Above the input
    dropdown.style.left = `${inputRect.left + (inputRect.width - dropdownWidth) / 2}px`; // Centered
    dropdown.style.width = `${dropdownWidth}px`; // 90% of input width
    dropdown.style.zIndex = '9999';
    dropdown.style.maxHeight = '300px';
    dropdown.style.overflowY = 'auto';
  }

  async populateSkillSelector() {
    try {
      console.log('[UIManager] Fetching skills from backend...');
      // Get all skills from backend
      const skills = await this.apiClient.getAllSkills();

      console.log('[UIManager] Skills received from backend:', skills);

      if (!skills || !Array.isArray(skills) || skills.length === 0) {
        console.warn('[UIManager] No skills returned from backend');
        this.skillSelectorState.allSkills = [];
        return;
      }

      this.skillSelectorState.allSkills = skills.map(skillName => ({
        name: skillName,
        displayName: skillName // Keep original skill name without transformation
      }));
      console.log('[UIManager] Processed skills:', this.skillSelectorState.allSkills);

    } catch (error) {
      console.error('[UIManager] Failed to populate skill selector:', error);
      console.error('[UIManager] Error details:', {
        message: error.message,
        stack: error.stack,
        response: error.response,
        data: error.data
      });

      // Show error to user
      this.showNotification(`Failed to load skills: ${error.message}`, 'error');

      // Set empty array instead of fallback test data
      this.skillSelectorState.allSkills = [];
    }
  }

  filterSkills() {
    const filter = this.skillSelectorState.currentFilter.toLowerCase();

    if (!filter) {
      this.skillSelectorState.filteredSkills = this.skillSelectorState.allSkills;
    } else {
      this.skillSelectorState.filteredSkills = this.skillSelectorState.allSkills.filter(skill =>
        skill.name.toLowerCase().startsWith(filter) ||
        skill.displayName.toLowerCase().startsWith(filter)
      );
    }

    this.renderSkillOptions();
  }

  renderSkillOptions() {
    if (!this.elements.skillOptionsList) return;

    // Clear existing options
    this.elements.skillOptionsList.innerHTML = '';

    if (this.skillSelectorState.filteredSkills.length === 0) {
      const noResults = document.createElement('div');
      noResults.className = 'skill-option';
      noResults.innerHTML = '<span class="skill-name">No skills found</span>';
      noResults.style.opacity = '0.6';
      noResults.style.cursor = 'not-allowed';
      this.elements.skillOptionsList.appendChild(noResults);
      return;
    }

    // Add skill options
    this.skillSelectorState.filteredSkills.forEach((skill, index) => {
      const option = this.createSkillOption(skill, index);
      this.elements.skillOptionsList.appendChild(option);
    });
  }

  createSkillOption(skill, index) {
    const option = document.createElement('div');
    option.className = 'skill-option';
    option.dataset.skillName = skill.name;
    option.dataset.skillIndex = index;

    option.innerHTML = `
      <span class="skill-name">${this.escapeHtml(skill.displayName)}</span>
    `;

    // Add click event for skill selection
    option.addEventListener('click', () => {
      this.selectSkill(skill);
    });

    return option;
  }

  selectSkill(skill) {
    if (!this.elements.taskInput) return;

    const input = this.elements.taskInput;
    const currentValue = input.value;
    const slashPosition = this.skillSelectorState.slashPosition;

    // Use special Unicode characters as boundaries for easy deletion
    const SKILL_START_MARKER = '\u200D'; // Zero-width joiner
    const SKILL_END_MARKER = '\u200E';   // Left-to-right mark

    // Create skill information string
    const skillInfo = `${SKILL_START_MARKER}/${skill.name}${SKILL_END_MARKER}`;

    // Replace / with skill selection
    const beforeSlash = currentValue.substring(0, slashPosition);
    const afterSlash = currentValue.substring(slashPosition + 1 + this.skillSelectorState.currentFilter.length);
    const newValue = `${beforeSlash}${skillInfo} ${afterSlash}`;

    input.value = newValue;

    // Trigger input change event for validation
    this.handleTaskInputChange({ target: input });

    // Set cursor position after the inserted text
    const newCursorPosition = beforeSlash.length + skillInfo.length + 1;
    input.setSelectionRange(newCursorPosition, newCursorPosition);
    input.focus();

    // Hide the selector
    this.hideSkillSelector();
  }

  getSelectedSkillsForTask() {
    if (!this.elements.taskInput) return null;

    const inputValue = this.elements.taskInput.value;
    const SKILL_START_MARKER = '\u200D'; // Zero-width joiner
    const SKILL_END_MARKER = '\u200E';   // Left-to-right mark

    const skills = [];
    let startIndex = 0;

    while ((startIndex = inputValue.indexOf(SKILL_START_MARKER, startIndex)) !== -1) {
      const endIndex = inputValue.indexOf(SKILL_END_MARKER, startIndex);
      if (endIndex !== -1) {
        const skillText = inputValue.substring(startIndex + 1, endIndex);
        if (skillText.startsWith('/')) {
          skills.push(skillText.substring(1)); // Remove the / prefix
        }
        startIndex = endIndex + 1;
      } else {
        break;
      }
    }

    return skills.length > 0 ? skills : null;
  }

  // Initialize social links from config
  initializeSocialLinks() {
    const socialLinksContainer = document.getElementById('social-links-container');
    if (!socialLinksContainer) {
      console.warn('[UIManager] Social links container not found');
      return;
    }

    // Get social links from config
    const socialLinks = window.VIBESURF_CONFIG?.SOCIAL_LINKS;
    if (!socialLinks) {
      console.warn('[UIManager] Social links not found in config');
      return;
    }

    // Clear existing content
    socialLinksContainer.innerHTML = '';

    // Handle website link separately by making VibeSurf logo/text clickable
    const websiteUrl = socialLinks.website;
    if (websiteUrl) {
      this.initializeVibeSurfWebsiteLink(websiteUrl);
    }

    // Create social link elements (excluding website)
    Object.entries(socialLinks).forEach(([platform, url]) => {
      if (platform !== 'website') {
        const link = this.createSocialLink(platform, url);
        if (link) {
          socialLinksContainer.appendChild(link);
        }
      }
    });
  }

  // Make VibeSurf text clickable to link to website
  initializeVibeSurfWebsiteLink(websiteUrl) {
    // Only find elements that contain "VibeSurf" text specifically
    const allElements = document.querySelectorAll('*');
    const vibeSurfTextElements = [];
    
    allElements.forEach(element => {
      // Only target elements that contain "VibeSurf" text and are likely text elements
      if (element.textContent &&
          element.textContent.trim() === 'VibeSurf' &&
          element.children.length === 0) { // Only leaf text nodes, not containers
        vibeSurfTextElements.push(element);
      }
    });
    
    // Make only VibeSurf text elements clickable
    vibeSurfTextElements.forEach(element => {
      if (element && !element.querySelector('a')) { // Don't double-wrap already linked elements
        element.style.cursor = 'pointer';
        element.style.transition = 'opacity 0.2s ease';
        element.setAttribute('title', 'Login to early access alpha features');
        
        // Add hover effect
        element.addEventListener('mouseenter', () => {
          element.style.opacity = '0.8';
        });
        
        element.addEventListener('mouseleave', () => {
          element.style.opacity = '1';
        });
        
        // Add click handler
        element.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.openWebsiteLink(websiteUrl);
        });
      }
    });
  }

  // Open website link in new tab
  async openWebsiteLink(url) {
    try {
      console.log('[UIManager] Opening VibeSurf website:', url);
      
      const result = await chrome.runtime.sendMessage({
        type: 'OPEN_FILE_URL',
        data: { fileUrl: url }
      });
      
      if (!result || !result.success) {
        throw new Error(result?.error || 'Failed to open website');
      }
      
      console.log('[UIManager] Successfully opened website tab:', result.tabId);
    } catch (error) {
      console.error('[UIManager] Error opening website:', error);
      this.showNotification(`Failed to open website: ${error.message}`, 'error');
    }
  }

  // Create individual social link element
  createSocialLink(platform, url) {
    const link = document.createElement('a');
    link.href = url;
    link.className = 'social-link';
    link.setAttribute('data-platform', platform);
    link.setAttribute('target', '_blank');
    link.setAttribute('rel', 'noopener noreferrer');

    // Set title and tooltip based on platform
    let title = '';
    let svg = '';

    switch (platform.toLowerCase()) {
      case 'github':
        title = 'GitHub';
        svg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" fill="currentColor"/>
        </svg>`;
        break;
      
      case 'discord':
        title = 'Discord';
        svg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" fill="currentColor"/>
        </svg>`;
        break;
      
      case 'x':
      case 'twitter':
        title = 'X (Twitter)';
        svg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" fill="currentColor"/>
        </svg>`;
        break;
      
      
      case 'reportbug':
        title = 'Report Bug';
        svg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5c-.49 0-.96.06-1.42.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z" fill="currentColor"/>
        </svg>`;
        break;
      
      default:
        console.warn(`[UIManager] Unknown social platform: ${platform}`);
        return null;
    }

    link.setAttribute('title', title);
    link.innerHTML = svg;

    return link;
  }

  // Export for use in other modules
  static exportToWindow() {
    if (typeof window !== 'undefined') {
      window.VibeSurfUIManager = VibeSurfUIManager;
    }
  }
}

// Call the export method
VibeSurfUIManager.exportToWindow();