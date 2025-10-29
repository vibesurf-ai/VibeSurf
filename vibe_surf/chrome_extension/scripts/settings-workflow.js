
// Settings Workflow Manager - Handles workflow management functionality
// Extracted from settings-manager.js for better code organization

class VibeSurfSettingsWorkflow {
  constructor(apiClient, emit, userSettingsStorage) {
    this.apiClient = apiClient;
    this.emit = emit;
    this.userSettingsStorage = userSettingsStorage;
    
    // Workflow-specific state
    this.state = {
      workflows: [],
      filteredWorkflows: [],
      workflowSearchQuery: '',
      workflowFilterStatus: 'all',
      currentWorkflow: null,
      runningJobs: new Map(),
      currentScheduleWorkflow: null,
      currentLogsWorkflow: null,
      currentLogsJobId: null,
      currentDeleteWorkflow: null,
      // Event cache to prevent competition between run monitoring and log display
      eventCache: new Map(), // Map<jobId, {events: [], lastFetch: timestamp, isComplete: boolean, workflowId: string}>
      eventSubscribers: new Map(), // Map<jobId, Set<callback functions>>
      // Mapping from workflow ID to job IDs for completed workflows
      workflowJobMapping: new Map(), // Map<workflowId, {jobId: string, completedAt: timestamp, eventCount: number}>
      
      // VibeSurf API Key state
      vibeSurfApiKey: null,
      vibeSurfKeyValid: false
    };
    
    // Schedule state for new interface
    this.scheduleState = {
      selectedTemplate: null,
      scheduleType: 'simple',
      cronExpression: '',
      isValid: false,
      previewTimes: []
    };
    
    this.elements = {};
    this.bindElements();
    this.bindEvents();
  }

  bindElements() {
    console.log('[SettingsWorkflow] bindElements called');
    this.elements = {
      // Workflow Tab
      workflowTab: document.getElementById('workflow-tab'),
      createWorkflowBtn: document.getElementById('create-workflow-btn'),
      importWorkflowBtn: document.getElementById('import-workflow-btn'),
      workflowSearch: document.getElementById('workflow-search'),
      workflowFilter: document.getElementById('workflow-filter'),
      workflowsList: document.getElementById('workflows-list'),
      workflowsLoading: document.getElementById('workflows-loading'),
      
      // Create Workflow Modal
      createWorkflowModal: document.getElementById('create-workflow-modal'),
      workflowNameInput: document.getElementById('workflow-name-input'),
      workflowDescriptionInput: document.getElementById('workflow-description-input'),
      createWorkflowCancel: document.getElementById('create-workflow-cancel'),
      createWorkflowConfirm: document.getElementById('create-workflow-confirm'),
      createWorkflowValidation: document.getElementById('create-workflow-validation'),
      
      // Import Workflow Modal
      importWorkflowModal: document.getElementById('import-workflow-modal'),
      workflowJsonInput: document.getElementById('workflow-json-input'),
      workflowJsonFile: document.getElementById('workflow-json-file'),
      selectJsonFileBtn: document.getElementById('select-json-file-btn'),
      selectedFileInfo: document.getElementById('selected-file-info'),
      selectedFileName: document.getElementById('selected-file-name'),
      clearFileBtn: document.getElementById('clear-file-btn'),
      jsonTextImport: document.getElementById('json-text-import'),
      jsonFileImport: document.getElementById('json-file-import'),
      importWorkflowCancel: document.getElementById('import-workflow-cancel'),
      importWorkflowConfirm: document.getElementById('import-workflow-confirm'),
      importWorkflowValidation: document.getElementById('import-workflow-validation'),
      
      // VibeSurf API Key Modal
      vibeSurfApiKeyModal: document.getElementById('vibesurf-api-key-modal'),
      vibeSurfApiKeyInput: document.getElementById('vibesurf-api-key-input'),
      openVibeSurfLink: document.getElementById('open-vibesurf-link'),
      vibeSurfApiKeyCancel: document.getElementById('vibesurf-api-key-cancel'),
      vibeSurfApiKeyConfirm: document.getElementById('vibesurf-api-key-confirm'),
      vibeSurfApiKeyValidation: document.getElementById('vibesurf-api-key-validation'),
      
      // Workflow Schedule Modal
      workflowScheduleModal: document.getElementById('workflow-schedule-modal'),
      scheduleModalTitle: document.getElementById('schedule-modal-title'),
      scheduleWorkflowName: document.getElementById('schedule-workflow-name'),
      scheduleTypeSelect: document.getElementById('schedule-type-select'),
      presetScheduleGroup: document.getElementById('preset-schedule-group'),
      presetScheduleSelect: document.getElementById('preset-schedule-select'),
      customCronGroup: document.getElementById('custom-cron-group'),
      customCronInput: document.getElementById('custom-cron-input'),
      cronPreview: document.getElementById('cron-preview'),
      cronPreviewTimes: document.getElementById('cron-preview-times'),
      scheduleCancel: document.getElementById('schedule-cancel'),
      scheduleSave: document.getElementById('schedule-save'),
      
      // Workflow Logs Modal
      workflowLogsModal: document.getElementById('workflow-logs-modal'),
      logsModalTitle: document.getElementById('logs-modal-title'),
      logsWorkflowName: document.getElementById('logs-workflow-name'),
      logsJobId: document.getElementById('logs-job-id'),
      logsRefreshBtn: document.getElementById('logs-refresh-btn'),
      logsClearBtn: document.getElementById('logs-clear-btn'),
      logsContainer: document.getElementById('logs-container'),
      logsContent: document.getElementById('logs-content'),
      logsLoading: document.getElementById('logs-loading'),
      logsClose: document.getElementById('logs-close'),
      
      // Workflow Delete Modal
      workflowDeleteModal: document.getElementById('workflow-delete-modal'),
      deleteWorkflowName: document.getElementById('delete-workflow-name'),
      deleteCancel: document.getElementById('delete-cancel'),
      deleteConfirm: document.getElementById('delete-confirm')
    };
  }

  bindEvents() {
    // Workflow tab events
    this.elements.createWorkflowBtn?.addEventListener('click', this.handleCreateWorkflow.bind(this));
    this.elements.importWorkflowBtn?.addEventListener('click', this.handleImportWorkflow.bind(this));
    this.elements.workflowSearch?.addEventListener('input', this.handleWorkflowSearch.bind(this));
    this.elements.workflowFilter?.addEventListener('change', this.handleWorkflowFilter.bind(this));
    
    // Create Workflow Modal events
    this.elements.createWorkflowCancel?.addEventListener('click', this.hideCreateWorkflowModal.bind(this));
    this.elements.createWorkflowConfirm?.addEventListener('click', this.handleCreateWorkflowConfirm.bind(this));
    
    // Import Workflow Modal events
    this.elements.importWorkflowCancel?.addEventListener('click', this.hideImportWorkflowModal.bind(this));
    this.elements.importWorkflowConfirm?.addEventListener('click', this.handleImportWorkflowConfirm.bind(this));
    this.elements.selectJsonFileBtn?.addEventListener('click', this.handleSelectJsonFile.bind(this));
    this.elements.workflowJsonFile?.addEventListener('change', this.handleJsonFileChange.bind(this));
    this.elements.clearFileBtn?.addEventListener('click', this.handleClearFile.bind(this));
    
    // VibeSurf API Key Modal events
    this.elements.openVibeSurfLink?.addEventListener('click', this.handleOpenVibeSurfLink.bind(this));
    this.elements.vibeSurfApiKeyCancel?.addEventListener('click', this.hideVibeSurfApiKeyModal.bind(this));
    this.elements.vibeSurfApiKeyConfirm?.addEventListener('click', this.handleVibeSurfApiKeyConfirm.bind(this));
    
    // Workflow Schedule Modal events
    this.elements.presetScheduleSelect?.addEventListener('change', this.handleCronExpressionChange.bind(this));
    this.elements.customCronInput?.addEventListener('input', this.handleCronExpressionChange.bind(this));
    this.elements.scheduleCancel?.addEventListener('click', this.hideScheduleModal.bind(this));
    this.elements.scheduleSave?.addEventListener('click', this.handleScheduleSave.bind(this));
    
    // Workflow Logs Modal events
    this.elements.logsRefreshBtn?.addEventListener('click', this.handleLogsRefresh.bind(this));
    this.elements.logsClearBtn?.addEventListener('click', this.handleLogsClear.bind(this));
    this.elements.logsClose?.addEventListener('click', this.hideLogsModal.bind(this));
    
    // Workflow Delete Modal events
    this.elements.deleteCancel?.addEventListener('click', this.hideDeleteModal.bind(this));
    this.elements.deleteConfirm?.addEventListener('click', this.handleDeleteConfirm.bind(this));
    
    // Workflow modal close buttons
    const vibeSurfModalClose = this.elements.vibeSurfApiKeyModal?.querySelector('.modal-close');
    if (vibeSurfModalClose) {
      vibeSurfModalClose.addEventListener('click', this.hideVibeSurfApiKeyModal.bind(this));
    }
    
    const scheduleModalClose = this.elements.workflowScheduleModal?.querySelector('.modal-close');
    if (scheduleModalClose) {
      scheduleModalClose.addEventListener('click', this.hideScheduleModal.bind(this));
    }
    
    const logsModalClose = this.elements.workflowLogsModal?.querySelector('.modal-close');
    if (logsModalClose) {
      logsModalClose.addEventListener('click', this.hideLogsModal.bind(this));
    }
    
    const deleteModalClose = this.elements.workflowDeleteModal?.querySelector('.modal-close');
    if (deleteModalClose) {
      deleteModalClose.addEventListener('click', this.hideDeleteModal.bind(this));
    }
    
    const createModalClose = this.elements.createWorkflowModal?.querySelector('.modal-close');
    if (createModalClose) {
      createModalClose.addEventListener('click', this.hideCreateWorkflowModal.bind(this));
    }
    
    const importModalClose = this.elements.importWorkflowModal?.querySelector('.modal-close');
    if (importModalClose) {
      importModalClose.addEventListener('click', this.hideImportWorkflowModal.bind(this));
    }

    // --- New Schedule Modal Events ---
    const scheduleTypeSelect = document.getElementById('schedule-type-select');
    if (scheduleTypeSelect) {
      scheduleTypeSelect.addEventListener('change', (e) => {
        this.handleScheduleTypeChange(e.target.value);
      });
    }
    
    const inputsToBind = [
      'minutes-interval', 'hours-interval', 'daily-time',
      'weekly-day', 'weekly-time', 'monthly-day', 'monthly-time'
    ];
    
    inputsToBind.forEach(id => {
      const input = document.getElementById(id);
      if (input) {
        const eventType = (id.includes('interval') || id.includes('day')) ? 'input' : 'change';
        input.addEventListener(eventType, () => {
          if (id === 'minutes-interval') this.updateMinutesLabel();
          if (id === 'hours-interval') this.updateHoursLabel();
          this.updateScheduleFromSimpleBuilder();
        });
      }
    });

    const enabledCheckbox = document.getElementById('schedule-enabled');
    if (enabledCheckbox) {
      enabledCheckbox.addEventListener('change', () => {
        console.log('[SettingsWorkflow] Schedule enabled checkbox changed:', {
          checked: enabledCheckbox.checked,
          currentScheduleValid: this.scheduleState.isValid
        });
        
        this.updateScheduleSaveButton(this.scheduleState.isValid);
      });
    }
    
    // Import method radio buttons
    const importMethodRadios = document.querySelectorAll('input[name="import-method"]');
    importMethodRadios.forEach(radio => {
      radio.addEventListener('change', this.handleImportMethodChange.bind(this));
    });
  }

