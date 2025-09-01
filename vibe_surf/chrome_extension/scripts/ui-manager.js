// UI Manager - Handles all user interface interactions and state updates
// Manages DOM manipulation, form handling, modal displays, and UI state

class VibeSurfUIManager {
  constructor(sessionManager, apiClient) {
    this.sessionManager = sessionManager;
    this.apiClient = apiClient;
    this.elements = {};
    this.state = {
      isLoading: false,
      currentModal: null,
      llmProfiles: [],
      mcpProfiles: [],
      settings: {},
      isTaskRunning: false,
      taskInfo: null,
      // File upload state
      uploadedFiles: [],
      // History-related state
      historyMode: 'recent', // 'recent' or 'all'
      currentPage: 1,
      totalPages: 1,
      pageSize: 10,
      searchQuery: '',
      statusFilter: 'all',
      recentTasks: [],
      allSessions: []
    };
    
    this.bindElements();
    this.bindEvents();
    this.setupSessionListeners();
    this.setupHistoryModalHandlers();
    
  }

  bindElements() {
    // Main UI elements
    this.elements = {
      // Header elements
      newSessionBtn: document.getElementById('new-session-btn'),
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
      taskInput: document.getElementById('task-input'),
      attachFileBtn: document.getElementById('attach-file-btn'),
      sendBtn: document.getElementById('send-btn'),
      fileInput: document.getElementById('file-input'),
      
      // Modals
      historyModal: document.getElementById('history-modal'),
      settingsModal: document.getElementById('settings-modal'),
      
      // History Modal Elements
      recentTasksList: document.getElementById('recent-tasks-list'),
      viewMoreTasksBtn: document.getElementById('view-more-tasks-btn'),
      allSessionsSection: document.getElementById('all-sessions-section'),
      backToRecentBtn: document.getElementById('back-to-recent-btn'),
      sessionSearch: document.getElementById('session-search'),
      sessionFilter: document.getElementById('session-filter'),
      allSessionsList: document.getElementById('all-sessions-list'),
      prevPageBtn: document.getElementById('prev-page-btn'),
      nextPageBtn: document.getElementById('next-page-btn'),
      pageInfo: document.getElementById('page-info'),
      
      // Settings - New Structure
      settingsTabs: document.querySelectorAll('.settings-tab'),
      settingsTabContents: document.querySelectorAll('.settings-tab-content'),
      llmProfilesContainer: document.getElementById('llm-profiles-container'),
      mcpProfilesContainer: document.getElementById('mcp-profiles-container'),
      addLlmProfileBtn: document.getElementById('add-llm-profile-btn'),
      addMcpProfileBtn: document.getElementById('add-mcp-profile-btn'),
      backendUrl: document.getElementById('backend-url'),
      
      // Profile Form Modal
      profileFormModal: document.getElementById('profile-form-modal'),
      profileFormTitle: document.getElementById('profile-form-title'),
      profileForm: document.getElementById('profile-form'),
      profileFormCancel: document.getElementById('profile-form-cancel'),
      profileFormSubmit: document.getElementById('profile-form-submit'),
      profileFormClose: document.querySelector('.profile-form-close'),
      
      // Environment Variables
      envVariablesList: document.getElementById('env-variables-list'),
      saveEnvVarsBtn: document.getElementById('save-env-vars-btn'),
      
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

  bindEvents() {
    // Header buttons
    this.elements.newSessionBtn?.addEventListener('click', this.handleNewSession.bind(this));
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
    this.elements.attachFileBtn?.addEventListener('click', this.handleAttachFiles.bind(this));
    this.elements.fileInput?.addEventListener('change', this.handleFileSelection.bind(this));
    
    // Task input handling
    this.elements.taskInput?.addEventListener('keydown', this.handleTaskInputKeydown.bind(this));
    this.elements.taskInput?.addEventListener('input', this.handleTaskInputChange.bind(this));
    
    // LLM profile selection handling
    this.elements.llmProfileSelect?.addEventListener('change', this.handleLlmProfileChange.bind(this));
    
    // Initialize auto-resize for textarea
    if (this.elements.taskInput) {
      this.autoResizeTextarea(this.elements.taskInput);
      // Set initial send button state
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }
    
    // Bind initial task suggestions if present
    this.bindTaskSuggestionEvents();
    
    // Settings handling
    this.elements.backendUrl?.addEventListener('change', this.handleBackendUrlChange.bind(this));
    this.elements.addLlmProfileBtn?.addEventListener('click', () => this.handleAddProfile('llm'));
    this.elements.addMcpProfileBtn?.addEventListener('click', () => this.handleAddProfile('mcp'));
    
    // Settings tabs
    this.elements.settingsTabs?.forEach(tab => {
      tab.addEventListener('click', this.handleTabSwitch.bind(this));
    });
    
    // Profile form modal
    this.elements.profileFormCancel?.addEventListener('click', this.closeProfileForm.bind(this));
    this.elements.profileFormClose?.addEventListener('click', this.closeProfileForm.bind(this));
    
    // Profile form submission - add both form submit and button click handlers
    if (this.elements.profileForm) {
      this.elements.profileForm.addEventListener('submit', this.handleProfileFormSubmit.bind(this));
      console.log('[UIManager] Profile form submit listener added');
    } else {
      console.warn('[UIManager] Profile form element not found during initialization');
    }
    
    if (this.elements.profileFormSubmit) {
      this.elements.profileFormSubmit.addEventListener('click', this.handleProfileFormSubmitClick.bind(this));
      console.log('[UIManager] Profile form submit button listener added');
    } else {
      console.warn('[UIManager] Profile form submit button not found during initialization');
    }
    
    // Environment variables
    this.elements.saveEnvVarsBtn?.addEventListener('click', this.handleSaveEnvironmentVariables.bind(this));
    
    // Modal handling
    this.bindModalEvents();
    
    // File link handling
    this.bindFileLinkEvents();
    
  }

  bindModalEvents() {
    // Close modals when clicking overlay or close button
    document.addEventListener('click', (event) => {
      if (event.target.classList.contains('modal-overlay') || 
          event.target.classList.contains('modal-close') ||
          event.target.closest('.modal-close')) {
        this.closeModal();
      }
    });
    
    // Close modals with Escape key
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.state.currentModal) {
        this.closeModal();
      }
    });
  }

  bindFileLinkEvents() {
    // Handle file:// link clicks with delegation
    document.addEventListener('click', (event) => {
      const target = event.target;
      
      // Check if clicked element is a file link
      if (target.matches('a.file-link') || target.closest('a.file-link')) {
        event.preventDefault();
        
        const fileLink = target.matches('a.file-link') ? target : target.closest('a.file-link');
        const filePath = fileLink.getAttribute('data-file-path');
        
        this.handleFileLink(filePath);
      }
    });
    
  }

  async handleFileLink(filePath) {
    // Prevent multiple simultaneous calls
    if (this._isHandlingFileLink) {
      return;
    }
    
    this._isHandlingFileLink = true;
    
    try {
      // First decode the URL-encoded path
      let decodedPath = decodeURIComponent(filePath);
      
      // Remove file:// protocol prefix and normalize
      let cleanPath = decodedPath.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
      
      // Ensure path starts with / for Unix paths if not Windows drive
      if (!cleanPath.startsWith('/') && !cleanPath.match(/^[A-Za-z]:/)) {
        cleanPath = '/' + cleanPath;
      }
      
      // Convert all backslashes to forward slashes
      cleanPath = cleanPath.replace(/\\/g, '/');
      
      // Create proper file URL - always use triple slash for proper format
      const fileUrl = cleanPath.match(/^[A-Za-z]:/) ?
        `file:///${cleanPath}` :
        `file:///${cleanPath.replace(/^\//, '')}`;  // Remove leading slash and add triple slash
      
      // Create Windows format path for system open
      const windowsPath = cleanPath.replace(/\//g, '\\');
      
      // Show user notification about the action
      this.showNotification(`Opening file: ${cleanPath}`, 'info');
      
      // Use setTimeout to prevent UI blocking
      setTimeout(async () => {
        try {
          // Primary strategy: Try browser open first for HTML files (more reliable)
          if (fileUrl.toLowerCase().endsWith('.html') || fileUrl.toLowerCase().endsWith('.htm')) {
            try {
              const opened = window.open(fileUrl, '_blank', 'noopener,noreferrer');
              if (opened) {
                this.showNotification('File opened in browser', 'success');
                return;
              } else {
                // If browser is blocked, try system open
                await this.trySystemOpen(windowsPath, fileUrl);
                return;
              }
            } catch (browserError) {
              await this.trySystemOpen(windowsPath, fileUrl);
              return;
            }
          } else {
            // For non-HTML files, try system open first
            const systemSuccess = await this.trySystemOpen(windowsPath, fileUrl);
            if (systemSuccess) return;
            
            // Fallback to browser if system open fails
            try {
              const opened = window.open(fileUrl, '_blank', 'noopener,noreferrer');
              if (opened) {
                this.showNotification('File opened in browser', 'success');
                return;
              }
            } catch (browserError) {
              console.error('[UIManager] Failed to open file:', browserError);
            }
          }
          
          // Last resort: Copy path to clipboard
          this.copyToClipboardFallback(fileUrl);
          
        } catch (error) {
          console.error('[UIManager] Error in async file handling:', error);
          this.showNotification(`Unable to open file: ${error.message}`, 'error');
        } finally {
          this._isHandlingFileLink = false;
        }
      }, 50); // Small delay to prevent UI blocking
      
    } catch (error) {
      console.error('[UIManager] Error handling file link:', error);
      this.showNotification(`Unable to open file: ${error.message}`, 'error');
      this._isHandlingFileLink = false;
    }
  }
  
  async trySystemOpen(windowsPath, fileUrl) {
    try {
      const systemOpenPromise = chrome.runtime.sendMessage({
        type: 'OPEN_FILE_SYSTEM',
        data: { filePath: windowsPath }
      });
      
      // Add timeout to prevent hanging
      const systemOpenResponse = await Promise.race([
        systemOpenPromise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 3000))
      ]);
      
      if (systemOpenResponse && systemOpenResponse.success) {
        this.showNotification('File opened with system default application', 'success');
        return true;
      }
      return false;
    } catch (systemError) {
      return false;
    }
  }

  async copyToClipboardFallback(fileUrl) {
    try {
      await navigator.clipboard.writeText(fileUrl);
      this.showNotification('File URL copied to clipboard - paste in browser address bar', 'info');
    } catch (clipboardError) {
      console.error('[UIManager] Clipboard failed:', clipboardError);
      this.showNotification('Unable to open file. URL: ' + fileUrl, 'warning');
    }
  }

  showFileAccessInstructions(windowsPath, fileUrl, unixPath) {
    const modal = this.createWarningModal({
      title: 'File Access Options',
      message: 'Chrome extensions cannot directly open local files due to security restrictions. Choose one of these methods to access your file:',
      details: `Windows Path: ${windowsPath}\nFile URL: ${fileUrl}\n\nRecommended Methods:\n1. Copy path and open in File Explorer\n2. Copy URL and paste in new browser tab\n3. Use "Open with" from File Explorer`,
      buttons: [
        {
          text: 'Copy Windows Path',
          style: 'primary',
          action: async () => {
            try {
              await navigator.clipboard.writeText(windowsPath);
              this.showNotification('Windows file path copied to clipboard', 'success');
            } catch (error) {
              console.error('Failed to copy path:', error);
              this.showNotification('Failed to copy, please copy manually', 'error');
            }
            this.closeWarningModal();
          }
        },
        {
          text: 'Copy File URL',
          style: 'secondary',
          action: async () => {
            try {
              await navigator.clipboard.writeText(fileUrl);
              this.showNotification('File URL copied to clipboard', 'success');
            } catch (error) {
              console.error('Failed to copy URL:', error);
              this.showNotification('Failed to copy, please copy manually', 'error');
            }
            this.closeWarningModal();
          }
        },
        {
          text: 'Try Open URL',
          style: 'secondary',
          action: async () => {
            try {
              
              // Try via background script first
              const response = await chrome.runtime.sendMessage({
                type: 'OPEN_FILE_URL',
                data: { fileUrl: fileUrl }
              });
              
              
              if (response && response.success) {
                this.showNotification('File opened successfully', 'success');
                this.closeWarningModal();
                return;
              }
              
              
              // Fallback to window.open
              const opened = window.open(fileUrl, '_blank');
              
              if (!opened) {
                this.showNotification('Popup blocked. Try copying URL instead.', 'warning');
              } else {
                this.showNotification('Attempting to open file in new tab...', 'info');
                
                // Check if the tab actually loaded the file after a delay
                setTimeout(() => {
                }, 2000);
              }
            } catch (error) {
              console.error('[UIManager] Failed to open file:', error);
              this.showNotification('Failed to open. Use copy options instead.', 'error');
            }
            this.closeWarningModal();
          }
        },
        {
          text: 'Close',
          style: 'secondary',
          action: () => {
            this.closeWarningModal();
          }
        }
      ]
    });
    
    document.body.appendChild(modal);
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
    console.log('[UIManager] Task submitted successfully, showing control panel');
    this.updateControlPanel('running');
    this.clearTaskInput();
  }

  handleTaskPaused(data) {
    this.updateControlPanel('paused');
    this.showNotification('Task paused successfully', 'info');
  }

  handleTaskResumed(data) {
    this.updateControlPanel('running');
    this.showNotification('Task resumed successfully', 'info');
  }

  handleTaskStopped(data) {
    this.updateControlPanel('ready');
    this.showNotification('Task stopped successfully', 'info');
  }

  handleTaskCompleted(data) {
    console.log('[UIManager] Task completed with status:', data.status);
    
    const message = data.status === 'done' ? 'Task completed successfully!' : 'Task completed with errors';
    const type = data.status === 'done' ? 'success' : 'error';
    
    // Check if we need to respect minimum visibility period
    if (this.controlPanelMinVisibilityActive) {
      console.log('[UIManager] Task completed during minimum visibility period, delaying control panel hide');
      // Wait for minimum visibility period to end before hiding
      const remainingTime = 2000; // Could be calculated more precisely, but 2s is reasonable
      setTimeout(() => {
        console.log('[UIManager] Minimum visibility period respected, now hiding control panel');
        this.updateControlPanel('ready');
      }, remainingTime);
    } else {
      console.log('[UIManager] Task completed, hiding control panel immediately');
      this.updateControlPanel('ready');
    }
    
    this.showNotification(message, type);
    
    // Clear uploaded files when task is completed
    this.clearUploadedFiles();
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
    this.showNotification(`Task error: ${data.error}`, 'error');
    
    // ✅ FIXED: Keep control panel visible during errors
    // Don't assume task stopped - it might still be running server-side
    this.updateControlPanel('error');
    
    // Optional: Verify task status after a delay
    setTimeout(() => {
      this.checkTaskStatus().then(status => {
        if (!status.isRunning) {
          console.log('[UIManager] Task confirmed stopped after error, hiding controls');
          this.updateControlPanel('ready');
        } else {
          console.log('[UIManager] Task still running after error, keeping controls visible');
        }
      }).catch(err => {
        console.warn('[UIManager] Could not verify task status after error:', err);
        // If we can't verify, keep controls visible for safety
      });
    }, 2000);
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
    // Check task status every 2 seconds
    this.taskStatusInterval = setInterval(() => {
      this.checkTaskStatus();
    }, 2000);
  }

  stopTaskStatusMonitoring() {
    if (this.taskStatusInterval) {
      clearInterval(this.taskStatusInterval);
      this.taskStatusInterval = null;
    }
  }

  updateUIForTaskStatus(isRunning) {
    // Disable/enable input elements based on task status
    if (this.elements.taskInput) {
      this.elements.taskInput.disabled = isRunning;
      this.elements.taskInput.placeholder = isRunning ?
        'Task is running - please wait...' :
        'Enter your task description...';
    }
    
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = isRunning || !this.canSubmitTask();
    }
    
    if (this.elements.llmProfileSelect) {
      this.elements.llmProfileSelect.disabled = isRunning;
    }
    
    if (this.elements.attachFileBtn) {
      this.elements.attachFileBtn.disabled = isRunning;
    }
    
    // Also disable header buttons when task is running
    if (this.elements.newSessionBtn) {
      this.elements.newSessionBtn.disabled = isRunning;
    }
    
    if (this.elements.historyBtn) {
      this.elements.historyBtn.disabled = isRunning;
    }
    
    if (this.elements.settingsBtn) {
      this.elements.settingsBtn.disabled = isRunning;
    }
    
    // Add visual feedback to indicate locked state
    const lockableElements = [
      this.elements.taskInput,
      this.elements.sendBtn,
      this.elements.llmProfileSelect,
      this.elements.attachFileBtn,
      this.elements.newSessionBtn,
      this.elements.historyBtn,
      this.elements.settingsBtn
    ];
    
    lockableElements.forEach(element => {
      if (element) {
        if (isRunning) {
          element.classList.add('task-running-disabled');
          element.setAttribute('title', 'Disabled while task is running');
        } else {
          element.classList.remove('task-running-disabled');
          element.removeAttribute('title');
        }
      }
    });
    
  }

  canSubmitTask() {
    const hasText = this.elements.taskInput?.value.trim().length > 0;
    const llmProfile = this.elements.llmProfileSelect?.value;
    const hasLlmProfile = llmProfile && llmProfile.trim() !== '';
    return hasText && hasLlmProfile && !this.state.isTaskRunning;
  }

  async showTaskRunningWarning(action) {
    const taskInfo = this.state.taskInfo;
    const taskId = taskInfo?.task_id || 'unknown';
    const sessionId = taskInfo?.session_id || 'unknown';
    
    return new Promise((resolve) => {
      const modal = this.createWarningModal({
        title: 'Task Currently Running',
        message: `A task is currently ${taskInfo?.status || 'running'}. You must stop the current task before you can ${action}.`,
        details: `Task ID: ${taskId}\nSession ID: ${sessionId}`,
        buttons: [
          {
            text: 'Stop Current Task',
            style: 'danger',
            action: async () => {
              try {
                await this.sessionManager.stopTask('User wants to perform new action');
                this.closeWarningModal();
                resolve(true);
              } catch (error) {
                this.showNotification(`Failed to stop task: ${error.message}`, 'error');
                resolve(false);
              }
            }
          },
          {
            text: 'Cancel',
            style: 'secondary',
            action: () => {
              this.closeWarningModal();
              resolve(false);
            }
          }
        ]
      });
      
      document.body.appendChild(modal);
    });
  }

  createWarningModal({ title, message, details, buttons }) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay warning-modal';
    modal.innerHTML = `
      <div class="modal-content warning-content">
        <div class="warning-header">
          <div class="warning-icon">⚠️</div>
          <h3>${title}</h3>
        </div>
        <div class="warning-body">
          <p>${message}</p>
          ${details ? `<pre class="warning-details">${details}</pre>` : ''}
        </div>
        <div class="warning-actions">
          ${buttons.map((btn, index) =>
            `<button class="btn btn-${btn.style}" data-action="${index}">${btn.text}</button>`
          ).join('')}
        </div>
      </div>
    `;
    
    // Add click handlers
    buttons.forEach((btn, index) => {
      const btnElement = modal.querySelector(`[data-action="${index}"]`);
      btnElement.addEventListener('click', btn.action);
    });
    
    return modal;
  }

  closeWarningModal() {
    const modal = document.querySelector('.warning-modal');
    if (modal) {
      modal.remove();
    }
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
    
    try {
      this.showLoading('Loading recent tasks...');
      
      // Reset to recent tasks view
      this.state.historyMode = 'recent';
      await this.loadRecentTasks();
      this.displayHistoryModal();
      
      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      this.showNotification(`Failed to load history: ${error.message}`, 'error');
    }
  }

  async handleShowSettings() {
    // Enhanced task running check
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('access settings');
      if (!canProceed) return;
    }
    
    try {
      this.showLoading('Loading settings...');
      
      await this.loadSettingsData();
      this.displaySettingsModal();
      
      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      this.showNotification(`Failed to load settings: ${error.message}`, 'error');
    }
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

  async handleSendTask() {
    // Check if task is already running with enhanced blocking
    const statusCheck = await this.checkTaskStatus();
    if (statusCheck.isRunning) {
      const canProceed = await this.showTaskRunningWarning('send a new task');
      if (!canProceed) {
        this.showNotification('Cannot send task while another task is running. Please stop the current task first.', 'warning');
        return;
      }
    }
    
    const taskDescription = this.elements.taskInput?.value.trim();
    const llmProfile = this.elements.llmProfileSelect?.value;
    
    if (!taskDescription) {
      this.showNotification('Please enter a task description', 'warning');
      this.elements.taskInput?.focus();
      return;
    }
    
    // Check if LLM profile is selected
    if (!llmProfile || llmProfile.trim() === '') {
      // Check if there are any LLM profiles available
      if (this.state.llmProfiles.length === 0) {
        // No LLM profiles configured at all
        this.showLLMProfileRequiredModal('configure');
      } else {
        // LLM profiles exist but none selected
        this.showLLMProfileRequiredModal('select');
      }
      return;
    }
    
    try {
      const taskData = {
        task_description: taskDescription,
        llm_profile_name: llmProfile
      };
      
      // Add uploaded files path if any
      if (this.state.uploadedFiles.length > 0) {
        console.log('[UIManager] Raw uploaded files state:', this.state.uploadedFiles);
        
        // Extract the first file path (backend expects single string)
        const firstFile = this.state.uploadedFiles[0];
        let filePath = null;
        
        if (typeof firstFile === 'string') {
          filePath = firstFile;
        } else if (firstFile && typeof firstFile === 'object') {
          // Extract path and normalize
          filePath = firstFile.file_path || firstFile.path || firstFile.stored_filename || firstFile.file_path;
          if (filePath) {
            filePath = filePath.replace(/\\/g, '/');
            console.log('[UIManager] Normalized file path:', filePath);
          }
        }
        
        if (filePath) {
          // Backend expects 'upload_files_path' as a single string
          taskData.upload_files_path = filePath;
          console.log('[UIManager] Set upload_files_path to:', filePath);
          
          // Show info if multiple files uploaded but only first will be processed
          if (this.state.uploadedFiles.length > 1) {
            console.warn('[UIManager] Multiple files uploaded, but backend only supports single file. Using first file:', filePath);
            this.showNotification(`Multiple files uploaded. Only the first file "${firstFile.name || filePath}" will be processed.`, 'warning');
          }
        } else {
          console.error('[UIManager] Could not extract file path from uploaded file:', firstFile);
        }
      }
      
      console.log('[UIManager] Complete task data being submitted:', JSON.stringify(taskData, null, 2));
      await this.sessionManager.submitTask(taskData);
      
      // Clear uploaded files after successful task submission
      this.clearUploadedFiles();
    } catch (error) {
      this.showNotification(`Failed to submit task: ${error.message}`, 'error');
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
      await this.sessionManager.stopTask('User clicked terminate');
    } catch (error) {
      this.showNotification(`Failed to terminate task: ${error.message}`, 'error');
    }
  }

  handleAttachFiles() {
    this.elements.fileInput?.click();
  }

  async handleFileSelection(event) {
    const files = Array.from(event.target.files);
    
    if (files.length === 0) return;
    
    try {
      this.showLoading(`Uploading ${files.length} file(s)...`);
      
      const response = await this.sessionManager.uploadFiles(files);
      
      console.log('[UIManager] File upload response:', response);
      
      // If SessionManager doesn't trigger the event, handle it directly
      if (response && response.files) {
        console.log('[UIManager] Manually handling uploaded files');
        this.handleFilesUploaded({
          sessionId: this.sessionManager.getCurrentSessionId(),
          files: response.files
        });
      }
      
      this.hideLoading();
      this.showNotification(`${files.length} file(s) uploaded successfully`, 'success');
      
      // Clear file input
      event.target.value = '';
    } catch (error) {
      this.hideLoading();
      this.showNotification(`File upload failed: ${error.message}`, 'error');
    }
  }

  handleFilesUploaded(data) {
    console.log('[UIManager] Files uploaded event received:', data);
    
    // Ensure data.files is always an array - handle both single file and array cases
    let filesArray = [];
    if (data.files) {
      if (Array.isArray(data.files)) {
        filesArray = data.files;
      } else {
        // If single file object, wrap in array
        filesArray = [data.files];
        console.log('[UIManager] Single file detected, wrapping in array');
      }
    }
    
    console.log('[UIManager] Processing files array:', filesArray);
    
    if (filesArray.length > 0) {
      // Append new files to existing uploaded files (for multiple uploads)
      const newFiles = filesArray.map(file => ({
        id: file.file_id,
        name: file.original_filename,
        path: file.file_path,  // Updated to use file_path field
        size: file.file_size,
        type: file.mime_type,
        stored_filename: file.stored_filename,
        file_path: file.file_path  // Add file_path for backward compatibility
      }));
      
      console.log('[UIManager] Mapped new files:', newFiles);
      
      // Add to existing files instead of replacing
      this.state.uploadedFiles = [...this.state.uploadedFiles, ...newFiles];
      
      console.log('[UIManager] Updated uploaded files state:', this.state.uploadedFiles);
      
      // Update the visual file list
      this.updateFilesList();
    } else {
      console.warn('[UIManager] No files to process in uploaded data');
    }
  }

  updateFilesList() {
    const container = this.getOrCreateFilesListContainer();
    
    // Debug logging to identify the issue
    console.log('[UIManager] updateFilesList called');
    console.log('[UIManager] uploadedFiles type:', typeof this.state.uploadedFiles);
    console.log('[UIManager] uploadedFiles isArray:', Array.isArray(this.state.uploadedFiles));
    console.log('[UIManager] uploadedFiles value:', this.state.uploadedFiles);
    
    // Ensure uploadedFiles is always an array
    if (!Array.isArray(this.state.uploadedFiles)) {
      console.error('[UIManager] uploadedFiles is not an array, resetting to empty array');
      this.state.uploadedFiles = [];
    }
    
    if (this.state.uploadedFiles.length === 0) {
      container.style.display = 'none';
      return;
    }
    
    container.style.display = 'block';
    
    // Build HTML safely with proper validation
    let filesHTML = '';
    try {
      filesHTML = this.state.uploadedFiles.map((file, index) => {
        console.log(`[UIManager] Processing file ${index}:`, file);
        
        // Validate file object structure
        if (!file || typeof file !== 'object') {
          console.error(`[UIManager] Invalid file object at index ${index}:`, file);
          return '';
        }
        
        // Extract properties safely with fallbacks
        const fileId = file.id || file.file_id || `file_${index}`;
        const fileName = file.name || file.original_filename || 'Unknown file';
        const filePath = file.path || file.file_path || file.stored_filename || 'Unknown path';
        
        console.log(`[UIManager] File display data: id=${fileId}, name=${fileName}, path=${filePath}`);
        
        return `
          <div class="file-item" data-file-id="${fileId}">
            <span class="file-name" title="${filePath}">${fileName}</span>
            <button class="file-remove-btn" title="Remove file" data-file-id="${fileId}">×</button>
          </div>
        `;
      }).join('');
    } catch (error) {
      console.error('[UIManager] Error generating files HTML:', error);
      filesHTML = '<div class="error-message">Error displaying files</div>';
    }
    
    container.innerHTML = `
      <div class="files-items">
        ${filesHTML}
      </div>
    `;
    
    // Add event listeners for remove buttons
    container.querySelectorAll('.file-remove-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const fileId = btn.dataset.fileId;
        this.removeUploadedFile(fileId);
      });
    });
  }

  getOrCreateFilesListContainer() {
    let container = document.getElementById('uploaded-files-list');
    
    if (!container) {
      container = document.createElement('div');
      container.id = 'uploaded-files-list';
      container.className = 'uploaded-files-container';
      
      // Insert after the textarea-container to avoid affecting button layout
      if (this.elements.taskInput) {
        const textareaContainer = this.elements.taskInput.closest('.textarea-container');
        if (textareaContainer && textareaContainer.parentElement) {
          // Insert after the textarea-container but before the input-footer
          const inputFooter = textareaContainer.parentElement.querySelector('.input-footer');
          if (inputFooter) {
            textareaContainer.parentElement.insertBefore(container, inputFooter);
          } else {
            textareaContainer.parentElement.insertBefore(container, textareaContainer.nextSibling);
          }
        }
      }
    }
    
    return container;
  }

  removeUploadedFile(fileId) {
    console.log('[UIManager] Removing uploaded file:', fileId);
    
    // Remove from state
    this.state.uploadedFiles = this.state.uploadedFiles.filter(file => file.id !== fileId);
    
    // Update visual list
    this.updateFilesList();
    
    this.showNotification('File removed from upload list', 'info');
  }

  formatFileSize(bytes) {
    if (!bytes) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  clearUploadedFiles() {
    this.state.uploadedFiles = [];
    this.updateFilesList();
  }

  handleTaskInputKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.handleSendTask();
    }
  }

  handleLlmProfileChange(event) {
    // Re-validate send button state when LLM profile changes
    if (this.elements.taskInput) {
      this.handleTaskInputChange({ target: this.elements.taskInput });
    }
  }

  handleTaskInputChange(event) {
    const hasText = event.target.value.trim().length > 0;
    const textarea = event.target;
    const llmProfile = this.elements.llmProfileSelect?.value;
    const hasLlmProfile = llmProfile && llmProfile.trim() !== '';
    
    // Update send button state - require both text and LLM profile and no running task
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = !(hasText && hasLlmProfile && !this.state.isTaskRunning);
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

  async handleBackendUrlChange(event) {
    const newUrl = event.target.value.trim();
    
    if (!newUrl) {
      this.showNotification('Backend URL cannot be empty', 'warning');
      return;
    }
    
    try {
      // Validate URL format
      new URL(newUrl);
      
      // Update API client
      this.apiClient.setBaseURL(newUrl);
      
      // Save to settings via main app
      if (window.vibeSurfApp) {
        await window.vibeSurfApp.updateSettings({ backendUrl: newUrl });
      }
      
      this.showNotification('Backend URL updated successfully', 'success');
      console.log('[UIManager] Backend URL updated to:', newUrl);
      
    } catch (error) {
      this.showNotification(`Invalid backend URL: ${error.message}`, 'error');
      console.error('[UIManager] Backend URL update failed:', error);
    }
  }

  // Settings Tab Management
  handleTabSwitch(event) {
    const clickedTab = event.currentTarget;
    const targetTabId = clickedTab.dataset.tab;
    
    // Update tab buttons
    this.elements.settingsTabs?.forEach(tab => {
      tab.classList.remove('active');
    });
    clickedTab.classList.add('active');
    
    // Update tab content
    this.elements.settingsTabContents?.forEach(content => {
      content.classList.remove('active');
    });
    const targetContent = document.getElementById(`${targetTabId}-tab`);
    if (targetContent) {
      targetContent.classList.add('active');
    }
  }

  // Profile Management
  async handleAddProfile(type) {
    try {
      this.showProfileForm(type);
    } catch (error) {
      console.error(`[UIManager] Failed to show ${type} profile form:`, error);
      this.showNotification(`Failed to show ${type} profile form`, 'error');
    }
  }

  async showProfileForm(type, profile = null) {
    const isEdit = profile !== null;
    const title = isEdit ? `Edit ${type.toUpperCase()} Profile` : `Add ${type.toUpperCase()} Profile`;
    
    if (this.elements.profileFormTitle) {
      this.elements.profileFormTitle.textContent = title;
    }
    
    // Generate form content based on type
    let formHTML = '';
    if (type === 'llm') {
      formHTML = await this.generateLLMProfileForm(profile);
    } else if (type === 'mcp') {
      formHTML = this.generateMCPProfileForm(profile);
    }
    
    if (this.elements.profileForm) {
      this.elements.profileForm.innerHTML = formHTML;
      this.elements.profileForm.dataset.type = type;
      this.elements.profileForm.dataset.mode = isEdit ? 'edit' : 'create';
      if (isEdit && profile) {
        this.elements.profileForm.dataset.profileId = profile.profile_name || profile.mcp_id;
      }
    }
    
    // Setup form event listeners
    this.setupProfileFormEvents();
    
    // Show modal
    if (this.elements.profileFormModal) {
      this.elements.profileFormModal.classList.remove('hidden');
    }
  }

  async generateLLMProfileForm(profile = null) {
    // Fetch available providers
    let providers = [];
    try {
      const response = await this.apiClient.getLLMProviders();
      providers = response.providers || response || [];
    } catch (error) {
      console.error('[UIManager] Failed to fetch LLM providers:', error);
    }
    
    const providersOptions = providers.map(p =>
      `<option value="${p.name}" ${profile?.provider === p.name ? 'selected' : ''}>${p.display_name}</option>`
    ).join('');
    
    const selectedProvider = profile?.provider || (providers.length > 0 ? providers[0].name : '');
    const selectedProviderData = providers.find(p => p.name === selectedProvider);
    const models = selectedProviderData?.models || [];
    
    const modelsOptions = models.map(model =>
      `<option value="${model}" ${profile?.model === model ? 'selected' : ''}>${model}</option>`
    ).join('');
    
    return `
      <div class="form-group">
        <label class="form-label required">Profile Name</label>
        <input type="text" name="profile_name" class="form-input" value="${profile?.profile_name || ''}"
               placeholder="Enter a unique name for this profile" required ${profile ? 'readonly' : ''}>
        <div class="form-help">A unique identifier for this LLM configuration</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">Provider</label>
        <select name="provider" class="form-select" required>
          <option value="">Select a provider</option>
          ${providersOptions}
        </select>
        <div class="form-help">Choose your LLM provider (OpenAI, Anthropic, etc.)</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">Model</label>
        <input type="text" name="model" class="form-input model-input" value="${profile?.model || ''}"
               list="model-options" placeholder="Select a model or type custom model name" required
               autocomplete="off">
        <datalist id="model-options">
          ${models.map(model => `<option value="${model}">${model}</option>`).join('')}
        </datalist>
        <div class="form-help">Choose from the list or enter a custom model name</div>
      </div>
      
      <div class="form-group api-key-field">
        <label class="form-label required">API Key</label>
        <input type="password" name="api_key" class="form-input api-key-input"
               placeholder="${profile ? 'Leave empty to keep existing key' : 'Enter your API key'}"
               ${profile ? '' : 'required'}>
        <button type="button" class="api-key-toggle" title="Toggle visibility">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/>
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
          </svg>
        </button>
        <div class="form-help">Your provider's API key for authentication</div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Base URL</label>
        <input type="url" name="base_url" class="form-input" value="${profile?.base_url || ''}"
               placeholder="https://api.openai.com/v1">
        <div class="form-help">Custom API endpoint (leave empty for provider default)</div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Temperature</label>
        <input type="number" name="temperature" class="form-input" value="${profile?.temperature || ''}"
               min="0" max="2" step="0.1" placeholder="0.7">
        <div class="form-help">Controls randomness (0.0-2.0, lower = more focused)</div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Max Tokens</label>
        <input type="number" name="max_tokens" class="form-input" value="${profile?.max_tokens || ''}"
               min="1" max="128000" placeholder="4096">
        <div class="form-help">Maximum tokens in the response</div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-textarea" placeholder="Optional description for this profile">${profile?.description || ''}</textarea>
        <div class="form-help">Optional description to help identify this profile</div>
      </div>
      
      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_default" ${profile?.is_default ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">Set as default profile</span>
        </label>
        <div class="form-help">This profile will be selected by default for new tasks</div>
      </div>
    `;
  }

  generateMCPProfileForm(profile = null) {
    // Convert existing profile to JSON for editing
    let defaultJson = '{\n  "command": "npx",\n  "args": [\n    "-y",\n    "@modelcontextprotocol/server-filesystem",\n    "/path/to/directory"\n  ]\n}';
    
    if (profile?.mcp_server_params) {
      try {
        defaultJson = JSON.stringify(profile.mcp_server_params, null, 2);
      } catch (error) {
        console.warn('[UIManager] Failed to stringify existing mcp_server_params:', error);
      }
    }
    
    return `
      <div class="form-group">
        <label class="form-label required">Display Name</label>
        <input type="text" name="display_name" class="form-input" value="${profile?.display_name || ''}"
               placeholder="Enter a friendly name for this MCP profile" required ${profile ? 'readonly' : ''}>
        <div class="form-help">A user-friendly name for this MCP configuration</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">Server Name</label>
        <input type="text" name="mcp_server_name" class="form-input" value="${profile?.mcp_server_name || ''}"
               placeholder="e.g., filesystem, markitdown, brave-search" required>
        <div class="form-help">The MCP server identifier</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">MCP Server Parameters (JSON)</label>
        <textarea name="mcp_server_params_json" class="form-textarea json-input" rows="8"
                  placeholder="Enter JSON configuration for MCP server parameters" required>${defaultJson}</textarea>
        <div class="json-validation-feedback"></div>
        <div class="form-help">
          JSON configuration including command and arguments. Example:
          <br><code>{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]}</code>
        </div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-textarea" placeholder="Optional description for this MCP profile">${profile?.description || ''}</textarea>
        <div class="form-help">Optional description to help identify this profile</div>
      </div>
      
      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_active" ${profile?.is_active !== false ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">Active</span>
        </label>
        <div class="form-help">Whether this MCP profile is active and available for use</div>
      </div>
    `;
  }

  setupProfileFormEvents() {
    console.log('[UIManager] Setting up profile form events');
    
    // Add form submission handler first (directly, no cloning)
    if (this.elements.profileForm) {
      this.elements.profileForm.addEventListener('submit', this.handleProfileFormSubmit.bind(this));
      console.log('[UIManager] Form submit listener added');
    }
    
    // Provider change handler for LLM profiles
    const providerSelect = this.elements.profileForm?.querySelector('select[name="provider"]');
    if (providerSelect) {
      providerSelect.addEventListener('change', this.handleProviderChange.bind(this));
      console.log('[UIManager] Provider select change listener added');
    }
    
    // API key toggle handler
    const apiKeyToggle = this.elements.profileForm?.querySelector('.api-key-toggle');
    const apiKeyInput = this.elements.profileForm?.querySelector('.api-key-input');
    if (apiKeyToggle && apiKeyInput) {
      apiKeyToggle.addEventListener('click', () => {
        const isPassword = apiKeyInput.type === 'password';
        apiKeyInput.type = isPassword ? 'text' : 'password';
        
        // Update icon
        const svg = apiKeyToggle.querySelector('svg');
        if (svg) {
          svg.innerHTML = isPassword ?
            '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C7 20 2.73 16.39 1 12A18.45 18.45 0 0 1 5.06 5.06L17.94 17.94ZM9.9 4.24A9.12 9.12 0 0 1 12 4C17 4 21.27 7.61 23 12A18.5 18.5 0 0 1 19.42 16.42" stroke="currentColor" stroke-width="2" fill="none"/><path d="M1 1L23 23" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/>' :
            '<path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>';
        }
      });
      console.log('[UIManager] API key toggle listener added');
    }
    
    // JSON validation handler for MCP profiles
    const jsonInput = this.elements.profileForm?.querySelector('textarea[name="mcp_server_params_json"]');
    if (jsonInput) {
      jsonInput.addEventListener('input', this.handleJsonInputValidation.bind(this));
      jsonInput.addEventListener('blur', this.handleJsonInputValidation.bind(this));
      console.log('[UIManager] JSON validation listener added');
      
      // Trigger initial validation
      this.handleJsonInputValidation({ target: jsonInput });
    }
  }

  handleJsonInputValidation(event) {
    const textarea = event.target;
    const feedbackElement = textarea.parentElement.querySelector('.json-validation-feedback');
    
    if (!feedbackElement) return;
    
    const jsonText = textarea.value.trim();
    
    if (!jsonText) {
      feedbackElement.innerHTML = '';
      textarea.classList.remove('json-valid', 'json-invalid');
      return;
    }
    
    try {
      const parsed = JSON.parse(jsonText);
      
      // Validate that it's an object (not array, string, etc.)
      if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
        throw new Error('MCP server parameters must be a JSON object');
      }
      
      // Validate required fields
      if (!parsed.command || typeof parsed.command !== 'string') {
        throw new Error('Missing or invalid "command" field (must be a string)');
      }
      
      // Validate args if present
      if (parsed.args && !Array.isArray(parsed.args)) {
        throw new Error('"args" field must be an array if provided');
      }
      
      // Success
      feedbackElement.innerHTML = '<span class="json-success">✓ Valid JSON configuration</span>';
      textarea.classList.remove('json-invalid');
      textarea.classList.add('json-valid');
      
      // Store valid state for form submission
      textarea.dataset.isValid = 'true';
      
    } catch (error) {
      const errorMessage = error.message;
      feedbackElement.innerHTML = `<span class="json-error">✗ Invalid JSON: ${errorMessage}</span>`;
      textarea.classList.remove('json-valid');
      textarea.classList.add('json-invalid');
      
      // Store invalid state for form submission
      textarea.dataset.isValid = 'false';
      textarea.dataset.errorMessage = errorMessage;
      
      // Show error modal for critical validation errors - trigger on both blur and input events
      if ((event.type === 'blur' || event.type === 'input') && jsonText.length > 0) {
        console.log('[UIManager] JSON validation failed, showing error modal:', errorMessage);
        setTimeout(() => {
          this.showJsonValidationErrorModal(errorMessage);
        }, event.type === 'blur' ? 100 : 500); // Longer delay for input events
      }
    }
  }

  showJsonValidationErrorModal(errorMessage) {
    console.log('[UIManager] Creating JSON validation error modal');
    const modal = this.createWarningModal({
      title: 'JSON Validation Error',
      message: 'The MCP server parameters contain invalid JSON format.',
      details: `Error: ${errorMessage}\n\nPlease correct the JSON format before submitting the form.`,
      buttons: [
        {
          text: 'OK',
          style: 'primary',
          action: () => {
            console.log('[UIManager] JSON validation error modal OK clicked');
            this.closeWarningModal();
          }
        }
      ]
    });
    
    console.log('[UIManager] Appending JSON validation error modal to body');
    document.body.appendChild(modal);
  }

  // Add separate method to handle submit button clicks
  handleProfileFormSubmitClick(event) {
    console.log('[UIManager] Profile form submit button clicked');
    event.preventDefault();
    
    // Find the form and trigger submit
    const form = this.elements.profileForm;
    if (form) {
      console.log('[UIManager] Triggering form submit via button click');
      const submitEvent = new Event('submit', { cancelable: true, bubbles: true });
      form.dispatchEvent(submitEvent);
    } else {
      console.error('[UIManager] Profile form not found when submit button clicked');
    }
  }

  async handleProviderChange(event) {
    const selectedProvider = event.target.value;
    const modelInput = this.elements.profileForm?.querySelector('input[name="model"]');
    const modelDatalist = this.elements.profileForm?.querySelector('#model-options');
    
    console.log('[UIManager] Provider changed to:', selectedProvider);
    
    if (!selectedProvider || !modelInput || !modelDatalist) {
      console.warn('[UIManager] Missing elements for provider change');
      return;
    }
    
    // Always clear the model input when provider changes
    modelInput.value = '';
    modelInput.placeholder = `Loading ${selectedProvider} models...`;
    modelDatalist.innerHTML = '<option value="">Loading...</option>';
    
    try {
      console.log('[UIManager] Fetching models for provider:', selectedProvider);
      const response = await this.apiClient.getLLMProviderModels(selectedProvider);
      const models = response.models || response || [];
      
      console.log('[UIManager] Received models:', models);
      
      // Update datalist options
      modelDatalist.innerHTML = models.map(model =>
        `<option value="${model}">${model}</option>`
      ).join('');
      
      // Update placeholder to reflect the new provider
      modelInput.placeholder = models.length > 0
        ? `Select a ${selectedProvider} model or type custom model name`
        : `Enter ${selectedProvider} model name`;
        
      console.log('[UIManager] Model list updated for provider:', selectedProvider);
        
    } catch (error) {
      console.error('[UIManager] Failed to fetch models for provider:', error);
      modelDatalist.innerHTML = '<option value="">Failed to load models</option>';
      modelInput.placeholder = `Enter ${selectedProvider} model name manually`;
      
      // Show user-friendly error notification
      this.showNotification(`Failed to load models for ${selectedProvider}. You can enter the model name manually.`, 'warning');
    }
  }

  closeProfileForm() {
    if (this.elements.profileFormModal) {
      this.elements.profileFormModal.classList.add('hidden');
    }
  }

  async handleProfileFormSubmit(event) {
    event.preventDefault();
    console.log('[UIManager] Profile form submit triggered');
    
    const form = event.target;
    
    // Prevent multiple submissions
    if (form.dataset.submitting === 'true') {
      console.log('[UIManager] Form already submitting, ignoring duplicate submission');
      return;
    }
    
    const formData = new FormData(form);
    const type = form.dataset.type;
    const mode = form.dataset.mode;
    const profileId = form.dataset.profileId;
    
    console.log('[UIManager] Form submission details:', { type, mode, profileId });
    
    // Set submitting state and disable form
    form.dataset.submitting = 'true';
    this.setProfileFormSubmitting(true);
    
    // Convert FormData to object
    const data = {};
    
    // Handle checkbox fields explicitly first
    const checkboxFields = ['is_default', 'is_active'];
    checkboxFields.forEach(fieldName => {
      const checkbox = form.querySelector(`input[name="${fieldName}"]`);
      if (checkbox) {
        data[fieldName] = checkbox.checked;
        console.log(`[UIManager] Checkbox field: ${fieldName} = ${checkbox.checked}`);
      }
    });
    
    for (const [key, value] of formData.entries()) {
      console.log(`[UIManager] Form field: ${key} = ${value}`);
      if (value.trim() !== '') {
        if (key === 'args' && type === 'mcp') {
          // Split args by newlines for MCP profiles
          data[key] = value.split('\n').map(arg => arg.trim()).filter(arg => arg);
        } else if (key === 'is_default' || key === 'is_active') {
          // Skip - already handled above with explicit checkbox checking
          continue;
        } else if (key === 'temperature') {
          const num = parseFloat(value);
          if (!isNaN(num) && num >= 0) {
            data[key] = num;
          }
          // 如果不设置或无效值，就不传给后端
        } else if (key === 'max_tokens') {
          const num = parseInt(value);
          if (!isNaN(num) && num > 0) {
            data[key] = num;
          }
          // Max Tokens如果不设置的话，不用传到后端
        } else {
          data[key] = value;
        }
      }
    }
    
    console.log('[UIManager] Processed form data:', data);
    
    // Handle MCP server params structure - parse JSON input
    if (type === 'mcp') {
      const jsonInput = data.mcp_server_params_json;
      
      // Check if JSON was pre-validated
      const jsonTextarea = form.querySelector('textarea[name="mcp_server_params_json"]');
      if (jsonTextarea && jsonTextarea.dataset.isValid === 'false') {
        console.error('[UIManager] JSON validation failed during form submission');
        this.showJsonValidationErrorModal(jsonTextarea.dataset.errorMessage || 'Invalid JSON format');
        return; // Don't submit the form if JSON is invalid
      }
      
      if (jsonInput) {
        try {
          const parsedParams = JSON.parse(jsonInput);
          
          // Validate the parsed JSON structure
          if (typeof parsedParams !== 'object' || Array.isArray(parsedParams) || parsedParams === null) {
            throw new Error('MCP server parameters must be a JSON object');
          }
          
          if (!parsedParams.command || typeof parsedParams.command !== 'string') {
            throw new Error('Missing or invalid "command" field (must be a string)');
          }
          
          if (parsedParams.args && !Array.isArray(parsedParams.args)) {
            throw new Error('"args" field must be an array if provided');
          }
          
          // Set the parsed parameters
          data.mcp_server_params = parsedParams;
          console.log('[UIManager] MCP server params parsed from JSON:', data.mcp_server_params);
          
        } catch (error) {
          console.error('[UIManager] Failed to parse MCP server params JSON:', error);
          this.showJsonValidationErrorModal(error.message);
          return; // Don't submit the form if JSON is invalid
        }
      } else {
        console.error('[UIManager] Missing mcp_server_params_json in form data');
        this.showNotification('MCP server parameters JSON is required', 'error');
        return;
      }
      
      // Remove the JSON field as it's not needed in the API request
      delete data.mcp_server_params_json;
      console.log('[UIManager] MCP data structure updated:', data);
    }
    
    try {
      console.log(`[UIManager] Starting ${mode} operation for ${type} profile`);
      let response;
      const endpoint = type === 'llm' ? '/config/llm-profiles' : '/config/mcp-profiles';
      
      if (mode === 'create') {
        console.log('[UIManager] Creating new profile...');
        if (type === 'llm') {
          response = await this.apiClient.createLLMProfile(data);
        } else {
          response = await this.apiClient.createMCPProfile(data);
        }
      } else {
        console.log('[UIManager] Updating existing profile...');
        if (type === 'llm') {
          response = await this.apiClient.updateLLMProfile(profileId, data);
        } else {
          response = await this.apiClient.updateMCPProfile(profileId, data);
        }
      }
      
      console.log('[UIManager] API response:', response);
      
      this.closeProfileForm();
      this.showNotification(`${type.toUpperCase()} profile ${mode === 'create' ? 'created' : 'updated'} successfully`, 'success');
      
      console.log('[UIManager] Refreshing settings data...');
      // Refresh the settings data
      await this.loadSettingsData();
      console.log('[UIManager] Settings data refreshed');
      
      // Force re-render of MCP profiles to ensure status is updated
      if (type === 'mcp') {
        console.log('[UIManager] Force updating MCP profiles display');
        this.renderMCPProfiles(this.state.mcpProfiles);
      }
      
    } catch (error) {
      console.error(`[UIManager] Failed to ${mode} ${type} profile:`, error);
      
      // Handle specific error types for better user experience
      let errorMessage = error.message || 'Unknown error occurred';
      
      if (errorMessage.includes('already exists') || errorMessage.includes('already in use')) {
        // For duplicate profile name errors, highlight the name field
        this.highlightProfileNameError(errorMessage);
        errorMessage = errorMessage; // Use the specific error message from backend
      } else if (errorMessage.includes('UNIQUE constraint')) {
        errorMessage = `Profile name '${data.profile_name || data.display_name}' already exists. Please choose a different name.`;
        this.highlightProfileNameError(errorMessage);
      }
      
      this.showNotification(`Failed to ${mode} ${type} profile: ${errorMessage}`, 'error');
    } finally {
      // Reset form state
      form.dataset.submitting = 'false';
      this.setProfileFormSubmitting(false);
    }
  }

  setProfileFormSubmitting(isSubmitting) {
    const form = this.elements.profileForm;
    const submitButton = this.elements.profileFormSubmit;
    const cancelButton = this.elements.profileFormCancel;
    
    if (!form) return;
    
    // Disable/enable form inputs
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
      input.disabled = isSubmitting;
    });
    
    // Update submit button
    if (submitButton) {
      submitButton.disabled = isSubmitting;
      submitButton.textContent = isSubmitting ? 'Saving...' : 'Save Profile';
    }
    
    // Update cancel button
    if (cancelButton) {
      cancelButton.disabled = isSubmitting;
    }
    
    console.log(`[UIManager] Profile form submitting state: ${isSubmitting}`);
  }

  highlightProfileNameError(errorMessage) {
    const nameInput = this.elements.profileForm?.querySelector('input[name="profile_name"], input[name="display_name"]');
    
    if (nameInput) {
      // Add error styling
      nameInput.classList.add('form-error');
      nameInput.focus();
      
      // Create or update error message
      let errorElement = nameInput.parentElement.querySelector('.profile-name-error');
      if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'form-error-message profile-name-error';
        nameInput.parentElement.appendChild(errorElement);
      }
      
      errorElement.textContent = errorMessage;
      
      // Remove error styling after user starts typing
      const removeError = () => {
        nameInput.classList.remove('form-error');
        if (errorElement) {
          errorElement.remove();
        }
        nameInput.removeEventListener('input', removeError);
      };
      
      nameInput.addEventListener('input', removeError);
      
      console.log('[UIManager] Highlighted profile name error:', errorMessage);
    }
  }

  // Real-time profile name validation
  async validateProfileNameAvailability(profileName, profileType) {
    if (!profileName || profileName.trim().length < 2) {
      return { isValid: true, message: '' }; // Don't validate very short names
    }
    
    try {
      // Check if profile already exists
      const profiles = profileType === 'llm' ? this.state.llmProfiles : this.state.mcpProfiles;
      const nameField = profileType === 'llm' ? 'profile_name' : 'display_name';
      
      const existingProfile = profiles.find(profile =>
        profile[nameField].toLowerCase() === profileName.toLowerCase()
      );
      
      if (existingProfile) {
        return {
          isValid: false,
          message: `${profileType.toUpperCase()} profile "${profileName}" already exists. Please choose a different name.`
        };
      }
      
      return { isValid: true, message: '' };
    } catch (error) {
      console.error('[UIManager] Error validating profile name:', error);
      return { isValid: true, message: '' }; // Don't block on validation errors
    }
  }


  // Settings Data Management
  async loadSettingsData() {
    try {
      // Load LLM profiles
      await this.loadLLMProfiles();
      
      // Load MCP profiles
      await this.loadMCPProfiles();
      
      // Load environment variables
      await this.loadEnvironmentVariables();
      
      // Update LLM profile select dropdown
      this.updateLLMProfileSelect();
      
    } catch (error) {
      console.error('[UIManager] Failed to load settings data:', error);
      this.showNotification('Failed to load settings data', 'error');
    }
  }

  async loadLLMProfiles() {
    try {
      const response = await this.apiClient.getLLMProfiles(false); // Load all profiles, not just active
      console.log('[UIManager] LLM profiles loaded:', response);
      
      // Handle different response structures
      let profiles = [];
      if (Array.isArray(response)) {
        profiles = response;
      } else if (response.profiles && Array.isArray(response.profiles)) {
        profiles = response.profiles;
      } else if (response.data && Array.isArray(response.data)) {
        profiles = response.data;
      }
      
      this.state.llmProfiles = profiles;
      this.renderLLMProfiles(profiles);
      this.updateLLMProfileSelect();
    } catch (error) {
      console.error('[UIManager] Failed to load LLM profiles:', error);
      this.state.llmProfiles = [];
      this.renderLLMProfiles([]);
      this.updateLLMProfileSelect();
    }
  }

  async loadMCPProfiles() {
    try {
      const response = await this.apiClient.getMCPProfiles(false); // Load all profiles, not just active
      console.log('[UIManager] MCP profiles loaded:', response);
      
      // Handle different response structures
      let profiles = [];
      if (Array.isArray(response)) {
        profiles = response;
      } else if (response.profiles && Array.isArray(response.profiles)) {
        profiles = response.profiles;
      } else if (response.data && Array.isArray(response.data)) {
        profiles = response.data;
      }
      
      this.state.mcpProfiles = profiles;
      this.renderMCPProfiles(profiles);
    } catch (error) {
      console.error('[UIManager] Failed to load MCP profiles:', error);
      this.state.mcpProfiles = [];
      this.renderMCPProfiles([]);
    }
  }

  async loadEnvironmentVariables() {
    try {
      const response = await this.apiClient.getEnvironmentVariables();
      console.log('[UIManager] Environment variables loaded:', response);
      const envVars = response.environments || response || {};
      this.renderEnvironmentVariables(envVars);
    } catch (error) {
      console.error('[UIManager] Failed to load environment variables:', error);
      this.renderEnvironmentVariables({});
    }
  }

  renderLLMProfiles(profiles) {
    const container = document.getElementById('llm-profiles-list');
    if (!container) return;

    if (profiles.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h3>No LLM Profiles</h3>
          <p>Create your first LLM profile to get started</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_default ? 'default' : ''}" data-profile-id="${profile.profile_name}">
        ${profile.is_default ? '<div class="profile-badge">Default</div>' : ''}
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.profile_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.provider)}</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="Edit Profile" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="Delete Profile" data-profile-id="${profile.profile_name}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="profile-content">
          <div class="profile-info">
            <span class="profile-model">${this.escapeHtml(profile.model)}</span>
            ${profile.description ? `<p class="profile-description">${this.escapeHtml(profile.description)}</p>` : ''}
          </div>
          <div class="profile-details">
            ${profile.base_url ? `<div class="profile-detail"><strong>Base URL:</strong> ${this.escapeHtml(profile.base_url)}</div>` : ''}
            ${profile.temperature !== undefined ? `<div class="profile-detail"><strong>Temperature:</strong> ${profile.temperature}</div>` : ''}
            ${profile.max_tokens ? `<div class="profile-detail"><strong>Max Tokens:</strong> ${profile.max_tokens}</div>` : ''}
          </div>
        </div>
      </div>
    `).join('');

    container.innerHTML = profilesHTML;

    // Add event listeners for profile actions
    container.querySelectorAll('.edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const profile = JSON.parse(btn.dataset.profile);
        this.showProfileForm('llm', profile);
      });
    });

    container.querySelectorAll('.delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await this.handleDeleteProfile('llm', btn.dataset.profileId);
      });
    });
  }

  renderMCPProfiles(profiles) {
    const container = document.getElementById('mcp-profiles-list');
    if (!container) return;

    if (profiles.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 2V8M16 2V8M3 10H21M5 4H19C20.1046 4 21 4.89543 21 6V20C21 21.1046 20.1046 22 19 22H5C3.89543 22 3 21.1046 3 20V6C3 4.89543 3.89543 4 5 4Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h3>No MCP Profiles</h3>
          <p>Create your first MCP profile to enable server integrations</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_active ? 'active' : 'inactive'}" data-profile-id="${profile.mcp_id}">
        <div class="profile-status ${profile.is_active ? 'active' : 'inactive'}">
          ${profile.is_active ? 'Active' : 'Inactive'}
        </div>
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.display_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.mcp_server_name)}</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="Edit Profile" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="Delete Profile" data-profile-id="${profile.mcp_id}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="profile-content">
          ${profile.description ? `<p class="profile-description">${this.escapeHtml(profile.description)}</p>` : ''}
          <div class="profile-details">
            <div class="profile-detail"><strong>Command:</strong> ${this.escapeHtml(profile.mcp_server_params?.command || 'N/A')}</div>
            ${profile.mcp_server_params?.args?.length ? `<div class="profile-detail"><strong>Args:</strong> ${profile.mcp_server_params.args.join(', ')}</div>` : ''}
          </div>
        </div>
      </div>
    `).join('');

    container.innerHTML = profilesHTML;

    // Add event listeners for profile actions
    container.querySelectorAll('.edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const profile = JSON.parse(btn.dataset.profile);
        this.showProfileForm('mcp', profile);
      });
    });

    container.querySelectorAll('.delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await this.handleDeleteProfile('mcp', btn.dataset.profileId);
      });
    });
  }

  renderEnvironmentVariables(envVars) {
    const container = this.elements.envVariablesList;
    if (!container) return;

    // Clear existing content
    container.innerHTML = '';

    // Check if there are any environment variables to display
    if (Object.keys(envVars).length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔧</div>
          <div class="empty-state-title">No Environment Variables</div>
          <div class="empty-state-description">Environment variables are configured on the backend. Only updates to existing variables are allowed.</div>
        </div>
      `;
      return;
    }

    // Backend URL related keys that should be readonly
    const backendUrlKeys = [
      'BACKEND_URL',
      'VIBESURF_BACKEND_URL',
      'API_URL',
      'BASE_URL',
      'API_BASE_URL',
      'BACKEND_API_URL'
    ];

    // Add existing environment variables (read-only keys, editable/readonly values based on type)
    Object.entries(envVars).forEach(([key, value]) => {
      const envVarItem = document.createElement('div');
      envVarItem.className = 'env-var-item';
      
      // Check if this is a backend URL variable
      const isBackendUrl = backendUrlKeys.includes(key.toUpperCase());
      const valueReadonly = isBackendUrl ? 'readonly' : '';
      const valueClass = isBackendUrl ? 'form-input readonly-input' : 'form-input';
      const valueTitle = isBackendUrl ? 'Backend URL is not editable from settings' : '';
      
      envVarItem.innerHTML = `
        <div class="env-var-key">
          <input type="text" class="form-input" placeholder="Variable name" value="${this.escapeHtml(key)}" readonly>
        </div>
        <div class="env-var-value">
          <input type="text" class="${valueClass}" placeholder="Variable value" value="${this.escapeHtml(value)}" ${valueReadonly} title="${valueTitle}">
        </div>
      `;

      container.appendChild(envVarItem);
    });
  }

  async handleDeleteProfile(type, profileId) {
    // Check if this is a default LLM profile
    if (type === 'llm') {
      const profile = this.state.llmProfiles.find(p => p.profile_name === profileId);
      if (profile && profile.is_default) {
        // Handle default profile deletion differently
        return await this.handleDeleteDefaultProfile(profileId);
      }
    }
    
    // Create a modern confirmation modal instead of basic confirm()
    return new Promise((resolve) => {
      const modal = this.createWarningModal({
        title: `Delete ${type.toUpperCase()} Profile`,
        message: `Are you sure you want to delete the "${profileId}" profile? This action cannot be undone.`,
        details: `This will permanently remove the ${type.toUpperCase()} profile and all its configurations.`,
        buttons: [
          {
            text: 'Delete Profile',
            style: 'danger',
            action: async () => {
              this.closeWarningModal();
              await this.performDeleteProfile(type, profileId);
              resolve(true);
            }
          },
          {
            text: 'Cancel',
            style: 'secondary',
            action: () => {
              this.closeWarningModal();
              resolve(false);
            }
          }
        ]
      });
      
      document.body.appendChild(modal);
    });
  }

  async handleDeleteDefaultProfile(profileId) {
    // Get other available profiles
    const otherProfiles = this.state.llmProfiles.filter(p => p.profile_name !== profileId);
    
    if (otherProfiles.length === 0) {
      // No other profiles available - cannot delete
      const modal = this.createWarningModal({
        title: 'Cannot Delete Default Profile',
        message: 'This is the only LLM profile configured. You cannot delete it without having at least one other profile.',
        details: 'Please create another LLM profile first, then you can delete this one.',
        buttons: [
          {
            text: 'Create New Profile',
            style: 'primary',
            action: () => {
              this.closeWarningModal();
              this.handleAddProfile('llm');
            }
          },
          {
            text: 'Cancel',
            style: 'secondary',
            action: () => {
              this.closeWarningModal();
            }
          }
        ]
      });
      
      document.body.appendChild(modal);
      return false;
    }
    
    // Show modal to select new default profile
    return new Promise((resolve) => {
      const profileOptions = otherProfiles.map(profile =>
        `<label style="display: flex; align-items: center; gap: 8px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin: 4px 0; cursor: pointer;">
          <input type="radio" name="newDefault" value="${profile.profile_name}" required>
          <div>
            <div style="font-weight: bold;">${profile.profile_name}</div>
            <div style="font-size: 12px; color: #666;">${profile.provider} - ${profile.model}</div>
          </div>
        </label>`
      ).join('');
      
      const modal = this.createWarningModal({
        title: 'Delete Default Profile',
        message: `"${profileId}" is currently the default profile. Please select a new default profile before deleting it.`,
        details: `<div style="margin: 16px 0;">
          <div style="font-weight: bold; margin-bottom: 8px;">Select new default profile:</div>
          <form id="newDefaultForm" style="max-height: 200px; overflow-y: auto;">
            ${profileOptions}
          </form>
        </div>`,
        buttons: [
          {
            text: 'Set Default & Delete',
            style: 'danger',
            action: async () => {
              const form = document.getElementById('newDefaultForm');
              const selectedProfile = form.querySelector('input[name="newDefault"]:checked');
              
              if (!selectedProfile) {
                this.showNotification('Please select a new default profile', 'warning');
                return;
              }
              
              try {
                this.closeWarningModal();
                await this.setNewDefaultAndDelete(selectedProfile.value, profileId);
                resolve(true);
              } catch (error) {
                this.showNotification(`Failed to update default profile: ${error.message}`, 'error');
                resolve(false);
              }
            }
          },
          {
            text: 'Cancel',
            style: 'secondary',
            action: () => {
              this.closeWarningModal();
              resolve(false);
            }
          }
        ]
      });
      
      document.body.appendChild(modal);
    });
  }

  async setNewDefaultAndDelete(newDefaultProfileId, profileToDelete) {
    try {
      this.showLoading('Updating default profile...');
      
      // First, set the new default profile
      await this.apiClient.updateLLMProfile(newDefaultProfileId, { is_default: true });
      
      this.showLoading('Deleting profile...');
      
      // Then delete the old default profile
      await this.apiClient.deleteLLMProfile(profileToDelete);
      
      this.showNotification(`Profile "${profileToDelete}" deleted and "${newDefaultProfileId}" set as default`, 'success');
      
      // Refresh the settings data
      await this.loadSettingsData();
      
      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      console.error('[UIManager] Failed to set new default and delete profile:', error);
      this.showNotification(`Failed to update profiles: ${error.message}`, 'error');
      throw error;
    }
  }

  async performDeleteProfile(type, profileId) {
    try {
      this.showLoading(`Deleting ${type} profile...`);
      
      if (type === 'llm') {
        await this.apiClient.deleteLLMProfile(profileId);
      } else {
        await this.apiClient.deleteMCPProfile(profileId);
      }
      
      this.showNotification(`${type.toUpperCase()} profile deleted successfully`, 'success');
      
      // Refresh the settings data
      await this.loadSettingsData();
      
      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      console.error(`[UIManager] Failed to delete ${type} profile:`, error);
      this.showNotification(`Failed to delete ${type} profile: ${error.message}`, 'error');
    }
  }

  async handleSaveEnvironmentVariables() {
    if (!this.elements.envVariablesList) return;

    const envVarItems = this.elements.envVariablesList.querySelectorAll('.env-var-item');
    const envVars = {};

    // Backend URL related keys that should be skipped during save
    const backendUrlKeys = [
      'BACKEND_URL',
      'VIBESURF_BACKEND_URL',
      'API_URL',
      'BASE_URL',
      'API_BASE_URL',
      'BACKEND_API_URL'
    ];

    envVarItems.forEach(item => {
      const keyInput = item.querySelector('.env-var-key input');
      const valueInput = item.querySelector('.env-var-value input');
      
      if (keyInput && valueInput && keyInput.value.trim()) {
        const key = keyInput.value.trim();
        const value = valueInput.value.trim();
        
        // Skip backend URL variables (they are readonly)
        if (!backendUrlKeys.includes(key.toUpperCase())) {
          envVars[key] = value;
        }
      }
    });

    try {
      await this.apiClient.updateEnvironmentVariables(envVars);
      this.showNotification('Environment variables updated successfully (backend URL variables are read-only)', 'success');
    } catch (error) {
      console.error('[UIManager] Failed to update environment variables:', error);
      this.showNotification(`Failed to update environment variables: ${error.message}`, 'error');
    }
  }

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // UI Display Methods
  updateSessionDisplay(sessionId) {
    console.log('[UIManager] Updating session display with ID:', sessionId);
    if (this.elements.sessionId) {
      this.elements.sessionId.textContent = sessionId || '-';
      console.log('[UIManager] Session ID display updated to:', sessionId);
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
        console.log('[UIManager] Setting control panel to ready (hidden)');
        panel.classList.add('hidden');
        panel.classList.remove('error-state');
        break;
        
      case 'running':
        console.log('[UIManager] Setting control panel to running (showing cancel button)');
        panel.classList.remove('hidden');
        panel.classList.remove('error-state');
        cancelBtn?.classList.remove('hidden');
        resumeBtn?.classList.add('hidden');
        terminateBtn?.classList.add('hidden');
        
        // For fast-completing tasks, ensure minimum visibility duration
        this.ensureMinimumControlPanelVisibility();
        break;
        
      case 'paused':
        console.log('[UIManager] Setting control panel to paused (showing resume/terminate buttons)');
        panel.classList.remove('hidden');
        panel.classList.remove('error-state');
        cancelBtn?.classList.add('hidden');
        resumeBtn?.classList.remove('hidden');
        terminateBtn?.classList.remove('hidden');
        break;
        
      case 'error':
        console.log('[UIManager] Setting control panel to error (keeping cancel/terminate buttons visible)');
        panel.classList.remove('hidden');
        panel.classList.add('error-state');
        cancelBtn?.classList.remove('hidden');
        resumeBtn?.classList.add('hidden');
        terminateBtn?.classList.remove('hidden');
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
      console.log('[UIManager] Minimum control panel visibility period ended');
    }, 2000);
  }

  clearActivityLog() {
    if (this.elements.activityLog) {
      this.elements.activityLog.innerHTML = '';
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
              <div class="task-description">Search information about browser-use and browser-use-webui, write a brief report</div>
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
    this.scrollActivityToBottom();
  }

  addActivityLog(activityData) {
    
    // Filter out "done" status messages from UI display only
    const agentStatus = activityData.agent_status || activityData.status || '';
    const agentMsg = activityData.agent_msg || activityData.message || '';
    
    
    // Filter done messages that are just status updates without meaningful content
    if (agentStatus.toLowerCase() === 'done') {
      return;
    }
    
    const activityItem = this.createActivityItem(activityData);
    
    if (this.elements.activityLog) {
      // Remove welcome message if present
      const welcomeMsg = this.elements.activityLog.querySelector('.welcome-message');
      if (welcomeMsg) {
        welcomeMsg.remove();
      }
      
      this.elements.activityLog.appendChild(activityItem);
      activityItem.classList.add('fade-in');
    }
  }

  addActivityItem(data) {
    const activityItem = this.createActivityItem(data);
    
    if (this.elements.activityLog) {
      // Remove welcome message if present
      const welcomeMsg = this.elements.activityLog.querySelector('.welcome-message');
      if (welcomeMsg) {
        welcomeMsg.remove();
      }
      
      this.elements.activityLog.appendChild(activityItem);
      activityItem.classList.add('fade-in');
      this.scrollActivityToBottom();
    }
  }

  createActivityItem(data) {
    const item = document.createElement('div');
    
    // Extract activity data with correct keys
    const agentName = data.agent_name || 'system';
    const agentStatus = data.agent_status || data.status || 'info';
    const agentMsg = data.agent_msg || data.message || data.action_description || 'No description';
    const timestamp = new Date(data.timestamp || Date.now()).toLocaleTimeString();
    
    // Determine if this is a user message (should be on the right)
    const isUser = agentName.toLowerCase() === 'user';
    
    // Set CSS classes based on agent type and status
    item.className = `activity-item ${isUser ? 'user-message' : 'agent-message'} ${agentStatus}`;
    
    // Create the message structure similar to chat interface
    item.innerHTML = `
      <div class="message-container ${isUser ? 'user-container' : 'agent-container'}">
        <div class="message-header">
          <span class="agent-name">${agentName}</span>
          <span class="message-time">${timestamp}</span>
        </div>
        <div class="message-bubble ${isUser ? 'user-bubble' : 'agent-bubble'}">
          <div class="message-status">
            <span class="status-indicator ${agentStatus}">${this.getStatusIcon(agentStatus)}</span>
            <span class="status-text">${agentStatus}</span>
          </div>
          <div class="message-content">
            ${this.formatActivityContent(agentMsg)}
          </div>
        </div>
      </div>
    `;
    
    return item;
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
        
        // Pre-process file:// markdown links since markdown-it doesn't recognize them
        const markdownFileLinkRegex = /\[([^\]]+)\]\((file:\/\/[^)]+)\)/g;
        formattedContent = formattedContent.replace(markdownFileLinkRegex, (match, linkText, fileUrl) => {
          // Convert to HTML format that markdown-it will preserve
          return `<a href="${fileUrl}" class="file-link-markdown">${linkText}</a>`;
        });
        
        // Parse markdown
        const htmlContent = md.render(formattedContent);
        
        // Post-process to handle local file path links (Windows paths and file:// URLs)
        let processedContent = htmlContent;
        
        // Convert our pre-processed file:// links to proper file-link format
        const preProcessedFileLinkRegex = /<a href="(file:\/\/[^"]+)"[^>]*class="file-link-markdown"[^>]*>([^<]*)<\/a>/g;
        processedContent = processedContent.replace(preProcessedFileLinkRegex, (match, fileUrl, linkText) => {
          try {
            // Decode and fix the file URL
            let decodedUrl = decodeURIComponent(fileUrl);
            let cleanPath = decodedUrl.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
            cleanPath = cleanPath.replace(/\\/g, '/');
            
            // Ensure path starts with / for Unix paths or has drive letter for Windows
            if (!cleanPath.startsWith('/') && !cleanPath.match(/^[A-Za-z]:/)) {
              cleanPath = '/' + cleanPath;
            }
            
            // Recreate proper file URL - always use triple slash for proper format
            let fixedUrl = cleanPath.match(/^[A-Za-z]:/) ?
              `file:///${cleanPath}` :
              `file://${cleanPath}`;
            
            
            return `<a href="#" class="file-link" data-file-path="${fixedUrl}" title="Click to open file">${linkText}</a>`;
          } catch (error) {
            console.error('[UIManager] Error processing pre-processed file:// link:', error);
            return match;
          }
        });
        
        // Detect and convert local Windows file path links
        const windowsPathLinkRegex = /<a href="([A-Za-z]:\\[^"]+\.html?)"([^>]*)>([^<]*)<\/a>/g;
        processedContent = processedContent.replace(windowsPathLinkRegex, (match, filePath, attributes, linkText) => {
          
          try {
            // Convert Windows path to file:// URL
            let normalizedPath = filePath.replace(/\\/g, '/');
            let fileUrl = `file:///${normalizedPath}`;
            
            
            return `<a href="#" class="file-link" data-file-path="${fileUrl}" title="Click to open file: ${filePath}"${attributes}>${linkText}</a>`;
          } catch (error) {
            console.error('[UIManager] Error converting Windows path:', error);
            return match; // Return original if conversion fails
          }
        });
        
        // Detect and convert file:// protocol links
        const fileProtocolLinkRegex = /<a href="(file:\/\/[^"]+\.html?)"([^>]*)>([^<]*)<\/a>/g;
        processedContent = processedContent.replace(fileProtocolLinkRegex, (match, fileUrl, attributes, linkText) => {
          
          try {
            // Decode and fix the file URL
            let decodedUrl = decodeURIComponent(fileUrl);
            let cleanPath = decodedUrl.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
            cleanPath = cleanPath.replace(/\\/g, '/');
            
            // Recreate proper file URL
            let fixedUrl = cleanPath.match(/^[A-Za-z]:/) ?
              `file:///${cleanPath}` :
              `file://${cleanPath}`;
            
            
            return `<a href="#" class="file-link" data-file-path="${fixedUrl}" title="Click to open file"${attributes}>${linkText}</a>`;
          } catch (error) {
            console.error('[UIManager] Error processing file:// link:', error);
            return match; // Return original if conversion fails
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
    } else {
    }
    
    // Fallback: Enhanced basic markdown-like formatting
    
    // Task lists (checkboxes)
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
    
    // Handle markdown-style local file links first [text](local_path) and [text](file://path)
    const markdownLocalLinkRegex = /\[([^\]]+)\]\(([A-Za-z]:\\[^)]+\.html?)\)/g;
    const markdownFileLinkRegex = /\[([^\]]+)\]\((file:\/\/[^)]+\.html?)\)/g;
    
    // Handle [text](local_path) format - Enhanced path detection and conversion
    formattedContent = formattedContent.replace(markdownLocalLinkRegex, (match, linkText, filePath) => {
      try {
        // Normalize path separators and handle absolute paths
        let normalizedPath = filePath.replace(/\\/g, '/');
        
        // Ensure proper file:// URL format
        let fileUrl;
        if (normalizedPath.startsWith('/')) {
          // Unix-style absolute path
          fileUrl = `file://${normalizedPath}`;
        } else if (normalizedPath.match(/^[A-Za-z]:/)) {
          // Windows-style absolute path (C:, D:, etc.)
          fileUrl = `file:///${normalizedPath}`;
        } else {
          // Relative path - make it absolute based on workspace
          fileUrl = `file:///${normalizedPath}`;
        }
        
        
        return `<a href="#" class="file-link" data-file-path="${fileUrl}" title="Click to open file: ${filePath}">${linkText}</a>`;
      } catch (error) {
        console.error('[UIManager] Error converting markdown local link:', error);
        return match;
      }
    });
    
    // Handle [text](file://path) format
    formattedContent = formattedContent.replace(markdownFileLinkRegex, (match, linkText, fileUrl) => {
      try {
        // Decode and fix the file URL
        let decodedUrl = decodeURIComponent(fileUrl);
        let cleanPath = decodedUrl.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
        cleanPath = cleanPath.replace(/\\/g, '/');
        
        // Recreate proper file URL
        let fixedUrl = cleanPath.match(/^[A-Za-z]:/) ?
          `file:///${cleanPath}` :
          `file://${cleanPath}`;
        
        
        return `<a href="#" class="file-link" data-file-path="${fixedUrl}" title="Click to open file">${linkText}</a>`;
      } catch (error) {
        console.error('[UIManager] Error processing markdown file:// link:', error);
        return match;
      }
    });
    
    
    // Handle [text](file://path) format
    formattedContent = formattedContent.replace(markdownFileLinkRegex, (match, linkText, fileUrl) => {
      try {
        // Decode and fix the file URL
        let decodedUrl = decodeURIComponent(fileUrl);
        let cleanPath = decodedUrl.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
        cleanPath = cleanPath.replace(/\\/g, '/');
        
        // Recreate proper file URL
        let fixedUrl = cleanPath.match(/^[A-Za-z]:/) ?
          `file:///${cleanPath}` :
          `file://${cleanPath}`;
        
        
        return `<a href="#" class="file-link" data-file-path="${fixedUrl}" title="Click to open file">${linkText}</a>`;
      } catch (error) {
        console.error('[UIManager] Error processing markdown file:// link:', error);
        return match;
      }
    });
    
    // Convert URLs to links - Enhanced for file:// protocol handling
    const httpUrlRegex = /(https?:\/\/[^\s]+)/g;
    const fileUrlRegex = /(file:\/\/[^\s]+)/g;
    
    // Handle HTTP/HTTPS URLs normally
    formattedContent = formattedContent.replace(httpUrlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    
    // Handle file:// URLs with custom class for special handling
    formattedContent = formattedContent.replace(fileUrlRegex, (match, fileUrl) => {
      try {
        // Immediately decode and fix the file URL
        let decodedUrl = decodeURIComponent(fileUrl);
        
        // Remove file:// protocol and normalize path
        let cleanPath = decodedUrl.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
        cleanPath = cleanPath.replace(/\\/g, '/');
        
        // Recreate proper file URL
        let fixedUrl = cleanPath.match(/^[A-Za-z]:/) ?
          `file:///${cleanPath}` :
          `file://${cleanPath}`;
        
        
        return `<a href="#" class="file-link" data-file-path="${fixedUrl}" title="Click to open file">${fixedUrl}</a>`;
      } catch (error) {
        console.error('[UIManager] Error processing file URL in markdown:', error);
        return `<a href="#" class="file-link" data-file-path="${fileUrl}" title="Click to open file">${fileUrl}</a>`;
      }
    });
    
    
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

  // Modal Management
  displayHistoryModal(sessions) {
    if (!this.elements.historyList) return;
    
    this.elements.historyList.innerHTML = '';
    
    if (sessions.length === 0) {
      this.elements.historyList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <div class="empty-state-title">No Sessions Found</div>
          <div class="empty-state-description">Create a new session to get started.</div>
        </div>
      `;
    } else {
      sessions.forEach(session => {
        const item = this.createHistoryItem(session);
        this.elements.historyList.appendChild(item);
      });
    }
    
    this.openModal('history');
  }

  createHistoryItem(session) {
    const item = document.createElement('div');
    item.className = 'history-item';
    
    const createdAt = new Date(session.createdAt || session.lastUpdated).toLocaleString();
    const taskCount = session.taskHistory?.length || 0;
    
    item.innerHTML = `
      <div class="history-item-header">
        <span class="history-session-id">${session.sessionId}</span>
        <span class="history-timestamp">${createdAt}</span>
      </div>
      <div class="history-task">${taskCount} task(s)</div>
      <div class="history-status">
        <span class="status-dot ${session.status || 'active'}"></span>
        ${session.status || 'active'}
      </div>
    `;
    
    item.addEventListener('click', () => {
      this.loadSession(session.sessionId);
      this.closeModal();
    });
    
    return item;
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

  async displaySettingsModal() {
    // Load current backend URL from API client
    if (this.elements.backendUrl && this.apiClient) {
      this.elements.backendUrl.value = this.apiClient.baseURL;
    }
    
    this.openModal('settings');
  }


  updateLLMProfileSelect() {
    if (!this.elements.llmProfileSelect) return;
    
    const select = this.elements.llmProfileSelect;
    select.innerHTML = ''; // Remove default option
    
    if (this.state.llmProfiles.length === 0) {
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
      
      // Add actual profiles
      this.state.llmProfiles.forEach(profile => {
        const option = document.createElement('option');
        option.value = profile.profile_name;
        option.textContent = profile.profile_name;
        if (profile.is_default) {
          option.selected = true;
        }
        select.appendChild(option);
      });
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
    
    const modal = this.createWarningModal({
      title,
      message,
      details: isConfigureAction
        ? 'LLM profiles contain the configuration for AI models (like OpenAI, Claude, etc.) that will process your tasks.'
        : null,
      buttons: isConfigureAction
        ? [
            {
              text: 'Open Settings',
              style: 'primary',
              action: () => {
                this.closeWarningModal();
                this.handleShowSettings();
              }
            },
            {
              text: 'Cancel',
              style: 'secondary',
              action: () => {
                this.closeWarningModal();
              }
            }
          ]
        : [
            {
              text: 'Open Settings',
              style: 'secondary',
              action: () => {
                this.closeWarningModal();
                this.handleShowSettings();
              }
            },
            {
              text: 'OK',
              style: 'primary',
              action: () => {
                this.closeWarningModal();
                this.elements.llmProfileSelect?.focus();
              }
            }
          ]
    });
    
    document.body.appendChild(modal);
  }

  updateSettingsDisplay() {
    // Update LLM profiles list in settings
    if (this.elements.llmProfilesList) {
      this.elements.llmProfilesList.innerHTML = '';
      
      this.state.llmProfiles.forEach(profile => {
        const item = this.createProfileItem(profile, 'llm');
        this.elements.llmProfilesList.appendChild(item);
      });
    }
    
    // Update MCP profiles list in settings
    if (this.elements.mcpFilesList) {
      this.elements.mcpFilesList.innerHTML = '';
      
      this.state.mcpProfiles.forEach(profile => {
        const item = this.createProfileItem(profile, 'mcp');
        this.elements.mcpFilesList.appendChild(item);
      });
    }
  }

  createProfileItem(profile, type) {
    const item = document.createElement('div');
    item.className = 'profile-item';
    
    const isLLM = type === 'llm';
    const name = profile.profile_name;
    const details = isLLM ? 
      `${profile.provider} - ${profile.model}` :
      `${profile.server_name || 'Unknown'}`;
    
    // Add active status
    const activeStatus = profile.is_active ? 'Active' : 'Inactive';
    const activeClass = profile.is_active ? 'active' : 'inactive';
    
    item.innerHTML = `
      <div class="profile-header">
        <span class="profile-name">${name}</span>
        <div class="profile-badges">
          ${isLLM && profile.is_default ? '<span class="profile-default">Default</span>' : ''}
          <span class="profile-status ${activeClass}">${activeStatus}</span>
        </div>
        <div class="profile-actions">
          <button class="profile-btn edit-btn" data-name="${name}" data-type="${type}">Edit</button>
          <button class="profile-btn danger delete-btn" data-name="${name}" data-type="${type}">Delete</button>
        </div>
      </div>
      <div class="profile-details">${details}</div>
    `;
    
    // Add event listeners
    const editBtn = item.querySelector('.edit-btn');
    const deleteBtn = item.querySelector('.delete-btn');
    
    editBtn?.addEventListener('click', () => {
      this.editProfile(name, type);
    });
    
    deleteBtn?.addEventListener('click', () => {
      this.deleteProfile(name, type);
    });
    
    return item;
  }

  async editProfile(name, type) {
    this.showNotification(`Edit ${type.toUpperCase()} profile '${name}' coming soon...`, 'info');
    // TODO: Implement profile editing form
    console.log(`[UIManager] Edit ${type} profile:`, name);
  }

  async deleteProfile(name, type) {
    if (!confirm(`Are you sure you want to delete the ${type.toUpperCase()} profile '${name}'?`)) {
      return;
    }
    
    try {
      this.showLoading(`Deleting ${type} profile...`);
      
      if (type === 'llm') {
        await this.apiClient.deleteLLMProfile(name);
      } else {
        await this.apiClient.deleteMCPProfile(name);
      }
      
      // Refresh the settings data
      await this.loadSettingsData();
      
      this.hideLoading();
      this.showNotification(`${type.toUpperCase()} profile '${name}' deleted successfully`, 'success');
    } catch (error) {
      this.hideLoading();
      this.showNotification(`Failed to delete ${type} profile: ${error.message}`, 'error');
    }
  }

  openModal(modalName) {
    const modal = document.getElementById(`${modalName}-modal`);
    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('scale-in');
      this.state.currentModal = modalName;
    }
  }

  closeModal() {
    if (this.state.currentModal) {
      const modal = document.getElementById(`${this.state.currentModal}-modal`);
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('scale-in');
      }
      this.state.currentModal = null;
    }
  }

  // History Modal Handlers
  setupHistoryModalHandlers() {
    // View More Tasks button
    this.elements.viewMoreTasksBtn?.addEventListener('click', this.handleViewMoreTasks.bind(this));
    
    // Back to Recent button
    this.elements.backToRecentBtn?.addEventListener('click', this.handleBackToRecent.bind(this));
    
    // Search and filter
    this.elements.sessionSearch?.addEventListener('input', this.handleSessionSearch.bind(this));
    this.elements.sessionFilter?.addEventListener('change', this.handleSessionFilter.bind(this));
    
    // Pagination
    this.elements.prevPageBtn?.addEventListener('click', this.handlePrevPage.bind(this));
    this.elements.nextPageBtn?.addEventListener('click', this.handleNextPage.bind(this));
    
    console.log('[UIManager] History modal handlers bound');
  }

  async handleViewMoreTasks() {
    try {
      console.log('[UIManager] View More Tasks clicked');
      this.showLoading('Loading all sessions...');
      
      // Switch to all sessions view
      this.state.historyMode = 'all';
      console.log('[UIManager] Set history mode to "all"');
      
      await this.loadAllSessions();
      console.log('[UIManager] All sessions loaded, switching view');
      
      this.displayAllSessionsView();
      console.log('[UIManager] All sessions view displayed');
      
      this.hideLoading();
    } catch (error) {
      this.hideLoading();
      console.error('[UIManager] Error in handleViewMoreTasks:', error);
      this.showNotification(`Failed to load sessions: ${error.message}`, 'error');
    }
  }

  handleBackToRecent() {
    this.state.historyMode = 'recent';
    this.displayRecentTasksView();
  }

  handleSessionSearch(event) {
    this.state.searchQuery = event.target.value.trim().toLowerCase();
    this.filterAndDisplaySessions();
  }

  handleSessionFilter(event) {
    this.state.statusFilter = event.target.value;
    this.filterAndDisplaySessions();
  }

  handlePrevPage() {
    if (this.state.currentPage > 1) {
      this.state.currentPage--;
      this.filterAndDisplaySessions();
    }
  }

  handleNextPage() {
    if (this.state.currentPage < this.state.totalPages) {
      this.state.currentPage++;
      this.filterAndDisplaySessions();
    }
  }

  // History Data Loading Methods
  async loadRecentTasks() {
    try {
      console.log('[UIManager] Loading recent tasks...');
      const response = await this.apiClient.getRecentTasks();
      
      // Handle API response structure: { tasks: [...], total_count: ..., limit: ... }
      let tasks = [];
      if (response && response.tasks && Array.isArray(response.tasks)) {
        tasks = response.tasks;
      } else if (response && Array.isArray(response)) {
        tasks = response;
      } else if (response && response.data && Array.isArray(response.data)) {
        tasks = response.data;
      }
      
      // Take only the first 3 most recent tasks
      this.state.recentTasks = tasks.slice(0, 3);
      console.log('[UIManager] Recent tasks loaded:', this.state.recentTasks.length);
      
      return this.state.recentTasks;
    } catch (error) {
      console.error('[UIManager] Failed to load recent tasks:', error);
      this.state.recentTasks = [];
      throw error;
    }
  }

  async loadAllSessions() {
    try {
      console.log('[UIManager] Loading all sessions...');
      const response = await this.apiClient.getAllSessions();
      
      // Handle API response structure: { sessions: [...], total_count: ..., limit: ..., offset: ... }
      let sessions = [];
      if (response && response.sessions && Array.isArray(response.sessions)) {
        sessions = response.sessions;
      } else if (response && Array.isArray(response)) {
        sessions = response;
      } else if (response && response.data && Array.isArray(response.data)) {
        sessions = response.data;
      }
      
      this.state.allSessions = sessions;
      console.log('[UIManager] All sessions loaded:', this.state.allSessions.length);
      
      return this.state.allSessions;
    } catch (error) {
      console.error('[UIManager] Failed to load all sessions:', error);
      this.state.allSessions = [];
      throw error;
    }
  }

  // History Display Methods
  displayHistoryModal() {
    if (this.state.historyMode === 'recent') {
      this.displayRecentTasksView();
    } else {
      this.displayAllSessionsView();
    }
    this.openModal('history');
  }

  displayRecentTasksView() {
    console.log('[UIManager] Switching to recent tasks view');
    
    // Show recent tasks section and hide all sessions section
    if (this.elements.recentTasksList && this.elements.allSessionsSection) {
      const recentParent = this.elements.recentTasksList.parentElement;
      if (recentParent) {
        recentParent.classList.remove('hidden');
        recentParent.style.display = 'block';
        console.log('[UIManager] Showed recent tasks section');
      }
      this.elements.allSessionsSection.classList.add('hidden');
      this.elements.allSessionsSection.style.display = 'none';
      console.log('[UIManager] Hidden all sessions section');
    }
    
    this.renderRecentTasks();
  }

  displayAllSessionsView() {
    console.log('[UIManager] Switching to all sessions view');
    console.log('[UIManager] Elements check:', {
      recentTasksList: !!this.elements.recentTasksList,
      allSessionsSection: !!this.elements.allSessionsSection,
      recentTasksParent: !!this.elements.recentTasksList?.parentElement
    });
    
    // Hide recent tasks section and show all sessions section
    if (this.elements.recentTasksList && this.elements.allSessionsSection) {
      const recentParent = this.elements.recentTasksList.parentElement;
      if (recentParent) {
        recentParent.style.display = 'none';
        recentParent.classList.add('hidden');
        console.log('[UIManager] Hidden recent tasks section');
      }
      
      // Remove hidden class and set display block
      this.elements.allSessionsSection.classList.remove('hidden');
      this.elements.allSessionsSection.style.display = 'block';
      console.log('[UIManager] Showed all sessions section - removed hidden class and set display block');
      
      // Debug: Check computed styles
      const computedStyle = window.getComputedStyle(this.elements.allSessionsSection);
      console.log('[UIManager] All sessions section computed display:', computedStyle.display);
      console.log('[UIManager] All sessions section classList:', this.elements.allSessionsSection.classList.toString());
      
    } else {
      console.error('[UIManager] Missing elements for view switching:', {
        recentTasksList: !!this.elements.recentTasksList,
        allSessionsSection: !!this.elements.allSessionsSection
      });
    }
    
    // Reset search and filter
    this.state.currentPage = 1;
    this.state.searchQuery = '';
    this.state.statusFilter = 'all';
    
    if (this.elements.sessionSearch) {
      this.elements.sessionSearch.value = '';
    }
    if (this.elements.sessionFilter) {
      this.elements.sessionFilter.value = 'all';
    }
    
    console.log('[UIManager] About to filter and display sessions');
    this.filterAndDisplaySessions();
  }

  renderRecentTasks() {
    if (!this.elements.recentTasksList) return;
    
    this.elements.recentTasksList.innerHTML = '';
    
    if (this.state.recentTasks.length === 0) {
      this.elements.recentTasksList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <div class="empty-state-title">No Recent Tasks</div>
          <div class="empty-state-description">Start a new task to see it here.</div>
        </div>
      `;
      return;
    }
    
    this.state.recentTasks.forEach(task => {
      const taskItem = this.createTaskItem(task);
      this.elements.recentTasksList.appendChild(taskItem);
    });
  }

  filterAndDisplaySessions() {
    if (!this.elements.allSessionsList) {
      console.error('[UIManager] allSessionsList element not found');
      return;
    }
    
    console.log('[UIManager] Filtering sessions. Total sessions:', this.state.allSessions.length);
    console.log('[UIManager] Search query:', this.state.searchQuery);
    console.log('[UIManager] Status filter:', this.state.statusFilter);
    
    let filteredSessions = [...this.state.allSessions]; // Create copy
    
    // Apply search filter
    if (this.state.searchQuery) {
      filteredSessions = filteredSessions.filter(session =>
        session.session_id.toLowerCase().includes(this.state.searchQuery) ||
        (session.description && session.description.toLowerCase().includes(this.state.searchQuery))
      );
    }
    
    // Apply status filter
    if (this.state.statusFilter !== 'all') {
      filteredSessions = filteredSessions.filter(session =>
        (session.status || 'active').toLowerCase() === this.state.statusFilter.toLowerCase()
      );
    }
    
    console.log('[UIManager] Filtered sessions count:', filteredSessions.length);
    
    // Calculate pagination
    const totalSessions = filteredSessions.length;
    this.state.totalPages = Math.ceil(totalSessions / this.state.pageSize);
    
    // Ensure current page is valid
    if (this.state.currentPage > this.state.totalPages) {
      this.state.currentPage = Math.max(1, this.state.totalPages);
    }
    
    // Get sessions for current page
    const startIndex = (this.state.currentPage - 1) * this.state.pageSize;
    const endIndex = startIndex + this.state.pageSize;
    const paginatedSessions = filteredSessions.slice(startIndex, endIndex);
    
    console.log('[UIManager] Paginated sessions for display:', paginatedSessions.length);
    
    // Render sessions
    this.renderSessionsList(paginatedSessions);
    
    // Update pagination controls
    this.updatePaginationControls();
  }

  renderSessionsList(sessions) {
    if (!this.elements.allSessionsList) {
      console.error('[UIManager] allSessionsList element not found for rendering');
      return;
    }
    
    console.log('[UIManager] Rendering sessions list with', sessions.length, 'sessions');
    
    this.elements.allSessionsList.innerHTML = '';
    
    if (sessions.length === 0) {
      console.log('[UIManager] No sessions to display, showing empty state');
      this.elements.allSessionsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">No Sessions Found</div>
          <div class="empty-state-description">Try adjusting your search or filter criteria.</div>
        </div>
      `;
      return;
    }
    
    sessions.forEach((session, index) => {
      console.log(`[UIManager] Creating session item ${index + 1}:`, session.session_id);
      const sessionItem = this.createSessionItem(session);
      this.elements.allSessionsList.appendChild(sessionItem);
    });
    
    console.log('[UIManager] Sessions list rendered successfully');
  }

  updatePaginationControls() {
    // Update pagination buttons
    if (this.elements.prevPageBtn) {
      this.elements.prevPageBtn.disabled = this.state.currentPage <= 1;
    }
    
    if (this.elements.nextPageBtn) {
      this.elements.nextPageBtn.disabled = this.state.currentPage >= this.state.totalPages;
    }
    
    // Update page info
    if (this.elements.pageInfo) {
      if (this.state.totalPages === 0) {
        this.elements.pageInfo.textContent = 'No results';
      } else {
        this.elements.pageInfo.textContent = `Page ${this.state.currentPage} of ${this.state.totalPages}`;
      }
    }
  }

  // Item Creation Methods
  createTaskItem(task) {
    const item = document.createElement('div');
    item.className = 'recent-task-item';
    
    const sessionId = task.session_id || 'Unknown';
    const taskDesc = task.description || task.task_description || 'No description';
    const timestamp = new Date(task.created_at || task.timestamp || Date.now()).toLocaleString();
    const status = task.status || 'completed';
    
    item.innerHTML = `
      <div class="task-item-header">
        <div class="task-session-id">${sessionId}</div>
        <div class="task-timestamp">${timestamp}</div>
      </div>
      <div class="task-description">${this.truncateText(taskDesc, 100)}</div>
      <div class="task-status">
        <span class="status-dot ${status}"></span>
        <span class="status-text">${status}</span>
      </div>
    `;
    
    item.addEventListener('click', () => {
      this.handleTaskItemClick(task);
    });
    
    return item;
  }

  createSessionItem(session) {
    const item = document.createElement('div');
    item.className = 'session-item';
    
    const sessionId = session.session_id || 'Unknown';
    const createdAt = new Date(session.created_at || session.timestamp || Date.now()).toLocaleString();
    const lastActivity = session.last_activity ? new Date(session.last_activity).toLocaleString() : 'No activity';
    const taskCount = session.task_count || 0;
    const status = session.status || 'active';
    
    item.innerHTML = `
      <div class="session-item-header">
        <div class="session-id">${sessionId}</div>
        <div class="session-timestamp">${createdAt}</div>
      </div>
      <div class="session-details">
        <div class="session-info">
          <span class="session-task-count">${taskCount} task(s)</span>
          <span class="session-last-activity">Last: ${lastActivity}</span>
        </div>
        <div class="session-status">
          <span class="status-dot ${status}"></span>
          <span class="status-text">${status}</span>
        </div>
      </div>
    `;
    
    // Add enhanced click handler with debugging
    item.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.handleSessionItemClick(session);
    });
    
    // Add visual feedback for clickability
    item.style.cursor = 'pointer';
    item.setAttribute('title', `Click to load session: ${sessionId}`);
    
    return item;
  }

  // Click Handlers
  async handleTaskItemClick(task) {
    try {
      
      const sessionId = task.session_id;
      if (!sessionId) {
        console.error('[UIManager] No session ID found in task data:', task);
        this.showNotification('Invalid task - no session ID found', 'error');
        return;
      }
      
      
      // Close the modal first
      this.closeModal();
      
      // Load the session and show logs
      await this.loadSessionAndShowLogs(sessionId);
      
    } catch (error) {
      console.error('[UIManager] Error in handleTaskItemClick:', error);
      this.showNotification(`Failed to load task session: ${error.message}`, 'error');
    }
  }

  async handleSessionItemClick(session) {
    try {
      
      const sessionId = session.session_id;
      if (!sessionId) {
        console.error('[UIManager] No session ID found in session data:', session);
        this.showNotification('Invalid session - no session ID found', 'error');
        return;
      }
      
      
      // Close the modal first
      this.closeModal();
      
      // Load the session and show logs
      await this.loadSessionAndShowLogs(sessionId);
      
    } catch (error) {
      console.error('[UIManager] Error in handleSessionItemClick:', error);
      this.showNotification(`Failed to load session: ${error.message}`, 'error');
    }
  }

  async loadSessionAndShowLogs(sessionId) {
    // Check if task is running
    if (this.state.isTaskRunning) {
      const canProceed = await this.showTaskRunningWarning('load a different session');
      if (!canProceed) return;
    }
    
    try {
      this.showLoading('Loading session...');
      
      
      // Load the session in session manager
      const success = await this.sessionManager.loadSession(sessionId);
      
      if (success) {
        // Session manager will trigger the session loaded event
        // which will update the UI automatically
        this.showNotification('Session loaded successfully', 'success');
      } else {
        this.showNotification('Failed to load session - session may not exist', 'error');
      }
      
      this.hideLoading();
    } catch (error) {
      console.error('[UIManager] Error in loadSessionAndShowLogs:', error);
      this.hideLoading();
      this.showNotification(`Failed to load session: ${error.message}`, 'error');
    }
  }

  // Utility Methods
  truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
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

  // Initialization
  async initialize() {
    try {
      this.showLoading('Initializing VibeSurf...');
      
      // Load settings data
      await this.loadSettingsData();
      
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

  // Cleanup
  destroy() {
    // Stop task status monitoring
    this.stopTaskStatusMonitoring();
    
    // Remove event listeners if needed
    this.state.currentModal = null;
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfUIManager = VibeSurfUIManager;
}