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
    
    this.bindElements();
    this.initializeManagers();
    this.bindEvents();
    this.setupSessionListeners();
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
      sendBtn: document.getElementById('send-btn'),
      
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
      
      // Initialize other managers
      this.settingsManager = new VibeSurfSettingsManager(this.apiClient);
      this.historyManager = new VibeSurfHistoryManager(this.apiClient);
      this.fileManager = new VibeSurfFileManager(this.sessionManager);
      
      // Set up inter-manager communication
      this.setupManagerEvents();
      
      console.log('[UIManager] All specialized managers initialized');
    } catch (error) {
      console.error('[UIManager] Failed to initialize managers:', error);
      this.showNotification('Failed to initialize UI components', 'error');
    }
  }

  setupManagerEvents() {
    // Settings Manager Events
    this.settingsManager.on('profilesUpdated', () => {
      this.updateLLMProfileSelect();
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
      const remainingTime = 1000;
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
    this.showNotification(`Task error: ${data.error}`, 'error');
    
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
    
    // Update file manager state
    this.fileManager.setEnabled(!isRunning);
    
    // Also disable header buttons when task is running
    const headerButtons = [
      this.elements.newSessionBtn,
      this.elements.historyBtn,
      this.elements.settingsBtn
    ];
    
    headerButtons.forEach(button => {
      if (button) {
        button.disabled = isRunning;
        if (isRunning) {
          button.classList.add('task-running-disabled');
          button.setAttribute('title', 'Disabled while task is running');
        } else {
          button.classList.remove('task-running-disabled');
          button.removeAttribute('title');
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
    
    try {
      // Immediately clear welcome message and show user request
      this.clearWelcomeMessage();
      
      const taskData = {
        task_description: taskDescription,
        llm_profile_name: llmProfile
      };
      
      // Add uploaded files path if any
      const filePath = this.fileManager.getUploadedFilesForTask();
      if (filePath) {
        taskData.upload_files_path = filePath;
        console.log('[UIManager] Set upload_files_path to:', filePath);
      }
      
      console.log('[UIManager] Complete task data being submitted:', JSON.stringify(taskData, null, 2));
      await this.sessionManager.submitTask(taskData);
      
      // Clear uploaded files after successful task submission
      this.fileManager.clearUploadedFiles();
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
      
      // Bind copy button functionality
      this.bindCopyButtonEvent(activityItem, activityData);
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
      console.log('[UIManager] navigator.clipboard available:', !!navigator.clipboard);
      console.log('[UIManager] writeText method available:', !!(navigator.clipboard && navigator.clipboard.writeText));
      console.log('[UIManager] Document has focus:', document.hasFocus());
      
      // Try multiple clipboard methods
      let copySuccess = false;
      let lastError = null;
      
      // Method 1: Chrome extension messaging approach
      try {
        console.log('[UIManager] Trying Chrome extension messaging approach...');
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
        console.log('[UIManager] Copied using Chrome extension messaging');
      } catch (extensionError) {
        console.warn('[UIManager] Chrome extension messaging failed:', extensionError);
        lastError = extensionError;
      }
      
      // Method 2: Modern clipboard API (if extension method failed)
      if (!copySuccess && navigator.clipboard && navigator.clipboard.writeText) {
        try {
          console.log('[UIManager] Trying modern clipboard API...');
          await navigator.clipboard.writeText(messageText);
          copySuccess = true;
          console.log('[UIManager] Copied using modern clipboard API');
        } catch (clipboardError) {
          console.warn('[UIManager] Modern clipboard API failed:', clipboardError);
          lastError = clipboardError;
        }
      }
      
      // Method 3: Fallback using execCommand
      if (!copySuccess) {
        try {
          console.log('[UIManager] Trying execCommand fallback...');
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
            console.log('[UIManager] Copied using execCommand fallback');
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
        console.log('[UIManager] Copy operation completed successfully');
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
        return '';
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

  updateLLMProfileSelect() {
    if (!this.elements.llmProfileSelect) return;
    
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
      
      // Add actual profiles
      profiles.forEach(profile => {
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
    
    const options = isConfigureAction
      ? {
          confirmText: 'Open Settings',
          cancelText: 'Cancel',
          onConfirm: () => {
            this.handleShowSettings();
          }
        }
      : {
          confirmText: 'OK',
          cancelText: 'Open Settings',
          onConfirm: () => {
            this.elements.llmProfileSelect?.focus();
          },
          onCancel: () => {
            this.handleShowSettings();
          }
        };
    
    this.modalManager.showWarningModal(title, message, options);
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
      
      // Load settings data through settings manager
      await this.settingsManager.loadSettingsData();
      
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
    
    // Cleanup managers
    if (this.settingsManager) {
      // Cleanup settings manager if it has destroy method
      if (typeof this.settingsManager.destroy === 'function') {
        this.settingsManager.destroy();
      }
    }
    
    if (this.historyManager) {
      // Cleanup history manager if it has destroy method
      if (typeof this.historyManager.destroy === 'function') {
        this.historyManager.destroy();
      }
    }
    
    if (this.fileManager) {
      // Cleanup file manager if it has destroy method
      if (typeof this.fileManager.destroy === 'function') {
        this.fileManager.destroy();
      }
    }
    
    if (this.modalManager) {
      // Cleanup modal manager if it has destroy method
      if (typeof this.modalManager.destroy === 'function') {
        this.modalManager.destroy();
      }
    }
    
    // Clear state
    this.state.currentModal = null;
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfUIManager = VibeSurfUIManager;
}