  // Load workflow content when tab is opened
  async loadWorkflowContent() {
    try {
      console.log('[SettingsWorkflow] Loading workflow content...');
      
      // Show loading state
      this.showWorkflowsLoading();
      
      // Check VibeSurf API key first
      const status = await this.checkVibeSurfStatus();
      
      if (status && status.connected && status.key_valid) {
        console.log('[SettingsWorkflow] Valid VibeSurf API key found, loading workflows...');
        // Load workflows from backend
        await this.loadWorkflows();
        console.log('[SettingsWorkflow] Workflow content loaded');
      } else {
        console.log('[SettingsWorkflow] No valid VibeSurf API key, showing setup modal automatically');
        console.log('[SettingsWorkflow] Status details - connected:', status?.connected, 'key_valid:', status?.key_valid);
        // Hide loading and show API key modal
        this.hideWorkflowsLoading();
        this.showVibeSurfApiKeyModal();
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflow content:', error);
      this.hideWorkflowsLoading();
      this.emit('notification', {
        message: 'Failed to load workflows',
        type: 'error'
      });
    }
  }
  
  // Check VibeSurf API key status
  async checkVibeSurfStatus() {
    try {
      console.log('[SettingsWorkflow] Checking VibeSurf status...');
      const response = await this.apiClient.getVibeSurfStatus();
      console.log('[SettingsWorkflow] VibeSurf status response:', response);
      
      this.state.vibeSurfKeyValid = response.connected && response.key_valid;
      this.state.vibeSurfApiKey = response.has_key ? '***' : null;
      
      console.log('[SettingsWorkflow] VibeSurf state updated:', {
        connected: response.connected,
        keyValid: response.key_valid,
        hasKey: response.has_key,
        message: response.message
      });
      
      return response;
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to check VibeSurf status:', error);
      this.state.vibeSurfKeyValid = false;
      this.state.vibeSurfApiKey = null;
      return {
        connected: false,
        key_valid: false,
        has_key: false,
        message: 'Status check failed'
      };
    }
  }
  
  // Show VibeSurf API key modal
  showVibeSurfApiKeyModal() {
    console.log('[SettingsWorkflow] Showing VibeSurf API key modal');
    console.log('[SettingsWorkflow] Modal element exists:', !!this.elements.vibeSurfApiKeyModal);
    
    if (this.elements.vibeSurfApiKeyModal) {
      this.elements.vibeSurfApiKeyModal.classList.remove('hidden');
      
      // Clear previous input and validation
      if (this.elements.vibeSurfApiKeyInput) {
        this.elements.vibeSurfApiKeyInput.value = '';
      }
      this.hideVibeSurfApiKeyValidation();
      
      // Focus on input
      setTimeout(() => {
        if (this.elements.vibeSurfApiKeyInput) {
          this.elements.vibeSurfApiKeyInput.focus();
        }
      }, 100);
      
      console.log('[SettingsWorkflow] VibeSurf API key modal shown successfully');
    } else {
      console.error('[SettingsWorkflow] VibeSurf API key modal element not found!');
    }
  }
  
  // Hide VibeSurf API key modal
  hideVibeSurfApiKeyModal() {
    if (this.elements.vibeSurfApiKeyModal) {
      this.elements.vibeSurfApiKeyModal.classList.add('hidden');
    }
  }
  
  // Handle VibeSurf link open
  handleOpenVibeSurfLink() {
    // Open VibeSurf website in new tab using Chrome extension API
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: 'https://vibe-surf.com/' });
    } else {
      // Fallback for non-extension context
      window.open('https://vibe-surf.com/', '_blank');
    }
  }
  
  // Handle VibeSurf API key confirm
  async handleVibeSurfApiKeyConfirm() {
    const apiKey = this.elements.vibeSurfApiKeyInput?.value?.trim();
    
    if (!apiKey) {
      this.showVibeSurfApiKeyValidation('Please enter a VibeSurf API key', 'error');
      return;
    }

    try {
      this.showVibeSurfApiKeyValidation('Validating API key...', 'info');
      
      const response = await this.apiClient.verifyVibeSurfKey(apiKey);
      
      if (response.valid) {
        this.showVibeSurfApiKeyValidation('API key is valid!', 'success');
        
        // Update state
        this.state.vibeSurfKeyValid = true;
        this.state.vibeSurfApiKey = '***';
        
        // Load workflows after successful validation
        await this.loadWorkflows();
        
        // Close modal after short delay
        setTimeout(() => {
          this.hideVibeSurfApiKeyModal();
        }, 1000);
        
        this.emit('notification', {
          message: 'VibeSurf API key validated and saved successfully',
          type: 'success'
        });
        
      } else {
        this.showVibeSurfApiKeyValidation('Invalid VibeSurf API key. Please check and try again.', 'error');
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to verify VibeSurf API key:', error);
      this.showVibeSurfApiKeyValidation(`Failed to verify API key: ${error.message}`, 'error');
    }
  }
  
  // Show VibeSurf API key validation message
  showVibeSurfApiKeyValidation(message, type) {
    if (!this.elements.vibeSurfApiKeyValidation) return;
    
    const className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
    this.elements.vibeSurfApiKeyValidation.innerHTML = `
      <div class="validation-message ${className}">
        ${this.escapeHtml(message)}
      </div>
    `;
    this.elements.vibeSurfApiKeyValidation.style.display = 'block';
  }

  // Hide VibeSurf API key validation message
  hideVibeSurfApiKeyValidation() {
    if (this.elements.vibeSurfApiKeyValidation) {
      this.elements.vibeSurfApiKeyValidation.style.display = 'none';
      this.elements.vibeSurfApiKeyValidation.innerHTML = '';
    }
  }
  
  // Load workflows from backend
  async loadWorkflows() {
    try {
      console.log('[SettingsWorkflow] Loading workflows from backend...');
      console.log('[SettingsWorkflow] API client base URL:', this.apiClient.baseURL);
      console.log('[SettingsWorkflow] API client prefix:', this.apiClient.apiPrefix);
      
      const response = await this.apiClient.getWorkflows();
      console.log('[SettingsWorkflow] Workflows response:', response);
      console.log('[SettingsWorkflow] Response type:', typeof response);
      console.log('[SettingsWorkflow] Response keys:', response ? Object.keys(response) : 'null response');
      
      // Handle different response structures
      let workflows = [];
      if (Array.isArray(response)) {
        workflows = response;
        console.log('[SettingsWorkflow] Response is array, length:', workflows.length);
      } else if (response.flows && Array.isArray(response.flows)) {
        workflows = response.flows;
        console.log('[SettingsWorkflow] Response has flows array, length:', workflows.length);
      } else if (response.data && Array.isArray(response.data)) {
        workflows = response.data;
        console.log('[SettingsWorkflow] Response has data array, length:', workflows.length);
      } else {
        console.warn('[SettingsWorkflow] Unexpected response structure:', response);
        workflows = [];
      }
      
      // Convert workflow data to frontend format
      this.state.workflows = workflows.map(workflow => ({
        id: workflow.id,
        name: workflow.name,
        description: workflow.description || '',
        flow_id: workflow.id,
        icon_bg_color: workflow.icon_bg_color,
        updated_at: workflow.updated_at,
        mcp_enabled: workflow.mcp_enabled,
        webhook: workflow.webhook,
        endpoint_name: workflow.endpoint_name
      }));
      
      console.log('[SettingsWorkflow] Converted workflows:', this.state.workflows.length);
      console.log('[SettingsWorkflow] First workflow sample:', this.state.workflows[0]);
      
      // Load schedule information for workflows
      await this.loadWorkflowSchedules();
      
      // Apply current search and filter
      this.filterWorkflows();
      
      console.log('[SettingsWorkflow] Loaded workflows:', this.state.workflows.length);
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflows:', error);
      console.error('[SettingsWorkflow] Error details:', error.message);
      console.error('[SettingsWorkflow] Error stack:', error.stack);
      this.state.workflows = [];
      this.state.filteredWorkflows = [];
      this.renderWorkflows();
      throw error;
    }
  }
  
  // Load workflow schedules
  async loadWorkflowSchedules() {
    try {
      const response = await this.apiClient.getSchedules();
      console.log('[SettingsWorkflow] Schedule API response:', response);
      
      let schedules = [];
      if (Array.isArray(response)) {
        schedules = response;
      } else if (response && response.schedules && Array.isArray(response.schedules)) {
        schedules = response.schedules;
      } else if (response && response.data && Array.isArray(response.data)) {
        schedules = response.data;
      } else if (response && typeof response === 'object') {
        // Handle case where response might be a single schedule object
        if (response.flow_id) {
          schedules = [response];
        } else {
          console.warn('[SettingsWorkflow] Unexpected schedule response format:', response);
        }
      }
      
      console.log('[SettingsWorkflow] Processed schedules:', schedules);
      
      // Add schedule information to workflows
      if (Array.isArray(schedules) && schedules.length > 0) {
        this.state.workflows.forEach(workflow => {
          const schedule = schedules.find(s => s && s.flow_id === workflow.flow_id);
          workflow.scheduled = !!schedule;
          workflow.schedule = schedule;
        });
      } else {
        console.log('[SettingsWorkflow] No schedules found or empty schedule array');
        // Set all workflows as unscheduled
        this.state.workflows.forEach(workflow => {
          workflow.scheduled = false;
          workflow.schedule = null;
        });
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflow schedules:', error);
      // Continue without schedule information - set all as unscheduled
      this.state.workflows.forEach(workflow => {
        workflow.scheduled = false;
        workflow.schedule = null;
      });
    }
  }
  
  // Show workflows loading state
  showWorkflowsLoading() {
    if (this.elements.workflowsLoading) {
      this.elements.workflowsLoading.style.display = 'block';
    }
    if (this.elements.workflowsList) {
      this.elements.workflowsList.innerHTML = '';
    }
  }
  
  // Hide workflows loading state
  hideWorkflowsLoading() {
    if (this.elements.workflowsLoading) {
      this.elements.workflowsLoading.style.display = 'none';
    }
  }
  
  // Handle create workflow button
  handleCreateWorkflow(event) {
    // Prevent any default behavior
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    this.showCreateWorkflowModal();
  }
  
  // Show create workflow modal
  showCreateWorkflowModal() {
    
    if (this.elements.createWorkflowModal) {
      this.elements.createWorkflowModal.classList.remove('hidden');
      
      // Clear previous input and validation
      if (this.elements.workflowNameInput) {
        this.elements.workflowNameInput.value = '';
        console.log('[SettingsWorkflow] Cleared workflow name input');
      }
      if (this.elements.workflowDescriptionInput) {
        this.elements.workflowDescriptionInput.value = '';
        console.log('[SettingsWorkflow] Cleared workflow description input');
      }
      this.hideCreateWorkflowValidation();
      
      // Focus on name input
      setTimeout(() => {
        if (this.elements.workflowNameInput) {
          this.elements.workflowNameInput.focus();
          console.log('[SettingsWorkflow] Focused on workflow name input');
        }
      }, 100);
      
      console.log('[SettingsWorkflow] *** CREATE WORKFLOW MODAL SHOWN SUCCESSFULLY ***');
    } else {
      console.error('[SettingsWorkflow] *** CRITICAL ERROR: Create workflow modal element not found! ***');
    }
  }
  
  // Hide create workflow modal
  hideCreateWorkflowModal() {
    if (this.elements.createWorkflowModal) {
      this.elements.createWorkflowModal.classList.add('hidden');
    }
  }
  
  // Handle create workflow confirm
  async handleCreateWorkflowConfirm() {
    // Prevent multiple simultaneous executions
    if (this._isCreatingWorkflow) {
      return;
    }
    
    this._isCreatingWorkflow = true;
    
    // Disable the confirm button immediately
    if (this.elements.createWorkflowConfirm) {
      this.elements.createWorkflowConfirm.disabled = true;
    }
    
    const name = this.elements.workflowNameInput?.value?.trim();
    const description = this.elements.workflowDescriptionInput?.value?.trim() || '';
    
    if (!name) {
      this._isCreatingWorkflow = false;
      if (this.elements.createWorkflowConfirm) {
        this.elements.createWorkflowConfirm.disabled = false;
      }
      this.showCreateWorkflowValidation('Please enter a workflow name', 'error');
      return;
    }

    try {
      this.showCreateWorkflowValidation('Creating workflow...', 'info');

      // Get projects to obtain folder_id
      const projects = await this.apiClient.getProjects();
      
      // Use the first project's ID as folder_id (typically "Starter Project")
      let folderId = null;
      if (Array.isArray(projects) && projects.length > 0) {
        folderId = projects[0].id;
      } else {
        folderId = "";
      }
      
      // Create workflow data based on the template
      const workflowData = {
        name: name,
        data: {
          nodes: [],
          edges: [],
          viewport: {
            zoom: 1,
            x: 0,
            y: 0
          }
        },
        description: description,
        is_component: false,
        folder_id: folderId,
        icon: null,
        gradient: null,
        endpoint_name: null,
        tags: [],
        mcp_enabled: true
      };
      
      const response = await this.apiClient.createWorkflow(workflowData);
      const workflowId = response.id;
      this.showCreateWorkflowValidation('Workflow created successfully!', 'success');
      
      // Wait a moment to show success message
      setTimeout(() => {
        this.hideCreateWorkflowModal();
        
        // Reset creation flag and re-enable button
        this._isCreatingWorkflow = false;
        if (this.elements.createWorkflowConfirm) {
          this.elements.createWorkflowConfirm.disabled = false;
        }
        
        // Reload workflows list
        this.loadWorkflows();
        
        // Navigate to the new workflow
        const backendUrl = this.apiClient.baseURL || window.CONFIG?.BACKEND_URL || 'http://localhost:9335';
        const editUrl = `${backendUrl}/flow/${workflowId}`;
        
        // Open in new tab using Chrome extension API
        if (typeof chrome !== 'undefined' && chrome.tabs) {
          chrome.tabs.create({ url: editUrl });
        } else {
          // Fallback for non-extension context
          window.open(editUrl, '_blank');
        }
        
        this.emit('notification', {
          message: 'Workflow created and opened for editing',
          type: 'success'
        });
      }, 1000);
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to create workflow:', error);
      this.showCreateWorkflowValidation(`Failed to create workflow: ${error.message}`, 'error');
      
      // Reset creation flag and re-enable button on error
      this._isCreatingWorkflow = false;
      if (this.elements.createWorkflowConfirm) {
        this.elements.createWorkflowConfirm.disabled = false;
      }
    }
  }
  
  // Show create workflow validation message
  showCreateWorkflowValidation(message, type) {
    if (!this.elements.createWorkflowValidation) return;
    
    const className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
    this.elements.createWorkflowValidation.innerHTML = `
      <div class="validation-message ${className}">
        ${this.escapeHtml(message)}
      </div>
    `;
    this.elements.createWorkflowValidation.style.display = 'block';
  }

  // Hide create workflow validation message
  hideCreateWorkflowValidation() {
    if (this.elements.createWorkflowValidation) {
      this.elements.createWorkflowValidation.style.display = 'none';
      this.elements.createWorkflowValidation.innerHTML = '';
    }
  }
  
  // Handle import workflow button
  handleImportWorkflow(event) {
    // Prevent any default behavior
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    this.showImportWorkflowModal();
  }
  
  // Show import workflow modal
  showImportWorkflowModal() {
    if (this.elements.importWorkflowModal) {
      this.elements.importWorkflowModal.classList.remove('hidden');
      
      // Clear previous input and validation
      if (this.elements.workflowJsonInput) {
        this.elements.workflowJsonInput.value = '';
      }
      this.clearJsonFileSelection();
      this.hideImportWorkflowValidation();
      
      // Set default import method to JSON file
      const jsonFileRadio = document.querySelector('input[name="import-method"][value="json-file"]');
      if (jsonFileRadio) {
        jsonFileRadio.checked = true;
        this.handleImportMethodChange();
      }
      
      // Focus on textarea
      setTimeout(() => {
        if (this.elements.workflowJsonInput) {
          this.elements.workflowJsonInput.focus();
        }
      }, 100);
      
      console.log('[SettingsWorkflow] Import workflow modal shown');
    } else {
      console.error('[SettingsWorkflow] Import workflow modal element not found!');
    }
  }
  
  // Hide import workflow modal
  hideImportWorkflowModal() {
    if (this.elements.importWorkflowModal) {
      this.elements.importWorkflowModal.classList.add('hidden');
    }
  }
  
  // Handle import method change (JSON file vs text)
  handleImportMethodChange() {
    const selectedMethod = document.querySelector('input[name="import-method"]:checked')?.value;
    
    if (selectedMethod === 'json-file') {
      this.elements.jsonFileImport?.classList.remove('hidden');
      this.elements.jsonTextImport?.classList.add('hidden');
    } else if (selectedMethod === 'json-text') {
      this.elements.jsonFileImport?.classList.add('hidden');
      this.elements.jsonTextImport?.classList.remove('hidden');
    }
    
    this.hideImportWorkflowValidation();
  }
  
  // Handle select JSON file button
  handleSelectJsonFile() {
    if (this.elements.workflowJsonFile) {
      this.elements.workflowJsonFile.click();
    }
  }
  
  // Handle JSON file selection change
  handleJsonFileChange(event) {
    const file = event.target.files[0];
    
    if (file) {
      if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
        this.showImportWorkflowValidation('Please select a valid JSON file', 'error');
        this.clearJsonFileSelection();
        return;
      }
      
      // Show selected file info
      if (this.elements.selectedFileName) {
        this.elements.selectedFileName.textContent = file.name;
      }
      if (this.elements.selectedFileInfo) {
        this.elements.selectedFileInfo.classList.remove('hidden');
      }
      
      this.hideImportWorkflowValidation();
    }
  }
  
  // Handle clear file selection
  handleClearFile() {
    this.clearJsonFileSelection();
  }
  
  // Clear JSON file selection
  clearJsonFileSelection() {
    if (this.elements.workflowJsonFile) {
      this.elements.workflowJsonFile.value = '';
    }
    if (this.elements.selectedFileInfo) {
      this.elements.selectedFileInfo.classList.add('hidden');
    }
    if (this.elements.selectedFileName) {
      this.elements.selectedFileName.textContent = '';
    }
  }
  
  // Handle import workflow confirm
  async handleImportWorkflowConfirm() {
    // Prevent multiple simultaneous executions
    if (this._isImportingWorkflow) {
      return;
    }
    
    this._isImportingWorkflow = true;
    
    // Disable the confirm button immediately
    if (this.elements.importWorkflowConfirm) {
      this.elements.importWorkflowConfirm.disabled = true;
      const btnText = this.elements.importWorkflowConfirm.querySelector('.btn-text');
      const btnLoading = this.elements.importWorkflowConfirm.querySelector('.btn-loading');
      if (btnText) btnText.classList.add('hidden');
      if (btnLoading) btnLoading.classList.remove('hidden');
    }
    
    try {
      const selectedMethod = document.querySelector('input[name="import-method"]:checked')?.value;
      let workflowJson = '';
      
      if (selectedMethod === 'json-file') {
        const file = this.elements.workflowJsonFile?.files[0];
        
        if (!file) {
          this.showImportWorkflowValidation('Please select a JSON file', 'error');
          throw new Error('No file selected');
        }
        
        try {
          workflowJson = await this.readFileAsText(file);
        } catch (error) {
          this.showImportWorkflowValidation('Failed to read file', 'error');
          throw new Error('Failed to read file');
        }
      } else if (selectedMethod === 'json-text') {
        workflowJson = this.elements.workflowJsonInput?.value?.trim() || '';
        
        if (!workflowJson) {
          this.showImportWorkflowValidation('Please enter workflow JSON', 'error');
          throw new Error('No workflow JSON provided');
        }
      }
      
      this.showImportWorkflowValidation('Importing workflow...', 'info');
      
      // Import the workflow
      const response = await this.apiClient.importWorkflow(workflowJson);
      
      if (response.success) {
        this.showImportWorkflowValidation('Workflow imported successfully!', 'success');
        
        // Wait a moment to show success message
        setTimeout(() => {
          this.hideImportWorkflowModal();
          
          // Reload workflows list
          this.loadWorkflows();
          
          // Navigate to the imported workflow if edit_url is provided
          if (response.edit_url) {
            if (typeof chrome !== 'undefined' && chrome.tabs) {
              chrome.tabs.create({ url: response.edit_url });
            } else {
              window.open(response.edit_url, '_blank');
            }
          }
          
          this.emit('notification', {
            message: 'Workflow imported and opened for editing',
            type: 'success'
          });
        }, 1000);
      } else {
        this.showImportWorkflowValidation(response.message || 'Failed to import workflow', 'error');
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to import workflow:', error);
      this.showImportWorkflowValidation(`Failed to import workflow: ${error.message}`, 'error');
    } finally {
      // Reset import flag and re-enable button
      this._isImportingWorkflow = false;
      if (this.elements.importWorkflowConfirm) {
        this.elements.importWorkflowConfirm.disabled = false;
        const btnText = this.elements.importWorkflowConfirm.querySelector('.btn-text');
        const btnLoading = this.elements.importWorkflowConfirm.querySelector('.btn-loading');
        if (btnText) btnText.classList.remove('hidden');
        if (btnLoading) btnLoading.classList.add('hidden');
      }
    }
  }
  
  // Read file as text
  readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = (e) => reject(new Error('Failed to read file'));
      reader.readAsText(file);
    });
  }
  
  // Show import workflow validation message
  showImportWorkflowValidation(message, type) {
    if (!this.elements.importWorkflowValidation) return;
    
    const className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
    this.elements.importWorkflowValidation.innerHTML = `
      <div class="validation-message ${className}">
        ${this.escapeHtml(message)}
      </div>
    `;
    this.elements.importWorkflowValidation.style.display = 'block';
  }

  // Hide import workflow validation message
  hideImportWorkflowValidation() {
    if (this.elements.importWorkflowValidation) {
      this.elements.importWorkflowValidation.style.display = 'none';
      this.elements.importWorkflowValidation.innerHTML = '';
    }
  }
  
  
  // Handle workflow search
  handleWorkflowSearch(event) {
    this.state.workflowSearchQuery = event.target.value.toLowerCase().trim();
    this.filterWorkflows();
  }
  
  // Handle workflow filter
  handleWorkflowFilter(event) {
    this.state.workflowFilterStatus = event.target.value;
    this.filterWorkflows();
  }
  
  // Filter workflows based on search and filter
  filterWorkflows() {
    let filtered = [...this.state.workflows];
    
    // Apply search filter
    if (this.state.workflowSearchQuery) {
      filtered = filtered.filter(workflow =>
        workflow.name.toLowerCase().includes(this.state.workflowSearchQuery) ||
        workflow.description.toLowerCase().includes(this.state.workflowSearchQuery)
      );
    }
    
    // Apply status filter
    if (this.state.workflowFilterStatus !== 'all') {
      if (this.state.workflowFilterStatus === 'scheduled') {
        filtered = filtered.filter(workflow => workflow.scheduled === true);
      } else if (this.state.workflowFilterStatus === 'unscheduled') {
        filtered = filtered.filter(workflow => workflow.scheduled === false);
      } else if (this.state.workflowFilterStatus === 'running') {
        filtered = filtered.filter(workflow => this.state.runningJobs.has(workflow.flow_id));
      }
    }
    
    this.state.filteredWorkflows = filtered;
    console.log('[SettingsWorkflow] Filtered workflows for rendering:', filtered.length);
    this.renderWorkflows();
  }
  
  // Render workflows list
  renderWorkflows() {
    console.log('[SettingsWorkflow] renderWorkflows called');
    
    if (!this.elements.workflowsList) {
      console.error('[SettingsWorkflow] workflowsList element not found!');
      return;
    }
    
    this.hideWorkflowsLoading();
    
    const workflows = this.state.filteredWorkflows;
    console.log('[SettingsWorkflow] Rendering workflows:', workflows.length);
    
    if (workflows.length === 0) {
      const isEmpty = this.state.workflows.length === 0;
      this.elements.workflowsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚡</div>
          <div class="empty-state-title">${isEmpty ? 'No Workflows Available' : 'No Matching Workflows'}</div>
          <div class="empty-state-description">
            ${isEmpty ? 'Create your first workflow to get started and unlock the power of automated workflows.' : 'Try adjusting your search or filter criteria to find what you\'re looking for.'}
          </div>
          ${isEmpty ? '<button class="btn btn-primary create-workflow-empty-btn">Create Your First Workflow</button>' : ''}
        </div>
      `;
      
      // Bind event to the empty state create workflow button
      if (isEmpty) {
        const emptyCreateBtn = this.elements.workflowsList.querySelector('.create-workflow-empty-btn');
        if (emptyCreateBtn) {
          emptyCreateBtn.addEventListener('click', this.handleCreateWorkflow.bind(this));
        }
      }
      return;
    }
    
    const workflowsHTML = workflows.map(workflow => this.renderWorkflowCard(workflow)).join('');
    this.elements.workflowsList.innerHTML = workflowsHTML;
    
    // Bind event listeners for workflow interactions
    this.bindWorkflowEvents();
  }
  
  // Render individual workflow card
  renderWorkflowCard(workflow) {
    const isRunning = this.state.runningJobs.has(workflow.flow_id);
    const jobInfo = this.state.runningJobs.get(workflow.flow_id);
    
    return `
      <div class="workflow-card" data-workflow-id="${workflow.flow_id}">
        <div class="workflow-header">
          <div class="workflow-info">
            <div class="workflow-name">${this.escapeHtml(workflow.name)}</div>
            <div class="workflow-description">${this.escapeHtml(workflow.description)}</div>
            <div class="workflow-flow-id">
              <span class="flow-id-label">Flow ID:</span>
              <code class="flow-id-value" title="Click to copy">${workflow.flow_id}</code>
              <button class="btn btn-icon copy-flow-id" data-flow-id="${workflow.flow_id}" title="Copy Flow ID">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M16 4H18C19.1046 4 20 4.89543 20 6V18C20 19.1046 19.1046 20 18 20H6C4.89543 20 4 19.1046 4 18V6C4 4.89543 4.89543 4 6 4H8" stroke="currentColor" stroke-width="2"/>
                  <rect x="8" y="2" width="8" height="4" rx="1" stroke="currentColor" stroke-width="2"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="workflow-status">
            ${workflow.scheduled ? '<span class="status-badge scheduled">Scheduled</span>' : ''}
            ${isRunning ? '<span class="status-badge running">Running</span>' : ''}
          </div>
        </div>
        <div class="workflow-actions">
          <button class="btn btn-primary workflow-run-btn" data-workflow-id="${workflow.flow_id}"
                  ${isRunning ? 'style="display: none;"' : ''}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <polygon points="5,3 19,12 5,21" stroke="currentColor" stroke-width="2" fill="currentColor"/>
            </svg>
            Run
          </button>
          <button class="btn btn-secondary workflow-pause-btn" data-workflow-id="${workflow.flow_id}" data-job-id="${jobInfo?.job_id || ''}"
                  ${!isRunning ? 'style="display: none;"' : ''}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect x="6" y="4" width="4" height="16" stroke="currentColor" stroke-width="2" fill="currentColor"/>
              <rect x="14" y="4" width="4" height="16" stroke="currentColor" stroke-width="2" fill="currentColor"/>
            </svg>
            Pause
          </button>
          <button class="btn btn-secondary workflow-logs-btn" data-workflow-id="${workflow.flow_id}" data-job-id="${jobInfo?.job_id || ''}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" stroke-width="2"/>
              <polyline points="14,2 14,8 20,8" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/>
              <polyline points="10,9 9,9 8,9" stroke="currentColor" stroke-width="2"/>
            </svg>
            Logs
          </button>
          <button class="btn btn-secondary workflow-schedule-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" stroke-width="2"/>
              <line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" stroke-width="2"/>
              <line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" stroke-width="2"/>
            </svg>
            Schedule
          </button>
          <button class="btn btn-secondary workflow-edit-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2"/>
              <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2"/>
            </svg>
            Edit
          </button>
          <button class="btn btn-danger workflow-delete-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M3 6H5H21" stroke="currentColor" stroke-width="2"/>
              <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2"/>
            </svg>
            Delete
          </button>
        </div>
      </div>
    `;
  }
  
  // Bind workflow event listeners
  bindWorkflowEvents() {
    if (!this.elements.workflowsList) return;
    
    // Copy flow ID buttons
    this.elements.workflowsList.querySelectorAll('.copy-flow-id').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleCopyFlowId(btn.dataset.flowId);
      });
    });
    
    // Run workflow buttons
    this.elements.workflowsList.querySelectorAll('.workflow-run-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowRun(btn.dataset.workflowId);
      });
    });
    
    // Pause workflow buttons
    this.elements.workflowsList.querySelectorAll('.workflow-pause-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowPause(btn.dataset.workflowId, btn.dataset.jobId);
      });
    });
    
    // Logs buttons
    this.elements.workflowsList.querySelectorAll('.workflow-logs-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowLogs(btn.dataset.workflowId, btn.dataset.jobId);
      });
    });
    
    // Schedule buttons
    this.elements.workflowsList.querySelectorAll('.workflow-schedule-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowSchedule(btn.dataset.workflowId);
      });
    });
    
    // Edit buttons
    this.elements.workflowsList.querySelectorAll('.workflow-edit-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowEdit(btn.dataset.workflowId);
      });
    });
    
    // Delete buttons
    this.elements.workflowsList.querySelectorAll('.workflow-delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowDelete(btn.dataset.workflowId);
      });
    });
  }
  
  // Handle copy flow ID
  async handleCopyFlowId(flowId) {
    try {
      await navigator.clipboard.writeText(flowId);
      this.emit('notification', {
        message: 'Flow ID copied to clipboard',
        type: 'success'
      });
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to copy flow ID:', error);
      this.emit('notification', {
        message: 'Failed to copy flow ID',
        type: 'error'
      });
    }
  }
  
  // Handle workflow run
  async handleWorkflowRun(workflowId) {
    try {
      console.log(`[SettingsWorkflow] Running workflow ${workflowId}`);
      
      const response = await this.apiClient.runWorkflow(workflowId);
      const jobId = response.job_id || response.id;
      
      if (jobId) {
        // Add to running jobs
        this.state.runningJobs.set(workflowId, {
          job_id: jobId,
          started_at: new Date()
        });
        
        // Re-render workflows to update UI
        this.renderWorkflows();
        
        // Start monitoring job status
        this.monitorWorkflowJob(workflowId, jobId);
        
        this.emit('notification', {
          message: 'Workflow started successfully',
          type: 'success'
        });
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to run workflow:', error);
      this.emit('notification', {
        message: `Failed to run workflow: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Handle workflow pause
  async handleWorkflowPause(workflowId, jobId) {
    try {
      console.log(`[SettingsWorkflow] Pausing workflow ${workflowId}, job ${jobId}`);
      
      await this.apiClient.cancelWorkflow(jobId);
      
      // Remove from running jobs
      this.state.runningJobs.delete(workflowId);
      
      // Re-render workflows to update UI
      this.renderWorkflows();
      
      this.emit('notification', {
        message: 'Workflow paused successfully',
        type: 'success'
      });
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to pause workflow:', error);
      this.emit('notification', {
        message: `Failed to pause workflow: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Unified event fetching with caching to prevent competition
  async fetchWorkflowEvents(jobId, options = {}) {
    const { forceRefresh = false, maxAge = 10000, preserveCache = true, workflowId = null } = options;
    
    console.log(`[SettingsWorkflow] 🔄 FETCHING EVENTS for job ${jobId}`, {
      forceRefresh,
      maxAge,
      preserveCache,
      workflowId
    });
    
    // Check cache first
    const cached = this.state.eventCache.get(jobId);
    const now = Date.now();
    
    console.log(`[SettingsWorkflow] Cache check:`, {
      exists: !!cached,
      isPersistent: cached?.isPersistent,
      isComplete: cached?.isComplete,
      eventCount: cached?.events?.length || 0,
      workflowId: cached?.workflowId,
      ageMs: cached ? now - cached.lastFetch : 'N/A'
    });
    
    // Persistent cache for completed workflows - NEVER refresh unless explicitly forced
    if (cached && cached.isPersistent && !forceRefresh) {
      console.log(`[SettingsWorkflow] ✅ Using persistent cached events for completed job ${jobId}, count: ${cached.events.length}`);
      return cached.events;
    }
    
    // For completed workflows, always prefer cached events to prevent loss
    if (cached && cached.isComplete && cached.events.length > 0 && !forceRefresh) {
      console.log(`[SettingsWorkflow] Using cached events for completed job ${jobId}, preventing loss of ${cached.events.length} events`);
      return cached.events;
    }
    
    if (cached && !forceRefresh && (now - cached.lastFetch) < maxAge) {
      console.log(`[SettingsWorkflow] Using cached events for job ${jobId}, cache hit preventing duplicate API call`);
      return cached.events;
    }
    
    try {
      const eventsResponse = await this.apiClient.getWorkflowEvents(jobId);
      
      // Parse events - API returns NDJSON format (newline-delimited JSON)
      let events = [];
      if (typeof eventsResponse === 'string') {
        // Split by newlines and parse each line as JSON
        const lines = eventsResponse.trim().split('\n');
        events = lines.map(line => {
          const trimmedLine = line.trim();
          if (!trimmedLine) return null; // Skip empty lines
          try {
            return JSON.parse(trimmedLine);
          } catch (e) {
            console.warn(`[SettingsWorkflow] Failed to parse event line: ${trimmedLine}`, e);
            return null;
          }
        }).filter(event => event !== null);
      } else if (Array.isArray(eventsResponse)) {
        events = eventsResponse;
      } else if (eventsResponse && typeof eventsResponse === 'object') {
        events = [eventsResponse];
      }
      
      // Check if workflow is complete based on events
      const hasEndEvent = events.some(event => {
        const eventType = event.event || event.eventType || '';
        return eventType === 'on_end' ||
               eventType === 'end' ||
               eventType === 'completed' ||
               eventType === 'error' ||
               eventType === 'failed' ||
               eventType === 'stream_end';
      });
      
      // Enhanced cache update strategy: NEVER overwrite cached events with fewer events
      let finalEvents = events;
      let shouldUpdateCache = true;
      
      if (cached && cached.events.length > 0) {
        if (events.length === 0) {
          // API returned empty - always preserve existing cache
          console.log(`[SettingsWorkflow] Preserving ${cached.events.length} cached events for job ${jobId} - API returned empty result`);
          finalEvents = cached.events;
          shouldUpdateCache = false; // Don't update cache with empty result
        } else if (events.length < cached.events.length && !hasEndEvent) {
          // API returned fewer events and workflow not complete - suspicious, preserve cache
          console.log(`[SettingsWorkflow] Preserving ${cached.events.length} cached events for job ${jobId} - API returned fewer events (${events.length})`);
          finalEvents = cached.events;
          shouldUpdateCache = false;
        } else {
          // API returned more or equal events, or workflow is complete - safe to update
          finalEvents = events;
        }
      }
      
      // Update cache only if safe to do so
      if (shouldUpdateCache) {
        const cacheEntry = {
          events: finalEvents,
          lastFetch: now,
          isComplete: hasEndEvent || (cached && cached.isComplete),
          workflowId: cached?.workflowId || workflowId // Preserve or set workflow association
        };
        
        // Mark as persistent if workflow is complete
        if (cacheEntry.isComplete && finalEvents.length > 0) {
          cacheEntry.isPersistent = true;
          cacheEntry.completedAt = now;
          console.log(`[SettingsWorkflow] Marking job ${jobId} cache as persistent with ${finalEvents.length} events`);
          
          // Update workflow-to-job mapping for completed workflows
          if (cacheEntry.workflowId) {
            this.state.workflowJobMapping.set(cacheEntry.workflowId, {
              jobId: jobId,
              completedAt: now,
              eventCount: finalEvents.length
            });
            console.log(`[SettingsWorkflow] Updated workflow mapping: ${cacheEntry.workflowId} -> ${jobId}`);
          }
        }
        
        this.state.eventCache.set(jobId, cacheEntry);
      } else {
        // Just update lastFetch to prevent excessive API calls
        if (cached) {
          this.state.eventCache.set(jobId, {
            ...cached,
            lastFetch: now
          });
        } else if (workflowId) {
          // Create new cache entry if none exists and we have workflow context
          this.state.eventCache.set(jobId, {
            events: finalEvents,
            lastFetch: now,
            isComplete: hasEndEvent,
            isPersistent: false,
            workflowId: workflowId
          });
        }
      }
      
      // Notify all subscribers with final events
      const subscribers = this.state.eventSubscribers.get(jobId);
      if (subscribers) {
        subscribers.forEach(callback => {
          try {
            callback(finalEvents, hasEndEvent || (cached && cached.isComplete));
          } catch (e) {
            console.error(`[SettingsWorkflow] Error notifying event subscriber:`, e);
          }
        });
      }
      
      return finalEvents;
      
    } catch (error) {
      console.error(`[SettingsWorkflow] Failed to fetch events for job ${jobId}:`, error);
      // Return cached events if available on error
      if (cached && cached.events.length > 0) {
        console.log(`[SettingsWorkflow] Returning cached events due to API error for job ${jobId}`);
        return cached.events;
      }
      throw error;
    }
  }
  
  // Subscribe to event updates for a job
  subscribeToEvents(jobId, callback) {
    console.log(`[SettingsWorkflow] subscribeToEvents called for job ${jobId}`);
    
    if (!this.state.eventSubscribers.has(jobId)) {
      this.state.eventSubscribers.set(jobId, new Set());
      console.log(`[SettingsWorkflow] Created new subscriber set for job ${jobId}`);
    }
    this.state.eventSubscribers.get(jobId).add(callback);
    console.log(`[SettingsWorkflow] Subscribed to events for job ${jobId}, total subscribers: ${this.state.eventSubscribers.get(jobId).size}`);
    
    // Return unsubscribe function
    return () => {
      console.log(`[SettingsWorkflow] Unsubscribe function called for job ${jobId}`);
      const subscribers = this.state.eventSubscribers.get(jobId);
      if (subscribers) {
        subscribers.delete(callback);
        console.log(`[SettingsWorkflow] Removed subscriber for job ${jobId}, remaining subscribers: ${subscribers.size}`);
        if (subscribers.size === 0) {
          this.state.eventSubscribers.delete(jobId);
          console.log(`[SettingsWorkflow] Removed empty subscriber set for job ${jobId}`);
        }
      }
      console.log(`[SettingsWorkflow] Unsubscribed from events for job ${jobId}`);
    };
  }
  
  // Monitor workflow job status using cached events
  async monitorWorkflowJob(workflowId, jobId) {
    let unsubscribe;
    let monitoringInterval;
    let monitoringStopped = false;
    
    const stopMonitoring = () => {
      if (monitoringStopped) return;
      monitoringStopped = true;
      
      if (monitoringInterval) {
        clearTimeout(monitoringInterval);
        monitoringInterval = null;
      }
      if (unsubscribe) {
        unsubscribe();
        unsubscribe = null;
      }
      console.log(`[SettingsWorkflow] Stopped monitoring job ${jobId}`);
    };
    
    const checkStatus = async (events, isComplete) => {
      try {
        if (isComplete || !this.state.runningJobs.has(workflowId)) {
          // Workflow finished, remove from running jobs
          console.log(`[SettingsWorkflow] ⚠️ WORKFLOW COMPLETION DETECTED: ${workflowId}, jobId: ${jobId}`);
          console.log(`[SettingsWorkflow] Events received: ${events.length}, isComplete: ${isComplete}`);
          console.log(`[SettingsWorkflow] RunningJobs before deletion:`, Array.from(this.state.runningJobs.keys()));
          
          this.state.runningJobs.delete(workflowId);
          console.log(`[SettingsWorkflow] RunningJobs after deletion:`, Array.from(this.state.runningJobs.keys()));
          
          // Mark cache as persistent for completed workflows - NEVER allow overwriting
          const cached = this.state.eventCache.get(jobId);
          console.log(`[SettingsWorkflow] Existing cache for job ${jobId}:`, {
            exists: !!cached,
            eventCount: cached?.events?.length || 0,
            isPersistent: cached?.isPersistent
          });
          
          if (cached && events.length > 0) {
            const completedAt = Date.now();
            this.state.eventCache.set(jobId, {
              ...cached,
              events: events,
              isComplete: true,
              isPersistent: true, // Mark as persistent - prevents any future overwrites
              completedAt: completedAt,
              finalEventCount: events.length
            });
            
            // Update workflow-to-job mapping for quick lookup
            if (cached.workflowId) {
              this.state.workflowJobMapping.set(cached.workflowId, {
                jobId: jobId,
                completedAt: completedAt,
                eventCount: events.length
              });
              console.log(`[SettingsWorkflow] Updated workflow mapping on completion: ${cached.workflowId} -> ${jobId}`);
            }
            
            console.log(`[SettingsWorkflow] ✅ PERMANENTLY cached job ${jobId} with ${events.length} events - cache is now read-only`);
          } else {
            console.log(`[SettingsWorkflow] ❌ FAILED to cache job ${jobId} - cached: ${!!cached}, events: ${events.length}`);
          }
          
          stopMonitoring();
          this.renderWorkflows();
          
          this.emit('notification', {
            message: 'Workflow execution completed',
            type: 'success'
          });
          return;
        }
        
      } catch (error) {
        console.error('[SettingsWorkflow] Failed to check workflow status:', error);
        // Stop monitoring on error but inform user
        this.state.runningJobs.delete(workflowId);
        stopMonitoring();
        this.renderWorkflows();
        
        this.emit('notification', {
          message: 'Failed to monitor workflow status',
          type: 'warning'
        });
      }
    };
    
    // Subscribe to event updates
    unsubscribe = this.subscribeToEvents(jobId, checkStatus);
    
    // Improved periodic event fetching that respects persistent cache
    const fetchEvents = async () => {
      if (monitoringStopped || !this.state.runningJobs.has(workflowId)) {
        stopMonitoring();
        return;
      }
      
      // Check if cache is already persistent - if so, stop monitoring
      const cached = this.state.eventCache.get(jobId);
      if (cached && cached.isPersistent) {
        console.log(`[SettingsWorkflow] Job ${jobId} cache is persistent, stopping monitoring`);
        stopMonitoring();
        return;
      }
      
      try {
        // For running jobs, fetch with moderate preservation to avoid empty overwrites
        // Pass workflowId context to maintain association
        const currentWorkflowId = Array.from(this.state.runningJobs.entries()).find(([wId, job]) => job.job_id === jobId)?.[0];
        await this.fetchWorkflowEvents(jobId, {
          preserveCache: true,
          maxAge: 8000,
          workflowId: currentWorkflowId
        });
        
        // Check if workflow completed during this fetch
        const updatedCache = this.state.eventCache.get(jobId);
        if (updatedCache && (updatedCache.isComplete || updatedCache.isPersistent)) {
          console.log(`[SettingsWorkflow] Job ${jobId} completed during fetch, stopping monitoring`);
          stopMonitoring();
          return;
        }
        
        // Schedule next fetch
        if (!monitoringStopped) {
          monitoringInterval = setTimeout(fetchEvents, 7000);
        }
      } catch (error) {
        console.error(`[SettingsWorkflow] Failed to fetch events for job ${jobId}:`, error);
        // Continue trying even on error, but with longer delay
        if (!monitoringStopped) {
          monitoringInterval = setTimeout(fetchEvents, 15000);
        }
      }
    };
    
    // Start monitoring after a short delay
    setTimeout(() => {
      if (!monitoringStopped) {
        fetchEvents(); // Initial fetch
      }
    }, 3000);
  }
  
  // Handle workflow logs
  async handleWorkflowLogs(workflowId, jobId) {
    console.log(`[SettingsWorkflow] 📋 OPENING LOGS: workflowId=${workflowId}, jobId=${jobId}`);
    
    const workflow = this.state.workflows.find(w => w.flow_id === workflowId);
    if (!workflow) {
      console.log(`[SettingsWorkflow] ❌ Workflow not found: ${workflowId}`);
      return;
    }
    
    console.log(`[SettingsWorkflow] Found workflow: ${workflow.name}`);
    console.log(`[SettingsWorkflow] Is workflow running?`, this.state.runningJobs.has(workflowId));
    
    this.state.currentLogsWorkflow = workflow;
    this.state.currentLogsJobId = jobId;
    
    this.showLogsModal();
    
    // If no jobId provided but workflow exists, try to find the correct job using workflow mapping
    let effectiveJobId = jobId;
    if (!jobId && workflow) {
      // First, check if we have a workflow-to-job mapping for this workflow
      const workflowMapping = this.state.workflowJobMapping.get(workflowId);
      if (workflowMapping && workflowMapping.jobId) {
        effectiveJobId = workflowMapping.jobId;
        console.log(`[SettingsWorkflow] Found mapped jobId for workflow ${workflowId}: ${effectiveJobId}`);
        this.state.currentLogsJobId = effectiveJobId;
      } else {
        // Fallback: Look for cached events associated with this workflow
        const cachedJobIds = Array.from(this.state.eventCache.keys());
        const workflowJobIds = cachedJobIds.filter(id => {
          const cached = this.state.eventCache.get(id);
          return cached && cached.workflowId === workflowId && cached.events && cached.events.length > 0;
        });
        
        if (workflowJobIds.length > 0) {
          // Use the most recently completed job for this workflow
          effectiveJobId = workflowJobIds.sort((a, b) => {
            const cacheA = this.state.eventCache.get(a);
            const cacheB = this.state.eventCache.get(b);
            const timeA = cacheA.completedAt || cacheA.lastFetch || 0;
            const timeB = cacheB.completedAt || cacheB.lastFetch || 0;
            return timeB - timeA; // Most recent first
          })[0];
          
          console.log(`[SettingsWorkflow] No mapping found, using most recent cached job for workflow ${workflowId}: ${effectiveJobId}`);
          this.state.currentLogsJobId = effectiveJobId;
        } else {
          console.log(`[SettingsWorkflow] No cached logs found for workflow ${workflowId}`);
        }
      }
    }
    
    await this.loadWorkflowLogs(effectiveJobId);
  }
  
  // Show logs modal
  showLogsModal() {
    if (!this.elements.workflowLogsModal || !this.state.currentLogsWorkflow) return;
    
    // Update modal title and info
    if (this.elements.logsModalTitle) {
      this.elements.logsModalTitle.textContent = `Workflow Logs`;
    }
    
    if (this.elements.logsWorkflowName) {
      this.elements.logsWorkflowName.textContent = this.state.currentLogsWorkflow.name;
    }
    
    if (this.elements.logsJobId) {
      this.elements.logsJobId.textContent = this.state.currentLogsJobId || 'No active job';
    }
    
    // Show modal
    this.elements.workflowLogsModal.classList.remove('hidden');
  }
  
  // Hide logs modal
  hideLogsModal() {
    if (this.elements.workflowLogsModal) {
      this.elements.workflowLogsModal.classList.add('hidden');
    }
    this.state.currentLogsWorkflow = null;
    this.state.currentLogsJobId = null;
  }
  
  // Load workflow logs using cached events
  async loadWorkflowLogs(jobId) {
    if (!this.elements.logsContent) return;
    
    try {
      if (this.elements.logsLoading) {
        this.elements.logsLoading.style.display = 'block';
      }
      
      if (!jobId) {
        this.elements.logsContent.innerHTML = '<div class="log-entry info">No active job to show logs for</div>';
        return;
      }
      
      console.log(`[SettingsWorkflow] Loading logs for job ${jobId}`);
      console.log(`[SettingsWorkflow] Current workflow:`, this.state.currentLogsWorkflow?.name);
      console.log(`[SettingsWorkflow] Running jobs:`, Array.from(this.state.runningJobs.keys()));
      
      // First, ALWAYS check persistent cache - this is the key fix
      let events = [];
      const cached = this.state.eventCache.get(jobId);
      
      console.log(`[SettingsWorkflow] Cache status for job ${jobId}:`, {
        exists: !!cached,
        isPersistent: cached?.isPersistent,
        isComplete: cached?.isComplete,
        eventCount: cached?.events?.length || 0,
        lastFetch: cached?.lastFetch ? new Date(cached.lastFetch).toLocaleTimeString() : 'never'
      });
      
      // Prioritize persistent cached events (completed workflows)
      if (cached && cached.isPersistent && cached.events.length > 0) {
        console.log(`[SettingsWorkflow] Using PERSISTENT cached events for completed job ${jobId}, count: ${cached.events.length}`);
        events = cached.events;
        
        // For completed workflows, render immediately and don't fetch fresh events
        this.renderWorkflowLogs(events);
        
        // Update job info display to show it's from cache
        if (this.elements.logsJobId) {
          this.elements.logsJobId.textContent = `${jobId} (Completed)`;
        }
        return;
      }
      
      // For non-persistent cache or empty cache
      if (cached && cached.events.length > 0) {
        console.log(`[SettingsWorkflow] Using cached events for job ${jobId}, count: ${cached.events.length}`);
        events = cached.events;
        
        // Render cached events immediately for better UX
        this.renderWorkflowLogs(events);
        
        // Check if this is a completed workflow that should be marked as persistent
        if (cached.isComplete && !cached.isPersistent) {
          console.log(`[SettingsWorkflow] Marking completed job ${jobId} as persistent to prevent future overwrites`);
          this.state.eventCache.set(jobId, {
            ...cached,
            isPersistent: true,
            completedAt: cached.completedAt || Date.now()
          });
        }
        
        // Only fetch fresh events for running jobs (don't fetch for completed jobs)
        if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id) && !cached.isComplete && !cached.isPersistent) {
          console.log(`[SettingsWorkflow] Job still running, fetching fresh events in background`);
          this.fetchWorkflowEvents(jobId, { preserveCache: true, maxAge: 2000 }).then(freshEvents => {
            if (freshEvents.length > events.length) {
              console.log(`[SettingsWorkflow] Fresh events available, updating logs: ${freshEvents.length} events`);
              this.renderWorkflowLogs(freshEvents);
            }
          }).catch(error => {
            console.warn(`[SettingsWorkflow] Background event fetch failed for job ${jobId}:`, error);
          });
        } else if (cached.isComplete || cached.isPersistent) {
          console.log(`[SettingsWorkflow] Using completed workflow logs from cache, no fresh fetch needed`);
          // Update job info display to show completion status
          if (this.elements.logsJobId) {
            this.elements.logsJobId.textContent = `${jobId} (Completed)`;
          }
        }
      } else {
        console.log(`[SettingsWorkflow] No cached events, fetching fresh for job ${jobId}`);
        // Only fetch fresh if no cache exists - but preserve any existing cache
        // Pass workflow context for proper association
        events = await this.fetchWorkflowEvents(jobId, {
          forceRefresh: false,
          preserveCache: true,
          workflowId: this.state.currentLogsWorkflow?.flow_id
        });
        console.log(`[SettingsWorkflow] Fetched ${events.length} fresh events for job ${jobId}`);
        this.renderWorkflowLogs(events);
      }
      
      // Set up real-time updates ONLY if job is still running
      if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id)) {
        console.log(`[SettingsWorkflow] Job is still running, setting up real-time log updates`);
        
        let unsubscribe;
        const updateLogs = (newEvents, isComplete) => {
          console.log(`[SettingsWorkflow] Real-time log update with ${newEvents.length} events, complete: ${isComplete}`);
          if (newEvents.length > 0) { // Only update if we have events
            this.renderWorkflowLogs(newEvents);
          }
        };
        
        // Subscribe to event updates
        unsubscribe = this.subscribeToEvents(jobId, updateLogs);
        
        // Clean up subscription when logs modal is closed
        const originalHideLogsModal = this.hideLogsModal.bind(this);
        this.hideLogsModal = () => {
          if (unsubscribe) {
            console.log(`[SettingsWorkflow] Cleaning up log subscription for job ${jobId}`);
            unsubscribe();
          }
          // Restore original method
          this.hideLogsModal = originalHideLogsModal;
          originalHideLogsModal();
        };
      } else {
        console.log(`[SettingsWorkflow] Job not running, no real-time updates needed for job ${jobId}`);
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflow logs:', error);
      this.elements.logsContent.innerHTML = `<div class="log-entry error">Failed to load logs: ${error.message}</div>`;
    } finally {
      if (this.elements.logsLoading) {
        this.elements.logsLoading.style.display = 'none';
      }
    }
  }
  
  // Render workflow logs with improved UI
  renderWorkflowLogs(events) {
    if (!this.elements.logsContent) return;
    
    console.log(`[SettingsWorkflow] Rendering logs with ${events.length} events`);
    
    if (events.length === 0) {
      this.elements.logsContent.innerHTML = `
        <div class="log-empty-state">
          <div class="log-empty-icon">📋</div>
          <div class="log-empty-title">No Events Available</div>
          <div class="log-empty-description">Events may still be processing or this workflow hasn't generated any logs yet.</div>
        </div>
      `;
      return;
    }
    
    // Group events by category for better organization
    const groupedEvents = this.groupEventsByCategory(events);
    
    let logsHTML = '';
    
    // Add summary header
    logsHTML += this.renderLogSummary(events, groupedEvents);
    
    // Render events with improved categorization
    logsHTML += events.map((event, index) => {
      return this.renderEnhancedLogEntry(event, index);
    }).join('');
    
    this.elements.logsContent.innerHTML = logsHTML;
    
    // Add event listeners for expandable sections
    this.bindLogEventListeners();
    
    // Scroll to bottom
    this.elements.logsContent.scrollTop = this.elements.logsContent.scrollHeight;
    
    console.log(`[SettingsWorkflow] Rendered ${events.length} enhanced log entries`);
  }
  
  // Group events by category for better organization
  groupEventsByCategory(events) {
    const groups = {
      system: [],
      execution: [],
      data: [],
      errors: [],
      completion: []
    };
    
    events.forEach(event => {
      const eventType = event.event || event.eventType || 'unknown';
      
      if (eventType.includes('error') || eventType.includes('failed')) {
        groups.errors.push(event);
      } else if (eventType.includes('end') || eventType.includes('completed') || eventType === 'on_end') {
        groups.completion.push(event);
      } else if (eventType.includes('data') || eventType.includes('message') || eventType.includes('output')) {
        groups.data.push(event);
      } else if (eventType.includes('vertices') || eventType.includes('start') || eventType.includes('init')) {
        groups.system.push(event);
      } else {
        groups.execution.push(event);
      }
    });
    
    return groups;
  }
  
  // Render log summary
  renderLogSummary(events, groupedEvents) {
    const totalEvents = events.length;
    const errorCount = groupedEvents.errors.length;
    const completionCount = groupedEvents.completion.length;
    const isCompleted = completionCount > 0;
    
    return `
      <div class="log-summary">
        <div class="log-summary-header">
          <h4>Event Summary</h4>
          <div class="log-summary-badge ${isCompleted ? 'completed' : 'running'}">
            ${isCompleted ? '✓ Completed' : '⏳ Running'}
          </div>
        </div>
        <div class="log-summary-stats">
          <div class="log-stat">
            <span class="log-stat-label">Total Events:</span>
            <span class="log-stat-value">${totalEvents}</span>
          </div>
          ${errorCount > 0 ? `
            <div class="log-stat error">
              <span class="log-stat-label">Errors:</span>
              <span class="log-stat-value">${errorCount}</span>
            </div>
          ` : ''}
          <div class="log-stat">
            <span class="log-stat-label">Status:</span>
            <span class="log-stat-value ${isCompleted ? 'success' : 'info'}">${isCompleted ? 'Completed' : 'Processing'}</span>
          </div>
        </div>
      </div>
    `;
  }
  
  // Render enhanced log entry
  renderEnhancedLogEntry(event, index) {
    let eventData = event;
    let timestamp, level, message, eventType, details = null;
    
    // Handle different event formats
    if (typeof event === 'string') {
      try {
        eventData = JSON.parse(event);
      } catch (e) {
        return this.renderLogEntry(new Date(), 'info', 'EVENT', event, null, index);
      }
    }
    
    // Extract event information
    if (eventData && typeof eventData === 'object') {
      timestamp = eventData.timestamp || eventData.time || Date.now();
      level = eventData.level || eventData.type || 'info';
      eventType = eventData.event || eventData.eventType || 'unknown';
      
      // Build message and details from event data
      if (eventData.message) {
        message = eventData.message;
        if (eventData.data && typeof eventData.data === 'object' && Object.keys(eventData.data).length > 0) {
          details = eventData.data;
        }
      } else if (eventData.data) {
        if (typeof eventData.data === 'string') {
          message = eventData.data;
        } else {
          message = this.getEventTypeDescription(eventType);
          details = eventData.data;
        }
      } else {
        message = this.getEventTypeDescription(eventType);
        const filteredData = { ...eventData };
        delete filteredData.timestamp;
        delete filteredData.time;
        delete filteredData.event;
        delete filteredData.eventType;
        delete filteredData.level;
        delete filteredData.type;
        
        if (Object.keys(filteredData).length > 0) {
          details = filteredData;
        }
      }
    } else {
      timestamp = Date.now();
      level = 'info';
      eventType = 'event';
      message = String(eventData);
    }
    
    // Determine log level and category
    const { logLevel, category, icon } = this.categorizeEvent(eventType, level);
    
    return this.renderEnhancedLogEntryHTML(new Date(timestamp), logLevel, eventType, message, details, index, category, icon);
  }
  
  // Get user-friendly event type descriptions
  getEventTypeDescription(eventType) {
    const descriptions = {
      'vertices_sorted': 'Workflow initialized and components sorted',
      'on_end': 'Workflow execution completed',
      'add_message': 'New message or output generated',
      'stream_end': 'Data stream finished',
      'error': 'An error occurred during execution',
      'failed': 'Workflow execution failed',
      'start': 'Component execution started',
      'end': 'Component execution finished',
      'unknown': 'System event'
    };
    
    return descriptions[eventType] || `${eventType} event`;
  }
  
  // Categorize events for better visual representation
  categorizeEvent(eventType, level) {
    let logLevel = level.toLowerCase();
    let category = 'info';
    let icon = '📄';
    
    if (eventType === 'error' || eventType === 'failed' || level === 'error') {
      logLevel = 'error';
      category = 'error';
      icon = '❌';
    } else if (eventType === 'end' || eventType === 'on_end' || eventType === 'completed') {
      logLevel = 'success';
      category = 'completion';
      icon = '✅';
    } else if (eventType === 'vertices_sorted' || eventType === 'start') {
      logLevel = 'info';
      category = 'system';
      icon = '⚙️';
    } else if (eventType === 'add_message' || eventType.includes('output')) {
      logLevel = 'success';
      category = 'data';
      icon = '📤';
    } else if (eventType.includes('stream')) {
      logLevel = 'info';
      category = 'data';
      icon = '🔄';
    } else {
      category = 'execution';
      icon = '▶️';
    }
    
    return { logLevel, category, icon };
  }
  
  // Render enhanced log entry HTML with improved design
  renderEnhancedLogEntryHTML(timestamp, logLevel, eventType, message, details, index, category, icon) {
    const timeStr = timestamp.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    const dateStr = timestamp.toLocaleDateString();
    const hasDetails = details && Object.keys(details).length > 0;
    
    // Format details for display
    let detailsContent = '';
    if (hasDetails) {
      if (typeof details === 'string') {
        detailsContent = details;
      } else {
        detailsContent = JSON.stringify(details, null, 2);
      }
    }
    
    const detailsSection = hasDetails ? `
      <div class="log-details" style="display: none;">
        <div class="log-details-header">Event Details:</div>
        <pre class="log-details-content">${this.escapeHtml(detailsContent)}</pre>
      </div>
    ` : '';
    
    const expandButton = hasDetails ? `
      <button class="log-expand-btn" data-index="${index}">
        <span class="expand-icon">▶</span>
        <span class="expand-text">Details</span>
      </button>
    ` : '';
    
    return `
      <div class="log-entry-enhanced ${logLevel} ${category}" data-index="${index}">
        <div class="log-entry-main">
          <div class="log-event-icon">${icon}</div>
          <div class="log-timestamp">
            <div class="log-time">${timeStr}</div>
            <div class="log-date" title="${dateStr}">${this.formatRelativeTime(timestamp)}</div>
          </div>
          <div class="log-content-enhanced">
            <div class="log-event-type">
              <span class="event-category ${category}">${category.toUpperCase()}</span>
              <span class="event-name">${eventType}</span>
            </div>
            <div class="log-message-enhanced">${this.escapeHtml(message)}</div>
          </div>
          <div class="log-actions">
            ${expandButton}
          </div>
        </div>
        ${detailsSection}
      </div>
    `;
  }
  
  // Format relative time for better readability
  formatRelativeTime(timestamp) {
    const now = new Date();
    const diff = now - timestamp;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    if (seconds > 0) return `${seconds}s ago`;
    return 'now';
  }
  
  // Bind event listeners for log interactions
  bindLogEventListeners() {
    if (!this.elements.logsContent) return;
    
    // Bind expand/collapse buttons
    this.elements.logsContent.querySelectorAll('.log-expand-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const logEntry = btn.closest('.log-entry-enhanced');
        const details = logEntry.querySelector('.log-details');
        const icon = btn.querySelector('.expand-icon');
        const text = btn.querySelector('.expand-text');
        
        if (details) {
          const isExpanded = details.style.display !== 'none';
          details.style.display = isExpanded ? 'none' : 'block';
          icon.textContent = isExpanded ? '▶' : '▼';
          text.textContent = isExpanded ? 'Details' : 'Hide';
          btn.classList.toggle('expanded', !isExpanded);
        }
      });
    });
  }
  
  // Legacy render method for backward compatibility
  renderLogEntry(timestamp, logLevel, eventType, message, details = null, index = 0) {
    return this.renderEnhancedLogEntryHTML(timestamp, logLevel, eventType, message, details, index, 'info', '📄');
  }
  
  // Handle logs refresh using cached events with force refresh
  async handleLogsRefresh() {
    if (this.state.currentLogsJobId) {
      console.log(`[SettingsWorkflow] Refreshing logs for job ${this.state.currentLogsJobId}`);
      try {
        // Force refresh to get latest events, but preserve cache if API returns empty
        const events = await this.fetchWorkflowEvents(this.state.currentLogsJobId, {
          forceRefresh: true,
          preserveCache: true
        });
        console.log(`[SettingsWorkflow] Refreshed logs with ${events.length} events`);
        if (events.length > 0) {
          this.renderWorkflowLogs(events);
        } else {
          this.emit('notification', {
            message: 'No new log events available',
            type: 'info'
          });
        }
      } catch (error) {
        console.error('[SettingsWorkflow] Failed to refresh logs:', error);
        this.emit('notification', {
          message: `Failed to refresh logs: ${error.message}`,
          type: 'error'
        });
      }
    }
  }
  
  // Handle logs clear
  handleLogsClear() {
    if (this.elements.logsContent) {
      this.elements.logsContent.innerHTML = '<div class="log-entry info">Logs cleared</div>';
    }
  }
  
  // Handle workflow schedule
  async handleWorkflowSchedule(workflowId) {
    const workflow = this.state.workflows.find(w => w.flow_id === workflowId);
    if (!workflow) return;
    
    this.state.currentScheduleWorkflow = workflow;
    this.showScheduleModal();
  }
  
  // Show schedule modal
  showScheduleModal() {
    if (!this.elements.workflowScheduleModal || !this.state.currentScheduleWorkflow) return;
    
    // Update modal title and info
    if (this.elements.scheduleModalTitle) {
      this.elements.scheduleModalTitle.textContent = 'Schedule Workflow';
    }
    
    if (this.elements.scheduleWorkflowName) {
      this.elements.scheduleWorkflowName.textContent = this.state.currentScheduleWorkflow.name;
    }
    
    // Reset form and initialize new schedule interface
    this.initializeScheduleModal();
    
    // If workflow is already scheduled, populate the form
    if (this.state.currentScheduleWorkflow.schedule) {
      this.populateExistingSchedule(this.state.currentScheduleWorkflow.schedule);
    }
    
    // Show modal
    this.elements.workflowScheduleModal.classList.remove('hidden');
  }

  // Initialize schedule modal with new interface
  initializeScheduleModal() {
    // 1. Reset the form and all associated states
    this.resetScheduleForm();
    
    // 2. Set the schedule type dropdown to 'daily'
    const scheduleTypeSelect = document.getElementById('schedule-type-select');
    if (scheduleTypeSelect) {
      scheduleTypeSelect.value = 'daily';
    }
    
    // 4. Set the default time for the 'daily' option to 8 AM
    const dailyTimeInput = document.getElementById('daily-time');
    if (dailyTimeInput) {
      dailyTimeInput.value = '08:00';
    }
    
    // 5. Hide all other schedule option sections
    this.hideAllScheduleOptions();
    
    // 6. Show the 'daily' schedule options
    this.showScheduleOptions('daily');
    
    // 7. Update the internal state and generate the initial cron expression
    this.updateScheduleFromSimpleBuilder();
  }

  // Reset schedule form
  resetScheduleForm() {
    // Clear all inputs
    const inputs = this.elements.workflowScheduleModal.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
      if (input.type === 'checkbox') {
        input.checked = true; // Default enabled
      } else if (input.type !== 'radio') {
        input.value = '';
      }
    });
    
    // Reset states
    this.scheduleState = {
      selectedTemplate: null,
      scheduleType: 'daily',
      cronExpression: '',
      isValid: false,
      previewTimes: []
    };
    
    // Hide all schedule options and reset to default
    this.hideAllScheduleOptions();
    this.showScheduleOptions('daily');
    
    // Reset button states
    this.updateScheduleSaveButton(false);
  }

  // Update minutes label
  updateMinutesLabel() {
    const minutesInput = document.getElementById('minutes-interval');
    const minutesLabel = document.getElementById('minutes-label');
    if (minutesInput && minutesLabel) {
      const value = parseInt(minutesInput.value) || 1;
      minutesLabel.textContent = value;
    }
  }
  
  // Update hours label
  updateHoursLabel() {
    const hoursInput = document.getElementById('hours-interval');
    const hoursLabel = document.getElementById('hours-label');
    if (hoursInput && hoursLabel) {
      const value = parseInt(hoursInput.value) || 1;
      hoursLabel.textContent = value;
    }
  }

  // Hide all schedule options
  hideAllScheduleOptions() {
    const options = ['every-x-minutes-options', 'every-x-hours-options', 'daily-options', 'weekly-options', 'monthly-options'];
    options.forEach(optionId => {
      const option = document.getElementById(optionId);
      if (option) option.classList.add('hidden');
    });
  }

  // Show schedule options for selected type
  showScheduleOptions(scheduleType) {
    // Corrected ID to match HTML
    const optionId = `${scheduleType}-options`;
    const option = document.getElementById(optionId);
    if (option) {
      option.classList.remove('hidden');
    }
  }

  // Update schedule from simple builder
  updateScheduleFromSimpleBuilder() {
    const scheduleType = document.getElementById('schedule-type-select')?.value;
    if (!scheduleType) return;
    
    let cronExpression = '';
    
    switch (scheduleType) {
      case 'every-x-minutes':
        const minutes = document.getElementById('minutes-interval')?.value || '1';
        cronExpression = `*/${minutes} * * * *`;
        break;
      case 'every-x-hours':
        const hours = document.getElementById('hours-interval')?.value || '1';
        cronExpression = `0 */${hours} * * *`;
        break;
      case 'daily':
        const dailyTime = document.getElementById('daily-time')?.value || '08:00';
        const [dailyHour, dailyMinute] = dailyTime.split(':');
        cronExpression = `${dailyMinute} ${dailyHour} * * *`;
        break;
      case 'weekly':
        const weeklyDay = document.getElementById('weekly-day')?.value || '1';
        const weeklyTime = document.getElementById('weekly-time')?.value || '08:00';
        const [weeklyHour, weeklyMinute] = weeklyTime.split(':');
        cronExpression = `${weeklyMinute} ${weeklyHour} * * ${weeklyDay}`;
        break;
      case 'monthly':
        const monthlyDay = document.getElementById('monthly-day')?.value || '1';
        const monthlyTime = document.getElementById('monthly-time')?.value || '08:00';
        const [monthlyHour, monthlyMinute] = monthlyTime.split(':');
        cronExpression = `${monthlyMinute} ${monthlyHour} ${monthlyDay} * *`;
        break;
    }
    
    if (cronExpression) {
      this.scheduleState.cronExpression = cronExpression;
      this.scheduleState.isValid = this.validateCronExpression(cronExpression);
      this.updateScheduleSaveButton(this.scheduleState.isValid);
    }
  }

  // Handle schedule type change
  handleScheduleTypeChange(scheduleType) {
    if (!scheduleType) return;
    
    console.log('[SettingsWorkflow] Schedule type changed to:', scheduleType);
    
    this.scheduleState.scheduleType = scheduleType;
    
    // Update the select dropdown value
    const scheduleTypeSelect = document.getElementById('schedule-type-select');
    if (scheduleTypeSelect && scheduleTypeSelect.value !== scheduleType) {
      scheduleTypeSelect.value = scheduleType;
    }
    
    // Hide all schedule options
    this.hideAllScheduleOptions();
    
    // Show selected options
    this.showScheduleOptions(scheduleType);
    
    // Force update the UI elements for the new type
    this.updateScheduleTypeUI(scheduleType);
    
    // Update schedule based on new type
    this.updateScheduleFromSimpleBuilder();
    
    // Validation is now handled directly, no need to clear
  }
  
  // Update UI elements for specific schedule type
  updateScheduleTypeUI(scheduleType) {
    console.log('[SettingsWorkflow] Updating UI for schedule type:', scheduleType);
    
    // Set default values for the new type
    switch (scheduleType) {
      case 'daily':
        const dailyTime = document.getElementById('daily-time');
        if (dailyTime && !dailyTime.value) {
          dailyTime.value = '08:00';
        }
        break;
      case 'weekly':
        const weeklyDay = document.getElementById('weekly-day');
        const weeklyTime = document.getElementById('weekly-time');
        if (weeklyDay && weeklyDay.value === '') {
          weeklyDay.value = '1'; // Monday
        }
        if (weeklyTime && !weeklyTime.value) {
          weeklyTime.value = '08:00';
        }
        break;
      case 'monthly':
        const monthlyDay = document.getElementById('monthly-day');
        const monthlyTime = document.getElementById('monthly-time');
        if (monthlyDay && monthlyDay.value === '') {
          monthlyDay.value = '1'; // 1st of month
        }
        if (monthlyTime && !monthlyTime.value) {
          monthlyTime.value = '08:00';
        }
        break;
      case 'every-x-minutes':
        const minutesInterval = document.getElementById('minutes-interval');
        if (minutesInterval && minutesInterval.value === '') {
          minutesInterval.value = '1';
        }
        break;
      case 'every-x-hours':
        const hoursInterval = document.getElementById('hours-interval');
        if (hoursInterval && hoursInterval.value === '') {
          hoursInterval.value = '1';
        }
        break;
    }
  }

  // Handle cron expression change
  handleCronExpressionChange() {
    const cronInput = document.getElementById('custom-cron-input');
    if (cronInput) {
      this.scheduleState.cronExpression = cronInput.value.trim();
      this.validateAndPreviewSchedule();
    }
  }

  // Validate cron expression
  validateCronExpression(cronExpression) {
    if (!cronExpression || typeof cronExpression !== 'string') {
      return false;
    }
    
    try {
      // Use cron-parser library for professional validation
      if (typeof cronParser !== 'undefined') {
        cronParser.parseExpression(cronExpression);
        return true;
      } else {
        // Fallback to basic validation if library not available
        const parts = cronExpression.trim().split(/\s+/);
        
        if (parts.length !== 5) {
          return false;
        }
        
        // Simple validation for each part
        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          
          // Allow common cron special characters
          if (!/^[0-9,\-*/]+$/.test(part)) {
            return false;
          }
        }
        
        return true;
      }
    } catch (error) {
      console.warn('[SettingsWorkflow] Cron expression validation failed:', error);
      return false;
    }
  }

  // Update schedule save button
  updateScheduleSaveButton(isValid) {
    const saveButton = document.getElementById('schedule-save');
    if (!saveButton) return;
    
    const enabledCheckbox = document.getElementById('schedule-enabled');
    const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;
    
    // FIXED: Allow saving when schedule is disabled (to delete it)
    // Only require valid cron expression when schedule is enabled
    const shouldDisable = isEnabled && !isValid;
    
    console.log('[SettingsWorkflow] updateScheduleSaveButton FIXED:', {
      isValid,
      isEnabled,
      shouldDisableButton: shouldDisable,
      logic: 'isEnabled && !isValid',
      previousButtonState: saveButton.disabled
    });
    
    saveButton.disabled = shouldDisable;
  }

  // Populate existing schedule
  populateExistingSchedule(schedule) {
    if (!schedule || !schedule.cron_expression) return;

    // Set enable/disable state and description
    const enabledCheckbox = document.getElementById('schedule-enabled');
    if (enabledCheckbox) enabledCheckbox.checked = schedule.is_enabled;
    const descriptionInput = document.getElementById('schedule-description');
    if (descriptionInput) descriptionInput.value = schedule.description || '';

    // --- Main Logic ---
    const parts = schedule.cron_expression.split(' ');
    const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
    let scheduleType = 'daily'; // Default

    if (minute.startsWith('*/')) scheduleType = 'every-x-minutes';
    else if (hour.startsWith('*/')) scheduleType = 'every-x-hours';
    else if (dayOfWeek !== '*') scheduleType = 'weekly';
    else if (dayOfMonth !== '*') scheduleType = 'monthly';

    // 1. Set the dropdown to the correct type
    const scheduleTypeSelect = document.getElementById('schedule-type-select');
    if (scheduleTypeSelect) scheduleTypeSelect.value = scheduleType;

    // 2. Hide all option panels, then show the correct one
    this.hideAllScheduleOptions();
    this.showScheduleOptions(scheduleType);

    // 3. Populate the inputs for the determined schedule type
    switch (scheduleType) {
      case 'every-x-minutes':
        document.getElementById('minutes-interval').value = minute.replace('*/', '');
        break;
      case 'every-x-hours':
        document.getElementById('hours-interval').value = hour.replace('*/', '');
        break;
      case 'daily':
        document.getElementById('daily-time').value = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
        break;
      case 'weekly':
        document.getElementById('weekly-day').value = dayOfWeek;
        document.getElementById('weekly-time').value = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
        break;
      case 'monthly':
        document.getElementById('monthly-day').value = dayOfMonth;
        document.getElementById('monthly-time').value = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
        break;
    }

    // 4. Regenerate the cron expression from the populated UI to ensure validation and enable the save button
    this.updateScheduleFromSimpleBuilder();
  }
  
  // Hide schedule modal
  hideScheduleModal() {
    if (this.elements.workflowScheduleModal) {
      this.elements.workflowScheduleModal.classList.add('hidden');
    }
    this.state.currentScheduleWorkflow = null;
  }
  
  // Handle schedule save
  async handleScheduleSave() {
    if (!this.state.currentScheduleWorkflow) return;
    
    try {
      const workflowId = this.state.currentScheduleWorkflow.flow_id;
      const enabledCheckbox = document.getElementById('schedule-enabled');
      const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;
      
      // DEBUG: Log save attempt
      console.log('[SettingsWorkflow] handleScheduleSave DEBUG:', {
        workflowId,
        isEnabled,
        hasExistingSchedule: !!this.state.currentScheduleWorkflow.schedule,
        cronExpression: this.scheduleState.cronExpression,
        scheduleValid: this.scheduleState.isValid
      });
      
      // If schedule is disabled, remove it
      if (!isEnabled && this.state.currentScheduleWorkflow.schedule) {
        console.log('[SettingsWorkflow] Deleting schedule because disabled');
        await this.apiClient.deleteSchedule(workflowId);
        
        this.emit('notification', {
          message: 'Workflow schedule disabled',
          type: 'success'
        });
      } else if (this.scheduleState.cronExpression && isEnabled) {
        // Add/update schedule with new interface
        const descriptionInput = document.getElementById('schedule-description');
        const description = descriptionInput ? descriptionInput.value.trim() : '';
        
        const scheduleData = {
          flow_id: workflowId,
          cron_expression: this.scheduleState.cronExpression,
          is_enabled: isEnabled,
          description: description
        };
        
        if (this.state.currentScheduleWorkflow.schedule) {
          // Update existing schedule
          await this.apiClient.updateSchedule(workflowId, scheduleData);
        } else {
          // Create new schedule
          await this.apiClient.createSchedule(scheduleData);
        }
        
        this.emit('notification', {
          message: 'Workflow schedule saved successfully',
          type: 'success'
        });
      } else if (isEnabled) {
        // Enabled but no valid cron expression
        this.emit('notification', {
          message: 'Please configure a valid schedule',
          type: 'error'
        });
        return;
      }
      
      // Reload workflows to update schedule status
      await this.loadWorkflows();
      
      // Close modal
      this.hideScheduleModal();
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to save schedule:', error);
      this.emit('notification', {
        message: `Failed to save schedule: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Handle workflow edit
  handleWorkflowEdit(workflowId) {
    console.log(`[SettingsWorkflow] Edit workflow ${workflowId}`);
    
    // Get backend URL from API client or settings
    const backendUrl = this.apiClient.baseURL || window.CONFIG?.BACKEND_URL || 'http://localhost:8000';
    const editUrl = `${backendUrl}/flow/${workflowId}`;
    
    // Open in new tab using Chrome extension API
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: editUrl });
    } else {
      // Fallback for non-extension context
      window.open(editUrl, '_blank');
    }
  }
  
  // Handle workflow delete
  async handleWorkflowDelete(workflowId) {
    const workflow = this.state.workflows.find(w => w.flow_id === workflowId);
    if (!workflow) return;
    
    this.state.currentDeleteWorkflow = workflow;
    this.showDeleteModal();
  }
  
  // Show delete modal
  showDeleteModal() {
    if (!this.elements.workflowDeleteModal || !this.state.currentDeleteWorkflow) return;
    
    if (this.elements.deleteWorkflowName) {
      this.elements.deleteWorkflowName.textContent = this.state.currentDeleteWorkflow.name;
    }
    
    // Show modal
    this.elements.workflowDeleteModal.classList.remove('hidden');
  }
  
  // Hide delete modal
  hideDeleteModal() {
    if (this.elements.workflowDeleteModal) {
      this.elements.workflowDeleteModal.classList.add('hidden');
    }
    this.state.currentDeleteWorkflow = null;
  }
  
  // Handle delete confirm
  async handleDeleteConfirm() {
    if (!this.state.currentDeleteWorkflow) return;
    
    try {
      const workflowId = this.state.currentDeleteWorkflow.flow_id;
      const workflow = this.state.currentDeleteWorkflow;
      
      // Check if workflow has an associated schedule and delete it first
      if (workflow.scheduled && workflow.schedule) {
        console.log(`[SettingsWorkflow] Deleting associated schedule for workflow ${workflowId}`);
        try {
          await this.apiClient.deleteSchedule(workflowId);
          console.log(`[SettingsWorkflow] Successfully deleted schedule for workflow ${workflowId}`);
        } catch (scheduleError) {
          console.warn(`[SettingsWorkflow] Failed to delete schedule for workflow ${workflowId}:`, scheduleError);
        }
      }
      
      // Delete the workflow
      await this.apiClient.deleteWorkflow(workflowId);
      
      this.emit('notification', {
        message: 'Workflow deleted successfully',
        type: 'success'
      });
      
      // Reload workflows
      await this.loadWorkflows();
      
      // Close modal
      this.hideDeleteModal();
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to delete workflow:', error);
      this.emit('notification', {
        message: `Failed to delete workflow: ${error.message}`,
        type: 'error'
      });
    }
  }

  // Utility function to escape HTML
  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Get workflow state for external access
  getState() {
    return { ...this.state };
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSettingsWorkflow = VibeSurfSettingsWorkflow;
}