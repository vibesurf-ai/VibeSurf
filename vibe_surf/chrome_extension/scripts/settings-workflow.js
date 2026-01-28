
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
    this.elements = {
      // Workflow Tab
      workflowTab: document.getElementById('workflow-tab'),
      createWorkflowBtn: document.getElementById('create-workflow-btn'),
      importWorkflowBtn: document.getElementById('import-workflow-btn'),
      workflowTemplatesBtn: document.getElementById('workflow-templates-btn'),
      recordToWorkflowBtn: document.getElementById('record-to-workflow-btn'),
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
    this.elements.workflowTemplatesBtn?.addEventListener('click', this.handleWorkflowTemplates.bind(this));
    this.elements.recordToWorkflowBtn?.addEventListener('click', this.handleRecordToWorkflow.bind(this));
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
      
      // Show loading state
      this.showWorkflowsLoading();
      
      // Check VibeSurf API key first
      const status = await this.checkVibeSurfStatus();
      
      if (status && status.connected && status.key_valid) {
        // Show workflow interface and load workflows from backend
        this.showWorkflowInterface();
        await this.loadWorkflows();
      } else {
        // Hide loading, hide workflow interface, and show API key modal
        this.hideWorkflowsLoading();
        this.hideWorkflowInterface();
        this.showVibeSurfApiKeyModal();
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflow content:', error);
      this.hideWorkflowsLoading();
      this.hideWorkflowInterface();
      this.emit('notification', {
        message: 'Failed to load workflows',
        type: 'error'
      });
    }
  }
  
  // Check VibeSurf API key status
  async checkVibeSurfStatus() {
    try {
      const response = await this.apiClient.getVibeSurfStatus();
      
      this.state.vibeSurfKeyValid = response.connected && response.key_valid;
      this.state.vibeSurfApiKey = response.has_key ? '***' : null;
      
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
    } else {
      console.error('[SettingsWorkflow] VibeSurf API key modal element not found!');
    }
  }
  
  // Hide VibeSurf API key modal
  hideVibeSurfApiKeyModal() {
    if (this.elements.vibeSurfApiKeyModal) {
      this.elements.vibeSurfApiKeyModal.classList.add('hidden');
    }
    
    // Hide workflow interface when modal is closed without valid API key
    if (!this.state.vibeSurfKeyValid) {
      this.hideWorkflowInterface();
    }
  }
  
  // Handle VibeSurf link open
  handleOpenVibeSurfLink() {
    // Prevent multiple simultaneous tab opening
    if (this._isOpeningVibeSurfLink) {
      return;
    }
    
    this._isOpeningVibeSurfLink = true;
    
    // Open VibeSurf website in new tab using Chrome extension API
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: 'https://vibe-surf.com/' });
    } else {
      // Fallback for non-extension context
      window.open('https://vibe-surf.com/', '_blank');
    }
    
    // Reset flag after a short delay to prevent accidental double-clicks
    setTimeout(() => {
      this._isOpeningVibeSurfLink = false;
    }, 1000);
  }
  
  // Handle VibeSurf API key confirm
  async handleVibeSurfApiKeyConfirm() {
    // Prevent multiple simultaneous submissions
    if (this._isVerifyingVibeSurfKey) {
      return;
    }
    
    this._isVerifyingVibeSurfKey = true;
    
    const apiKey = this.elements.vibeSurfApiKeyInput?.value?.trim();
    
    if (!apiKey) {
      this._isVerifyingVibeSurfKey = false;
      this.showVibeSurfApiKeyValidation('Please enter a VibeSurf API key', 'error');
      return;
    }

    // Disable the confirm button
    if (this.elements.vibeSurfApiKeyConfirm) {
      this.elements.vibeSurfApiKeyConfirm.disabled = true;
    }

    try {
      this.showVibeSurfApiKeyValidation('Validating API key...', 'info');
      
      const response = await this.apiClient.verifyVibeSurfKey(apiKey);
      
      if (response.valid) {
        this.showVibeSurfApiKeyValidation('API key is valid!', 'success');
        
        // Update state
        this.state.vibeSurfKeyValid = true;
        this.state.vibeSurfApiKey = '***';
        
        // Show workflow interface and load workflows after successful validation
        this.showWorkflowInterface();
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
    } finally {
      // Always reset the verification flag and re-enable button
      this._isVerifyingVibeSurfKey = false;
      if (this.elements.vibeSurfApiKeyConfirm) {
        this.elements.vibeSurfApiKeyConfirm.disabled = false;
      }
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
      
      // First get the project ID
      const projects = await this.apiClient.getProjects();
      
      if (!Array.isArray(projects) || projects.length === 0) {
        console.warn('[SettingsWorkflow] No projects found');
        this.state.workflows = [];
        this.state.filteredWorkflows = [];
        this.renderWorkflows();
        return;
      }
      
      // Use the first project (typically "Starter Project")
      const projectId = projects[0].id;
      console.log("Project ID:", projectId);
      
      // Get workflows with updated_at using the new API
      const projectData = await this.apiClient.getProjectFlows(projectId);
      console.log(projectData);
      
      // Extract workflows from the flows.items array
      let workflows = [];
      if (projectData && projectData.flows && Array.isArray(projectData.flows.items)) {
        workflows = projectData.flows.items;
      } else {
        console.warn('[SettingsWorkflow] Unexpected project data structure:', projectData);
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
      
      // Load schedule information for workflows
      await this.loadWorkflowSchedules();
      
      // Load skill states for workflows
      await this.loadWorkflowSkillStates();
      
      // Apply current search and filter
      this.filterWorkflows();
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflows:', error);
      this.state.workflows = [];
      this.state.filteredWorkflows = [];
      this.renderWorkflows();
      throw error;
    }
  }
  
  // Load workflow skill states from database
  async loadWorkflowSkillStates() {
    try {
      const response = await this.apiClient.getEnabledSkills();
      
      if (response && response.success && Array.isArray(response.skills)) {
        // Create a map of flow_id -> skill state
        const skillMap = new Map();
        response.skills.forEach(skill => {
          if (skill.flow_id) {
            skillMap.set(skill.flow_id, true);
          }
        });
        
        // Update workflows with skill state
        this.state.workflows.forEach(workflow => {
          workflow.add_to_skill = skillMap.has(workflow.flow_id);
        });
        
        console.log(`[SettingsWorkflow] Loaded skill states for ${skillMap.size} workflows`);
      } else {
        // No skills enabled, set all to false
        this.state.workflows.forEach(workflow => {
          workflow.add_to_skill = false;
        });
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load workflow skill states:', error);
      // Continue without skill state information - set all as disabled
      this.state.workflows.forEach(workflow => {
        workflow.add_to_skill = false;
      });
    }
  }
  
  // Load workflow schedules
  async loadWorkflowSchedules() {
    try {
      const response = await this.apiClient.getSchedules();
      
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
      
      // Add schedule information to workflows
      if (Array.isArray(schedules) && schedules.length > 0) {
        this.state.workflows.forEach(workflow => {
          const schedule = schedules.find(s => s && s.flow_id === workflow.flow_id);
          workflow.scheduled = !!schedule;
          workflow.schedule = schedule; // This contains schedule.id which we'll need for API calls
        });
      } else {
        // Set all workflows as unscheduled
        this.state.workflows.forEach(workflow => {
          workflow.scheduled = false;
          workflow.schedule = null;
        });
      }
      
    } catch (error) {
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
  
  // Show workflow interface elements (buttons, search, filter, list)
  showWorkflowInterface() {
    const interfaceElements = [
      this.elements.createWorkflowBtn,
      this.elements.importWorkflowBtn,
      this.elements.workflowTemplatesBtn,
      this.elements.recordToWorkflowBtn,
      this.elements.workflowSearch,
      this.elements.workflowFilter,
      this.elements.workflowsList
    ];
    
    interfaceElements.forEach(element => {
      if (element) {
        element.style.display = '';
      }
    });
  }
  
  // Hide workflow interface elements (buttons, search, filter, list)
  hideWorkflowInterface() {
    const interfaceElements = [
      this.elements.createWorkflowBtn,
      this.elements.importWorkflowBtn,
      this.elements.workflowTemplatesBtn,
      this.elements.recordToWorkflowBtn,
      this.elements.workflowSearch,
      this.elements.workflowFilter,
      this.elements.workflowsList
    ];
    
    interfaceElements.forEach(element => {
      if (element) {
        element.style.display = 'none';
      }
    });
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
      }
      if (this.elements.workflowDescriptionInput) {
        this.elements.workflowDescriptionInput.value = '';
      }
      this.hideCreateWorkflowValidation();
      
      // Focus on name input
      setTimeout(() => {
        if (this.elements.workflowNameInput) {
          this.elements.workflowNameInput.focus();
        }
      }, 100);

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
      
      // Set default import method to JSON file immediately (no setTimeout to avoid conflicts)
      const jsonFileRadio = document.querySelector('input[name="import-method"][value="json-file"]');
      if (jsonFileRadio) {
        jsonFileRadio.checked = true;
        this.handleImportMethodChange();
      }
    } else {
      console.error('[SettingsWorkflow] ❌ CRITICAL ERROR: Import workflow modal element not found!');
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
    
    console.log('[SettingsWorkflow] Import method changed to:', selectedMethod);
    
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
  handleSelectJsonFile(event) {
    // Prevent multiple simultaneous file selections
    if (this._isSelectingJsonFile) {
      return;
    }
    
    // Prevent any propagation and default behavior
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    this._isSelectingJsonFile = true;
    
    // Clear any existing selection first to ensure change event fires
    if (this.elements.workflowJsonFile) {
      this.elements.workflowJsonFile.value = '';
    }
    
    // Trigger file selection immediately (no setTimeout to avoid conflicts)
    setTimeout(() => {
      if (this.elements.workflowJsonFile) {
        this.elements.workflowJsonFile.click();
      }
      // Reset flag after a brief delay
      setTimeout(() => {
        this._isSelectingJsonFile = false;
      }, 100);
    }, 0);
  }
  
  // Handle JSON file selection change
  handleJsonFileChange(event) {
    const file = event.target.files[0];
    
    console.log('[SettingsWorkflow] File selected:', file ? file.name : 'none');
    
    if (file) {
      // Validate file type
      const isValidJson = file.type === 'application/json' || file.name.endsWith('.json');
      
      if (!isValidJson) {
        console.log('[SettingsWorkflow] Invalid file type:', file.type, file.name);
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
      console.log('[SettingsWorkflow] File selection successful:', file.name);
    } else {
      console.log('[SettingsWorkflow] No file selected or file cleared');
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
    this.renderWorkflows();
  }
  
  // Render workflows list
  renderWorkflows() {
    
    if (!this.elements.workflowsList) {
      console.error('[SettingsWorkflow] workflowsList element not found!');
      return;
    }
    
    this.hideWorkflowsLoading();
    
    const workflows = this.state.filteredWorkflows;
    
    if (workflows.length === 0) {
      const isEmpty = this.state.workflows.length === 0;
      this.elements.workflowsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚡</div>
          <div class="empty-state-title">${isEmpty ? window.i18n.getMessage('noWorkflowsFound') : window.i18n.getMessage('noMatchingWorkflows')}</div>
          <div class="empty-state-description">
            ${isEmpty ? window.i18n.getMessage('createFirstWorkflowHelp') : window.i18n.getMessage('adjustSearchCriteria')}
          </div>
          ${isEmpty ? `<button class="btn btn-primary create-workflow-empty-btn">${window.i18n.getMessage('createNewWorkflow')}</button>` : ''}
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
    const addToSkillLabel = window.i18n.getMessage('addToSkill');
    const flowIdLabel = window.i18n.getMessage('flowId');
    const copyFlowIdTitle = window.i18n.getMessage('copyFlowId');
    const scheduledLabel = window.i18n.getMessage('filterScheduled');
    const runningLabel = window.i18n.getMessage('filterRunning');
    const runLabel = window.i18n.getMessage('runWorkflow');
    const pauseLabel = window.i18n.getMessage('pause');
    const logsLabel = window.i18n.getMessage('workflowLogs');
    const scheduleLabel = window.i18n.getMessage('scheduleWorkflow');
    const deleteLabel = window.i18n.getMessage('deleteWorkflow');

    return `
      <div class="workflow-card" data-workflow-id="${workflow.flow_id}">
        <div class="workflow-header">
          <div class="workflow-info">
            <div class="workflow-name">${this.escapeHtml(workflow.name)}</div>
            <div class="workflow-description">${this.escapeHtml(workflow.description)}</div>
            <div class="workflow-flow-id">
              <span class="flow-id-label">${flowIdLabel}:</span>
              <code class="flow-id-value" title="${window.i18n.getMessage('clickToCopy')}">${workflow.flow_id}</code>
              <button class="btn btn-icon copy-flow-id" data-flow-id="${workflow.flow_id}" title="${copyFlowIdTitle}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M16 4H18C19.1046 4 20 4.89543 20 6V18C20 19.1046 19.1046 20 18 20H6C4.89543 20 4 19.1046 4 18V6C4 4.89543 4.89543 4 6 4H8" stroke="currentColor" stroke-width="2"/>
                  <rect x="8" y="2" width="8" height="4" rx="1" stroke="currentColor" stroke-width="2"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="workflow-status">
            ${workflow.scheduled ? `<span class="status-badge scheduled">${scheduledLabel}</span>` : ''}
            ${isRunning ? `<span class="status-badge running">${runningLabel}</span>` : ''}
            <div class="workflow-skill-toggle" title="${addToSkillLabel}">
              <label class="toggle-switch">
                <input type="checkbox" class="skill-toggle-input" data-flow-id="${workflow.flow_id}" ${workflow.add_to_skill ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
              <span class="toggle-label">${addToSkillLabel}</span>
            </div>
          </div>
        </div>
        <div class="workflow-actions">
          <button class="btn btn-primary workflow-run-btn" data-workflow-id="${workflow.flow_id}"
                  ${isRunning ? 'style="display: none;"' : ''}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <polygon points="5,3 19,12 5,21" stroke="currentColor" stroke-width="2" fill="currentColor"/>
            </svg>
            ${runLabel}
          </button>
          <button class="btn btn-secondary workflow-pause-btn" data-workflow-id="${workflow.flow_id}" data-job-id="${jobInfo?.job_id || ''}"
                  ${!isRunning ? 'style="display: none;"' : ''}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect x="6" y="4" width="4" height="16" stroke="currentColor" stroke-width="2" fill="currentColor"/>
              <rect x="14" y="4" width="4" height="16" stroke="currentColor" stroke-width="2" fill="currentColor"/>
            </svg>
            ${pauseLabel}
          </button>
          <button class="btn btn-secondary workflow-logs-btn" data-workflow-id="${workflow.flow_id}" data-job-id="${jobInfo?.job_id || ''}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" stroke-width="2"/>
              <polyline points="14,2 14,8 20,8" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/>
              <polyline points="10,9 9,9 8,9" stroke="currentColor" stroke-width="2"/>
            </svg>
            ${logsLabel}
          </button>
          <button class="btn btn-secondary workflow-schedule-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="currentColor" stroke-width="2"/>
              <line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" stroke-width="2"/>
              <line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" stroke-width="2"/>
              <line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" stroke-width="2"/>
            </svg>
            ${scheduleLabel}
          </button>
          <button class="btn btn-secondary workflow-edit-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2"/>
              <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2"/>
            </svg>
            ${window.i18n.getMessage('edit')}
          </button>
          <button class="btn btn-secondary workflow-download-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" stroke-width="2"/>
              <polyline points="7,10 12,15 17,10" stroke="currentColor" stroke-width="2"/>
              <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" stroke-width="2"/>
            </svg>
            ${window.i18n.getMessage('download')}
          </button>
          <button class="btn btn-danger workflow-delete-btn" data-workflow-id="${workflow.flow_id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M3 6H5H21" stroke="currentColor" stroke-width="2"/>
              <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2"/>
            </svg>
            ${deleteLabel}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Re-render all workflows with current language
   * This should be called when language changes to update dynamically rendered content
   */
  rerenderAllWorkflows() {
    console.log('[SettingsWorkflow] Re-rendering all workflows for language change');
    this.renderWorkflows();
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
    
    // Download buttons
    this.elements.workflowsList.querySelectorAll('.workflow-download-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowDownload(btn.dataset.workflowId);
      });
    });
    
    // Delete buttons
    this.elements.workflowsList.querySelectorAll('.workflow-delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleWorkflowDelete(btn.dataset.workflowId);
      });
    });
    
    // Skill toggle checkboxes
    this.elements.workflowsList.querySelectorAll('.skill-toggle-input').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        this.handleSkillToggle(checkbox.dataset.flowId, checkbox.checked);
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
    
    // Check cache first
    const cached = this.state.eventCache.get(jobId);
    const now = Date.now();
    

    // Persistent cache for completed workflows - NEVER refresh unless explicitly forced
    if (cached && cached.isPersistent && !forceRefresh) {
      return cached.events;
    }
    
    // For completed workflows, always prefer cached events to prevent loss
    if (cached && cached.isComplete && cached.events.length > 0 && !forceRefresh) {
      return cached.events;
    }
    
    if (cached && !forceRefresh && (now - cached.lastFetch) < maxAge) {
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
          finalEvents = cached.events;
          shouldUpdateCache = false; // Don't update cache with empty result
        } else if (events.length < cached.events.length && !hasEndEvent) {
          // API returned fewer events and workflow not complete - suspicious, preserve cache
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
          
          // Update workflow-to-job mapping for completed workflows
          if (cacheEntry.workflowId) {
            this.state.workflowJobMapping.set(cacheEntry.workflowId, {
              jobId: jobId,
              completedAt: now,
              eventCount: finalEvents.length
            });
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
    
    if (!this.state.eventSubscribers.has(jobId)) {
      this.state.eventSubscribers.set(jobId, new Set());
    }
    this.state.eventSubscribers.get(jobId).add(callback);
    
    // Return unsubscribe function
    return () => {
      const subscribers = this.state.eventSubscribers.get(jobId);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.state.eventSubscribers.delete(jobId);
        }
      }
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
    };
    
    const checkStatus = async (events, isComplete) => {
      try {
        if (isComplete || !this.state.runningJobs.has(workflowId)) {
          this.state.runningJobs.delete(workflowId);
          
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
    
    const workflow = this.state.workflows.find(w => w.flow_id === workflowId);
    if (!workflow) {
      console.log(`[SettingsWorkflow] ❌ Workflow not found: ${workflowId}`);
      return;
    }
    
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
      this.elements.logsModalTitle.textContent = window.i18n.getMessage('workflowLogs');
    }

    if (this.elements.logsWorkflowName) {
      this.elements.logsWorkflowName.textContent = this.state.currentLogsWorkflow.name;
    }

    if (this.elements.logsJobId) {
      this.elements.logsJobId.textContent = this.state.currentLogsJobId || window.i18n.getMessage('noActiveJob');
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
        this.elements.logsContent.innerHTML = `<div class="log-entry info">${window.i18n.getMessage('noActiveJobToShowLogs')}</div>`;
        return;
      }
      
      // First, ALWAYS check persistent cache - this is the key fix
      let events = [];
      const cached = this.state.eventCache.get(jobId);
      
      // Prioritize persistent cached events (completed workflows)
      if (cached && cached.isPersistent && cached.events.length > 0) {
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
        events = cached.events;
        
        // Render cached events immediately for better UX
        this.renderWorkflowLogs(events);
        
        // Check if this is a completed workflow that should be marked as persistent
        if (cached.isComplete && !cached.isPersistent) {
          this.state.eventCache.set(jobId, {
            ...cached,
            isPersistent: true,
            completedAt: cached.completedAt || Date.now()
          });
        }
        
        // Only fetch fresh events for running jobs (don't fetch for completed jobs)
        if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id) && !cached.isComplete && !cached.isPersistent) {
          this.fetchWorkflowEvents(jobId, { preserveCache: true, maxAge: 2000 }).then(freshEvents => {
            if (freshEvents.length > events.length) {
              this.renderWorkflowLogs(freshEvents);
            }
          }).catch(error => {
            console.warn(`[SettingsWorkflow] Background event fetch failed for job ${jobId}:`, error);
          });
        } else if (cached.isComplete || cached.isPersistent) {
          // Update job info display to show completion status
          if (this.elements.logsJobId) {
            this.elements.logsJobId.textContent = `${jobId} (${window.i18n.getMessage('completed')})`;
          }
        }
      } else {
        // Only fetch fresh if no cache exists - but preserve any existing cache
        // Pass workflow context for proper association
        events = await this.fetchWorkflowEvents(jobId, {
          forceRefresh: false,
          preserveCache: true,
          workflowId: this.state.currentLogsWorkflow?.flow_id
        });
        this.renderWorkflowLogs(events);
      }
      
      // Set up real-time updates ONLY if job is still running
      if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id)) {
        
        let unsubscribe;
        const updateLogs = (newEvents, isComplete) => {
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
      const errorMsg = error?.message || error?.toString() || 'Unknown error';
      this.elements.logsContent.innerHTML = `<div class="log-entry error">${window.i18n.getMessage('failedToLoadLogs', [errorMsg])}</div>`;
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
          <div class="log-empty-title">${window.i18n.getMessage('noEventsAvailable')}</div>
          <div class="log-empty-description">${window.i18n.getMessage('noEventsDescription')}</div>
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

      // Extract vertex information if available
      let vertexId = '';
      let vertexName = '';
      if (eventData.data && eventData.data.build_data) {
        const buildData = eventData.data.build_data;
        // Get full vertex ID
        if (buildData.id) {
          vertexId = buildData.id;
        }
        // Try to get component name from build_data
        if (buildData.data && buildData.data.component_display_name) {
          vertexName = buildData.data.component_display_name;
        } else if (buildData.id) {
          // Use vertex ID first part as name if display name not available
          vertexName = buildData.id.split('-')[0];
        }
      } else if (eventData.vertex_id) {
        vertexId = eventData.vertex_id;
        vertexName = eventData.vertex_id.split('-')[0];
      } else if (eventData.data && eventData.data.vertex_id) {
        vertexId = eventData.data.vertex_id;
        vertexName = eventData.data.vertex_id.split('-')[0];
      }

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
          // For vertex events, show the component ID as the main message
          if (vertexId && (eventType === 'end_vertex' || eventType === 'start_vertex')) {
            message = vertexId;
          } else {
            message = this.getEventTypeDescription(eventType, vertexName);
          }
          details = eventData.data;
        }
      } else {
        // For vertex events, show the component ID as the main message
        if (vertexId && (eventType === 'end_vertex' || eventType === 'start_vertex')) {
          message = vertexId;
        } else {
          message = this.getEventTypeDescription(eventType, vertexName);
        }
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
  getEventTypeDescription(eventType, vertexName = '') {
    const descriptions = {
      'vertices_sorted': 'Workflow initialized',
      'on_end': 'Workflow completed',
      'add_message': 'Message generated',
      'stream_end': 'Stream finished',
      'error': 'Error occurred',
      'failed': 'Execution failed',
      'start': 'Started',
      'end': 'Finished',
      'end_vertex': 'Completed',
      'start_vertex': 'Started',
      'unknown': 'System event'
    };

    let baseDescription = descriptions[eventType] || `${eventType} event`;

    // Add vertex name if available (for non-vertex specific events)
    if (vertexName && eventType !== 'end_vertex' && eventType !== 'start_vertex') {
      return `${baseDescription}: ${vertexName}`;
    }

    return baseDescription;
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
    } else if (eventType === 'end' || eventType === 'end_vertex' || eventType === 'on_end' || eventType === 'completed') {
      logLevel = 'success';
      category = 'completion';
      icon = '✅';
    } else if (eventType === 'vertices_sorted' || eventType === 'start' || eventType === 'start_vertex') {
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

    // For vertex events, don't show event type in the header (component ID is the message)
    const isVertexEvent = eventType === 'end_vertex' || eventType === 'start_vertex';
    const eventTypeDisplay = isVertexEvent ? '' : `<span class="event-name">${eventType}</span>`;

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
              ${eventTypeDisplay}
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
          message: window.i18n.getMessage('failedToRefreshLogs', [error.message]),
          type: 'error'
        });
      }
    }
  }
  
  // Handle logs clear
  handleLogsClear() {
    if (this.elements.logsContent) {
      this.elements.logsContent.innerHTML = `<div class="log-entry info">${window.i18n.getMessage('logsCleared')}</div>`;
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
      this.elements.scheduleModalTitle.textContent = window.i18n.getMessage('scheduleWorkflow');
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
      this.scheduleState.isValid = true; // Set valid state when cron expression is generated
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

  // Update schedule save button
  updateScheduleSaveButton(isValid) {
    const saveButton = document.getElementById('schedule-save');
    if (!saveButton) return;
    
    const enabledCheckbox = document.getElementById('schedule-enabled');
    const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;
    
    // FIXED: Allow saving when schedule is disabled (to delete it)
    // Only require valid cron expression when schedule is enabled
    const shouldDisable = isEnabled && !isValid;
    
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
    
    // Prevent multiple simultaneous executions
    if (this._isSavingSchedule) {
      return;
    }
    
    this._isSavingSchedule = true;
    
    // Disable the save button immediately
    const saveButton = document.getElementById('schedule-save');
    if (saveButton) {
      saveButton.disabled = true;
    }
    
    try {
      const workflowId = this.state.currentScheduleWorkflow.flow_id;
      const enabledCheckbox = document.getElementById('schedule-enabled');
      const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;

      // If schedule is disabled, remove it
      if (!isEnabled && this.state.currentScheduleWorkflow.schedule) {
        await this.apiClient.deleteSchedule(workflowId);

        this.emit('notification', {
          message: window.i18n.getMessage('workflowScheduleDisabled'),
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
          // Update existing schedule using flow_id
          await this.apiClient.updateSchedule(workflowId, scheduleData);
        } else {
          // Create new schedule
          await this.apiClient.createSchedule(scheduleData);
        }

        this.emit('notification', {
          message: window.i18n.getMessage('workflowScheduleSaved'),
          type: 'success'
        });
      } else if (isEnabled) {
        // Enabled but no valid cron expression
        this.emit('notification', {
          message: window.i18n.getMessage('scheduleEnabledRequired'),
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
    } finally {
      // Always reset the saving flag and re-enable button
      this._isSavingSchedule = false;
      if (saveButton) {
        saveButton.disabled = false;
      }
    }
  }
  
  // Handle workflow edit
  handleWorkflowEdit(workflowId) {
    
    // Get backend URL from API client or settings
    const backendUrl = this.apiClient.baseURL || window.CONFIG?.BACKEND_URL || 'http://localhost:9335';
    const editUrl = `${backendUrl}/flow/${workflowId}`;
    
    // Open in new tab using Chrome extension API
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: editUrl });
    } else {
      // Fallback for non-extension context
      window.open(editUrl, '_blank');
    }
  }
  
  // Handle workflow download
  async handleWorkflowDownload(workflowId) {
    try {
      console.log(`[SettingsWorkflow] Downloading workflow: ${workflowId}`);
      
      // Call the export API
      const response = await this.apiClient.exportWorkflow(workflowId);
      
      if (response.success && response.file_path) {
        // For Chrome extension, we need to trigger a browser download
        // Since we can't directly access the saved file, we'll fetch the workflow data
        // and trigger a download through the browser
        
        // Get the workflow data first
        const workflowData = await this.apiClient.getWorkflow(workflowId);
        
        // Create the JSON blob
        const jsonBlob = new Blob([JSON.stringify(workflowData, null, 2)], {
          type: 'application/json'
        });
        
        // Create download URL
        const downloadUrl = URL.createObjectURL(jsonBlob);
        
        // Use the filename directly from the response (backend now returns just the filename)
        const fileName = response.file_path || `workflow_${workflowId.slice(0, 4)}.json`;
        
        // Trigger download using Chrome extension API if available
        if (typeof chrome !== 'undefined' && chrome.downloads) {
          chrome.downloads.download({
            url: downloadUrl,
            filename: fileName,
            saveAs: false
          }, (downloadId) => {
            if (chrome.runtime.lastError) {
              console.error('[SettingsWorkflow] Chrome download failed:', chrome.runtime.lastError);
              // Fallback to manual download
              this.triggerManualDownload(downloadUrl, fileName);
            } else {
              this.emit('notification', {
                message: 'Workflow downloaded successfully',
                type: 'success'
              });
            }
            // Clean up the blob URL
            setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
          });
        } else {
          // Fallback for non-extension context or if chrome.downloads is not available
          this.triggerManualDownload(downloadUrl, fileName);
        }
        
      } else {
        this.emit('notification', {
          message: response.message || 'Failed to export workflow',
          type: 'error'
        });
      }
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to download workflow:', error);
      this.emit('notification', {
        message: `Failed to download workflow: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Trigger manual download using a temporary link
  triggerManualDownload(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    this.emit('notification', {
      message: 'Workflow download started',
      type: 'success'
    });
    
    // Clean up the blob URL after a short delay
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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
        try {
          await this.apiClient.deleteSchedule(workflowId);
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

  // Handle workflow templates button
  handleWorkflowTemplates(event) {
    // Prevent any default behavior
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    // Prevent multiple simultaneous tab opening
    if (this._isOpeningWorkflowTemplates) {
      return;
    }
    
    this._isOpeningWorkflowTemplates = true;
    
    // Open VibeSurf workflows page in new tab
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: 'https://vibe-surf.com/workflows' });
    } else {
      // Fallback for non-extension context
      window.open('https://vibe-surf.com/workflows', '_blank');
    }
    
    // Reset flag after a short delay to prevent accidental double-clicks
    setTimeout(() => {
      this._isOpeningWorkflowTemplates = false;
    }, 1000);
  }
  
  // Handle record workflow button
  handleRecordToWorkflow(event) {
    // Prevent any default behavior
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    // Prevent multiple simultaneous modal opening
    if (this._isOpeningRecordModal) {
      return;
    }
    
    this._isOpeningRecordModal = true;
    
    this.showRecordWorkflowDialog();
    
    // Reset flag after modal is shown
    setTimeout(() => {
      this._isOpeningRecordModal = false;
    }, 500);
  }
  
  // Show initial recording dialog
  showRecordWorkflowDialog() {
    // Create dialog if it doesn't exist
    if (!this.elements.recordWorkflowDialog) {
      this.createRecordWorkflowDialog();
    }
    
    // Reset form
    if (this.elements.recordWorkflowNameInput) {
      this.elements.recordWorkflowNameInput.value = '';
    }
    if (this.elements.recordWorkflowDescInput) {
      this.elements.recordWorkflowDescInput.value = '';
    }
    this.hideRecordWorkflowValidation();
    
    // Show dialog
    if (this.elements.recordWorkflowDialog) {
      this.elements.recordWorkflowDialog.classList.remove('hidden');
      setTimeout(() => {
        if (this.elements.recordWorkflowNameInput) {
          this.elements.recordWorkflowNameInput.focus();
        }
      }, 100);
    }
  }
  
  // Create record workflow dialog
  createRecordWorkflowDialog() {
    const dialogHTML = `
      <div id="record-workflow-dialog" class="modal hidden">
        <div class="modal-overlay"></div>
        <div class="modal-content record-workflow-dialog-content">
          <div class="modal-header">
            <h3 data-i18n="recordWorkflow">Record Workflow</h3>
            <button class="modal-close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M6 6L18 18M6 18L18 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label" for="record-workflow-name-input" data-i18n="workflowNameRequired">Workflow Name <span class="required">*</span></label>
              <input type="text" id="record-workflow-name-input" class="form-input" data-i18n-placeholder="enterWorkflowName" placeholder="Enter workflow name" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="record-workflow-desc-input" data-i18n="descriptionOptional">Description (optional)</label>
              <textarea id="record-workflow-desc-input" class="form-textarea" data-i18n-placeholder="describeWorkflow" placeholder="Describe what this workflow does" rows="3"></textarea>
            </div>
            <div id="record-workflow-validation" style="display: none;"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="form-btn secondary" id="record-workflow-cancel"><span data-i18n="cancel">Cancel</span></button>
            <button type="button" class="form-btn primary" id="record-workflow-start"><span data-i18n="confirm">Confirm</span></button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', dialogHTML);

    this.elements.recordWorkflowDialog = document.getElementById('record-workflow-dialog');
    this.elements.recordWorkflowNameInput = document.getElementById('record-workflow-name-input');
    this.elements.recordWorkflowDescInput = document.getElementById('record-workflow-desc-input');
    this.elements.recordWorkflowValidation = document.getElementById('record-workflow-validation');
    this.elements.recordWorkflowCancel = document.getElementById('record-workflow-cancel');
    this.elements.recordWorkflowStart = document.getElementById('record-workflow-start');

    // Bind events
    if (this.elements.recordWorkflowCancel) {
      this.elements.recordWorkflowCancel.addEventListener('click', this.hideRecordWorkflowDialog.bind(this));
    }
    if (this.elements.recordWorkflowStart) {
      this.elements.recordWorkflowStart.addEventListener('click', this.handleStartRecording.bind(this));
    }

    const modalClose = this.elements.recordWorkflowDialog?.querySelector('.modal-close');
    if (modalClose) {
      modalClose.addEventListener('click', this.hideRecordWorkflowDialog.bind(this));
    }

    const modalOverlay = this.elements.recordWorkflowDialog?.querySelector('.modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', this.hideRecordWorkflowDialog.bind(this));
    }

    // Translate the dialog content
    if (window.i18n && window.i18n.translatePage) {
      window.i18n.translatePage(this.elements.recordWorkflowDialog);
    }
  }

  // Hide record workflow dialog
  hideRecordWorkflowDialog() {
    if (this.elements.recordWorkflowDialog) {
      this.elements.recordWorkflowDialog.classList.add('hidden');
    }
  }
  
  // Show record workflow validation message
  showRecordWorkflowValidation(message, type) {
    if (!this.elements.recordWorkflowValidation) return;
    
    const className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
    this.elements.recordWorkflowValidation.innerHTML = `
      <div class="validation-message ${className}">
        ${this.escapeHtml(message)}
      </div>
    `;
    this.elements.recordWorkflowValidation.style.display = 'block';
  }
  
  // Hide record workflow validation message
  hideRecordWorkflowValidation() {
    if (this.elements.recordWorkflowValidation) {
      this.elements.recordWorkflowValidation.style.display = 'none';
      this.elements.recordWorkflowValidation.innerHTML = '';
    }
  }
  
  // Handle start recording
  async handleStartRecording() {
    const name = this.elements.recordWorkflowNameInput?.value?.trim();
    const description = this.elements.recordWorkflowDescInput?.value?.trim() || '';
    
    if (!name) {
      this.showRecordWorkflowValidation('Please enter a workflow name', 'error');
      return;
    }
    
    // Store workflow info for later
    this.recordingWorkflowInfo = {
      name: name,
      description: description
    };
    
    // Hide dialog and show recording page
    this.hideRecordWorkflowDialog();
    this.showRecordingPage();
  }
  
  // Show recording page
  showRecordingPage() {
    // Create recording page if it doesn't exist
    if (!this.elements.recordingPage) {
      this.createRecordingPage();
    }
    
    // Reset recording state
    this.recordingState = {
      isRecording: false,
      steps: [],
      startTime: null
    };
    
    // Reset recording button state
    this.updateRecordingButton(false, false);

    // Clear previous steps
    if (this.elements.recordingStepsList) {
      const clickToBeginLabel = window.i18n?.getMessage('clickStartRecordingToBegin') || 'Click "Start Recording" to begin';
      this.elements.recordingStepsList.innerHTML = `<div class="no-steps-message">${clickToBeginLabel}</div>`;
    }
    
    // Show page
    if (this.elements.recordingPage) {
      this.elements.recordingPage.classList.remove('hidden');
    }
  }
  
  // Create recording page
  createRecordingPage() {
    const recordingLabel = window.i18n?.getMessage('recording') || 'Recording';
    const startRecordingLabel = window.i18n?.getMessage('startRecording') || 'Start Recording';
    const recordedStepsLabel = window.i18n?.getMessage('recordedSteps') || 'Recorded Steps';
    const clickToBeginLabel = window.i18n?.getMessage('clickStartRecordingToBegin') || 'Click "Start Recording" to begin';

    const pageHTML = `
      <div id="recording-page" class="modal hidden">
        <div class="modal-overlay"></div>
        <div class="modal-content recording-page-content">
          <div class="modal-header">
            <h3>${recordingLabel}: <span id="recording-workflow-title">Workflow</span></h3>
            <button class="modal-close" id="recording-page-close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M6 6L18 18M6 18L18 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="recording-controls">
              <button id="recording-toggle-btn" class="recording-toggle-btn">
                <span class="recording-btn-text">${startRecordingLabel}</span>
                <div class="recording-indicator hidden"></div>
              </button>
            </div>
            <div class="recording-steps-container">
              <h4 data-i18n="recordedSteps">${recordedStepsLabel}</h4>
              <div id="recording-steps-list" class="recording-steps-list">
                <div class="no-steps-message">${clickToBeginLabel}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', pageHTML);

    this.elements.recordingPage = document.getElementById('recording-page');
    this.elements.recordingWorkflowTitle = document.getElementById('recording-workflow-title');
    this.elements.recordingToggleBtn = document.getElementById('recording-toggle-btn');
    this.elements.recordingStepsList = document.getElementById('recording-steps-list');
    this.elements.recordingPageClose = document.getElementById('recording-page-close');

    // Set workflow name
    if (this.elements.recordingWorkflowTitle && this.recordingWorkflowInfo) {
      this.elements.recordingWorkflowTitle.textContent = this.recordingWorkflowInfo.name;
    }

    // Bind events
    if (this.elements.recordingToggleBtn) {
      this.elements.recordingToggleBtn.addEventListener('click', this.handleRecordingToggle.bind(this));
    }
    if (this.elements.recordingPageClose) {
      this.elements.recordingPageClose.addEventListener('click', this.handleRecordingPageClose.bind(this));
    }

    const modalOverlay = this.elements.recordingPage?.querySelector('.modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', this.handleRecordingPageClose.bind(this));
    }
  }
  
  // Handle recording toggle (start/stop)
  async handleRecordingToggle() {
    if (!this.recordingState.isRecording) {
      // Start recording
      await this.startWorkflowRecording();
    } else {
      // Stop recording
      await this.stopWorkflowRecording();
    }
  }
  
  // Start workflow recording
  async startWorkflowRecording() {
    try {
      // Send message to background script to start recording
      const response = await chrome.runtime.sendMessage({ type: 'START_RECORDING' });
      
      if (response && response.success) {
        // Explicitly reset recording steps
        this.recordingState.steps = [];
        this.updateStepsDisplay([]);
        
        this.recordingState.isRecording = true;
        this.recordingState.startTime = response.startTime || Date.now();
        this.recordingState.steps = [];
        
        // Notify all tabs to start capturing user interactions
        try {
          const tabs = await chrome.tabs.query({});
          for (const tab of tabs) {
            if (tab.url && !tab.url.startsWith('chrome://') && !tab.url.startsWith('chrome-extension://')) {
              chrome.tabs.sendMessage(tab.id, { type: 'START_RECORDING_CONTENT' }).catch(() => {
                // Ignore errors - content script may not be loaded
              });
            }
          }
        } catch (error) {
          console.warn('[SettingsWorkflow] Failed to notify content scripts:', error);
        }
        
        // Update UI
        this.updateRecordingButton(true);
        
        // Start polling for steps
        this.startStepsPolling();
        
        this.emit('notification', {
          message: 'Recording started',
          type: 'success'
        });
      } else {
        throw new Error(response?.error || 'Failed to start recording');
      }
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to start recording:', error);
      this.emit('notification', {
        message: `Failed to start recording: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Stop workflow recording and auto-save
  async stopWorkflowRecording() {
    try {
      // Notify all tabs to stop capturing
      try {
        const tabs = await chrome.tabs.query({});
        for (const tab of tabs) {
          if (tab.url && !tab.url.startsWith('chrome://') && !tab.url.startsWith('chrome-extension://')) {
            chrome.tabs.sendMessage(tab.id, { type: 'STOP_RECORDING_CONTENT' }).catch(() => {
              // Ignore errors
            });
          }
        }
      } catch (error) {
        console.warn('[SettingsWorkflow] Failed to notify content scripts:', error);
      }
      
      // Stop the recording and get the final workflow data
      const stopResponse = await chrome.runtime.sendMessage({ type: 'STOP_RECORDING' });
      
      if (stopResponse && stopResponse.success) {
        // Extract steps directly from stopResponse
        const steps = stopResponse.workflow?.steps || [];
        this.recordingState.steps = steps;
        this.recordingState.isRecording = false;
        
        // Stop polling
        this.stopStepsPolling();
        
        // Update UI to show "Saving..." state
        this.updateRecordingButton(false, true); // false = not recording, true = saving
        
        // Auto-save immediately
        if (steps.length > 0) {
          await this.handleSaveWorkflow();
        } else {
          // No steps recorded - just show message
          this.updateRecordingButton(false, false);
          this.emit('notification', {
            message: 'No steps recorded',
            type: 'warning'
          });
        }
      } else {
        throw new Error(stopResponse?.error || 'Failed to stop recording');
      }
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to stop recording:', error);
      this.updateRecordingButton(false, false);
      this.emit('notification', {
        message: `Failed to stop recording: ${error.message}`,
        type: 'error'
      });
    }
  }
  
  // Handle Save Workflow (now called automatically after stop)
  async handleSaveWorkflow() {
    if (!this.recordingState.steps || this.recordingState.steps.length === 0) {
      this.emit('notification', {
        message: 'No steps recorded to save',
        type: 'warning'
      });
      return;
    }
    
    try {
      // Save recording to backend
      const result = await this.saveRecording(this.recordingState.steps);
      
      // Show success result dialog
      this.showWorkflowSaveResultDialog({
        success: true,
        message: 'Workflow saved successfully',
        workflow_id: result.workflow_id,
        langflow_path: result.langflow_path
      });
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to save workflow:', error);
      this.updateRecordingButton(false, false);
      
      // Show error result dialog
      this.showWorkflowSaveResultDialog({
        success: false,
        message: error.message || 'Failed to save workflow'
      });
    }
  }
  
  // Save recording to backend
  async saveRecording(steps) {
    try {
      const backendUrl = this.apiClient.baseURL || window.CONFIG?.BACKEND_URL || 'http://127.0.0.1:9335';
      
      const response = await fetch(`${backendUrl}/api/vibesurf/workflows/save-recording`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: this.recordingWorkflowInfo.name,
          description: this.recordingWorkflowInfo.description,
          workflows: steps
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      console.log('[SettingsWorkflow] Recording saved:', data);
      
      return data;
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to save recording:', error);
      throw error;
    }
  }
  
  // Update recording button appearance
  updateRecordingButton(isRecording, isSaving = false) {
    if (!this.elements.recordingToggleBtn) return;

    const btnText = this.elements.recordingToggleBtn.querySelector('.recording-btn-text');
    const indicator = this.elements.recordingToggleBtn.querySelector('.recording-indicator');
    const startRecordingLabel = window.i18n?.getMessage('startRecording') || 'Start Recording';
    const savingLabel = window.i18n?.getMessage('saving') || 'Saving...';

    if (isRecording) {
      this.elements.recordingToggleBtn.classList.add('recording');
      this.elements.recordingToggleBtn.disabled = false;
      if (btnText) btnText.style.display = 'none';
      if (indicator) indicator.classList.remove('hidden');
    } else if (isSaving) {
      this.elements.recordingToggleBtn.classList.remove('recording');
      this.elements.recordingToggleBtn.disabled = true;
      if (btnText) {
        btnText.textContent = savingLabel;
        btnText.style.display = 'block';
      }
      if (indicator) indicator.classList.add('hidden');
    } else {
      this.elements.recordingToggleBtn.classList.remove('recording');
      this.elements.recordingToggleBtn.disabled = false;
      if (btnText) {
        btnText.textContent = startRecordingLabel;
        btnText.style.display = 'block';
      }
      if (indicator) indicator.classList.add('hidden');
    }
  }
  
  // Start polling for steps (reduced frequency)
  startStepsPolling() {
    this.stopStepsPolling(); // Clear any existing interval
    
    this.stepsPollingInterval = setInterval(async () => {
      try {
        const response = await chrome.runtime.sendMessage({ type: 'GET_RECORDING_DATA' });
        // Extract steps from workflow object in response
        if (response && response.workflow && response.workflow.steps) {
          this.updateStepsDisplay(response.workflow.steps);
        } else if (response && response.steps) {
          // Fallback for direct steps format
          this.updateStepsDisplay(response.steps);
        }
      } catch (error) {
        console.error('[SettingsWorkflow] Failed to poll steps:', error);
      }
    }, 2000); // Poll every 2 seconds (reduced from 1 second)
  }
  
  // Stop polling for steps
  stopStepsPolling() {
    if (this.stepsPollingInterval) {
      clearInterval(this.stepsPollingInterval);
      this.stepsPollingInterval = null;
    }
  }
  
  // Update steps display
  updateStepsDisplay(steps) {
    if (!this.elements.recordingStepsList) return;

    const noStepsLabel = window.i18n?.getMessage('noStepsRecordedYet') || 'No steps recorded yet';

    if (steps.length === 0) {
      this.elements.recordingStepsList.innerHTML = `<div class="no-steps-message">${noStepsLabel}</div>`;
      return;
    }

    const stepsHTML = steps.map((step, index) => {
      const time = new Date(step.timestamp).toLocaleTimeString();
      return `
        <div class="recording-step">
          <div class="step-index">${index + 1}</div>
          <div class="step-info">
            <div class="step-type">${this.escapeHtml(step.type)}</div>
            <div class="step-details">${this.getStepDetails(step)}</div>
            <div class="step-time">${time}</div>
          </div>
        </div>
      `;
    }).join('');

    this.elements.recordingStepsList.innerHTML = stepsHTML;
    // Auto-scroll to bottom
    this.elements.recordingStepsList.scrollTop = this.elements.recordingStepsList.scrollHeight;
  }
  
  // Get step details for display
  getStepDetails(step) {
    switch (step.type) {
      case 'navigate':
        return this.escapeHtml(step.url || 'Unknown URL');
      case 'click':
        if (step.target_text && step.target_text !== 'Unknown Element') {
          return `Clicked on "${this.escapeHtml(step.target_text)}"`;
        } else if (step.target_selector) {
          return `Clicked on ${this.escapeHtml(step.target_selector)}`;
        } else if (step.coordinates && step.coordinates.x !== undefined) {
          return `Clicked at (${step.coordinates.x}, ${step.coordinates.y})`;
        } else if (step.x !== undefined && step.y !== undefined) {
          return `Clicked at (${step.x}, ${step.y})`;
        } else {
          return 'Click action';
        }
      case 'input':
        const inputTarget = step.target_text && step.target_text !== 'Input Field' ?
          `"${this.escapeHtml(step.target_text)}"` :
          (step.target_selector ? this.escapeHtml(step.target_selector) : 'input field');
        return `Typed "${this.escapeHtml(step.value || '')}" into ${inputTarget}`;
      case 'scroll':
        return `Scrolled to (${step.scrollX}, ${step.scrollY})`;
      case 'navigate':
        return `Navigated to ${this.escapeHtml(step.url || 'Unknown URL')}`;
      case 'keypress':
        return `Pressed key "${this.escapeHtml(step.key)}"`;
      default:
        return `Action: ${this.escapeHtml(step.type)}`;
    }
  }
  
  // Handle recording page close
  handleRecordingPageClose() {
    if (this.recordingState.isRecording) {
      // Confirm before closing if recording
      if (confirm(window.i18n.getMessage('confirmStopRecording'))) {
        this.stopStepsPolling();
        chrome.runtime.sendMessage({ type: 'STOP_RECORDING' });
        this.hideRecordingPage();
      }
    } else {
      this.hideRecordingPage();
    }
  }
  
  // Hide recording page
  hideRecordingPage() {
    this.stopStepsPolling();
    if (this.elements.recordingPage) {
      this.elements.recordingPage.classList.add('hidden');
    }
  }

  // Show workflow save result dialog
  showWorkflowSaveResultDialog(result) {
    // Create dialog if it doesn't exist
    if (!this.elements.workflowSaveResultDialog) {
      this.createWorkflowSaveResultDialog();
    }
    
    const { success, message, workflow_id, langflow_path } = result;
    
    // Update dialog content
    const dialogTitle = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-title');
    const dialogIcon = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-icon');
    const dialogMessage = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-message');
    const dialogDetails = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-details');
    const dialogConfirm = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-confirm');
    
    if (success) {
      if (dialogTitle) dialogTitle.textContent = 'Workflow Saved Successfully';
      if (dialogIcon) dialogIcon.textContent = '✅';
      if (dialogMessage) dialogMessage.textContent = message;
      
      // Show workflow details
      if (dialogDetails && workflow_id) {
        dialogDetails.innerHTML = `
          <div class="result-detail-item">
            <span class="result-detail-label">Workflow ID:</span>
            <div class="result-detail-value">
              <code class="workflow-id-code">${this.escapeHtml(workflow_id)}</code>
              <button class="btn btn-icon copy-workflow-id-btn" data-workflow-id="${workflow_id}" title="Copy Workflow ID">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M16 4H18C19.1046 4 20 4.89543 20 6V18C20 19.1046 19.1046 20 18 20H6C4.89543 20 4 19.1046 4 18V6C4 4.89543 4.89543 4 6 4H8" stroke="currentColor" stroke-width="2"/>
                  <rect x="8" y="2" width="8" height="4" rx="1" stroke="currentColor" stroke-width="2"/>
                </svg>
              </button>
            </div>
          </div>
          ${langflow_path ? `
            <div class="result-detail-item">
              <span class="result-detail-label">Saved to database</span>
              <span class="result-detail-value success-text">✓</span>
            </div>
          ` : ''}
        `;
        dialogDetails.style.display = 'block';
        
        // Bind copy button
        setTimeout(() => {
          const copyBtn = dialogDetails.querySelector('.copy-workflow-id-btn');
          if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
              try {
                await navigator.clipboard.writeText(workflow_id);
                this.emit('notification', {
                  message: 'Workflow ID copied to clipboard',
                  type: 'success'
                });
              } catch (error) {
                console.error('[SettingsWorkflow] Failed to copy workflow ID:', error);
              }
            });
          }
        }, 100);
      } else if (dialogDetails) {
        dialogDetails.style.display = 'none';
      }
    } else {
      if (dialogTitle) dialogTitle.textContent = 'Failed to Save Workflow';
      if (dialogIcon) dialogIcon.textContent = '❌';
      if (dialogMessage) dialogMessage.textContent = message;
      if (dialogDetails) dialogDetails.style.display = 'none';
    }
    
    // Update button state
    this.updateRecordingButton(false, false);
    
    // Show dialog
    if (this.elements.workflowSaveResultDialog) {
      this.elements.workflowSaveResultDialog.classList.remove('hidden');
    }
  }
  
  // Create workflow save result dialog
  createWorkflowSaveResultDialog() {
    const dialogHTML = `
      <div id="workflow-save-result-dialog" class="modal hidden">
        <div class="modal-overlay"></div>
        <div class="modal-content result-dialog-content">
          <div class="modal-body">
            <div class="result-dialog-icon">✅</div>
            <h3 class="result-dialog-title">Workflow Saved Successfully</h3>
            <p class="result-dialog-message">Your workflow has been saved</p>
            <div class="result-dialog-details" style="display: none;"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="form-btn primary result-dialog-confirm">OK</button>
          </div>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', dialogHTML);
    
    this.elements.workflowSaveResultDialog = document.getElementById('workflow-save-result-dialog');
    
    // Bind events
    const confirmBtn = this.elements.workflowSaveResultDialog?.querySelector('.result-dialog-confirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => {
        this.hideWorkflowSaveResultDialog();
      });
    }
    
    const modalOverlay = this.elements.workflowSaveResultDialog?.querySelector('.modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', () => {
        this.hideWorkflowSaveResultDialog();
      });
    }
  }
  
  // Hide workflow save result dialog
  hideWorkflowSaveResultDialog() {
    if (this.elements.workflowSaveResultDialog) {
      this.elements.workflowSaveResultDialog.classList.add('hidden');
    }
    
    // Close all recording-related dialogs
    this.hideRecordingPage();
    
    // Reload workflows to show new one
    this.loadWorkflows();
  }

  // Handle skill toggle
  async handleSkillToggle(flowId, isEnabled) {
    try {
      if (isEnabled) {
        // Show skill configuration modal
        await this.showSkillConfigModal(flowId);
      } else {
        // Disable skill
        await this.apiClient.updateWorkflowExposeConfig(flowId, false, null);
        
        // Update workflow state
        const workflow = this.state.workflows.find(w => w.flow_id === flowId);
        if (workflow) {
          workflow.add_to_skill = false;
        }
        
        this.emit('notification', {
          message: 'Workflow removed from skills',
          type: 'success'
        });
      }
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to toggle skill:', error);
      this.emit('notification', {
        message: `Failed to update skill: ${error.message}`,
        type: 'error'
      });
      
      // Revert checkbox state
      const checkbox = document.querySelector(`.skill-toggle-input[data-flow-id="${flowId}"]`);
      if (checkbox) {
        checkbox.checked = !isEnabled;
      }
    }
  }
  
  // Show skill configuration modal
  async showSkillConfigModal(flowId) {
    try {
      // Get workflow expose config from backend
      const response = await this.apiClient.getWorkflowExposeConfig(flowId);
      
      if (!response.success) {
        throw new Error(response.message || 'Failed to get workflow configuration');
      }
      
      const workflow = this.state.workflows.find(w => w.flow_id === flowId);
      const workflowName = workflow ? workflow.name : flowId;
      
      // Create and show modal
      this.showSkillExposeModal(flowId, workflowName, response.workflow_expose_config);
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to load skill config:', error);
      this.emit('notification', {
        message: `Failed to load skill configuration: ${error.message}`,
        type: 'error'
      });
      
      // Revert checkbox
      const checkbox = document.querySelector(`.skill-toggle-input[data-flow-id="${flowId}"]`);
      if (checkbox) {
        checkbox.checked = false;
      }
    }
  }
  
  // Show skill expose modal
  showSkillExposeModal(flowId, workflowName, exposeConfig) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('skill-expose-modal');
    if (!modal) {
      modal = this.createSkillExposeModal();
    }

    const inputSchemaLabel = window.i18n?.getMessage('inputSchema') || 'Input Schema';
    const workflowLabel = window.i18n?.getMessage('workflow') || 'Workflow';

    // Update modal content
    const modalTitle = modal.querySelector('.skill-expose-title');
    const modalWorkflowName = modal.querySelector('.skill-expose-workflow-name');
    const modalContent = modal.querySelector('.skill-expose-content');
    const modalWorkflowLabel = modal.querySelector('.skill-expose-workflow-label');

    if (modalTitle) modalTitle.textContent = inputSchemaLabel;
    if (modalWorkflowLabel) modalWorkflowLabel.textContent = workflowLabel;
    if (modalWorkflowName) modalWorkflowName.textContent = workflowName;

    // Render expose configuration
    if (modalContent) {
      modalContent.innerHTML = this.renderExposeConfig(exposeConfig);
    }

    // Store current flow ID for saving
    modal.dataset.flowId = flowId;
    modal.dataset.exposeConfig = JSON.stringify(exposeConfig);

    // Show modal
    modal.classList.remove('hidden');
  }
  
  // Create skill expose modal
  createSkillExposeModal() {
    const inputSchemaLabel = window.i18n?.getMessage('inputSchema') || 'Input Schema';
    const workflowLabel = window.i18n?.getMessage('workflow') || 'Workflow';
    const cancelLabel = window.i18n?.getMessage('cancel') || 'Cancel';
    const saveLabel = window.i18n?.getMessage('save') || 'Save';
    const searchPlaceholder = window.i18n?.getMessage('searchInputs') || 'Search by component name, field name, or description...';

    const modalHTML = `
      <div id="skill-expose-modal" class="modal hidden">
        <div class="modal-overlay"></div>
        <div class="modal-content skill-expose-modal-content">
          <div class="modal-header">
            <h3 class="skill-expose-title">${inputSchemaLabel}</h3>
            <button class="modal-close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M6 6L18 18M6 18L18 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="skill-expose-workflow-name-container">
              <strong class="skill-expose-workflow-label">${workflowLabel}:</strong>
              <span class="skill-expose-workflow-name"></span>
            </div>
            <div class="skill-search-container">
              <input type="text"
                     id="skill-search-input"
                     class="skill-search-input"
                     placeholder="${searchPlaceholder}">
              <svg class="skill-search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="11" cy="11" r="8"></circle>
                <path d="m21 21-4.35-4.35"></path>
              </svg>
            </div>
            <div class="skill-expose-content"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="skill-expose-cancel">${cancelLabel}</button>
            <button type="button" class="btn btn-primary" id="skill-expose-save">${saveLabel}</button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
    const modal = document.getElementById('skill-expose-modal');

    // Bind events
    const closeBtn = modal.querySelector('.modal-close');
    const cancelBtn = modal.querySelector('#skill-expose-cancel');
    const saveBtn = modal.querySelector('#skill-expose-save');
    const overlay = modal.querySelector('.modal-overlay');
    const searchInput = modal.querySelector('#skill-search-input');

    if (closeBtn) closeBtn.addEventListener('click', () => this.hideSkillExposeModal());
    if (cancelBtn) cancelBtn.addEventListener('click', () => this.hideSkillExposeModal());
    if (saveBtn) saveBtn.addEventListener('click', () => this.saveSkillExposeConfig());
    if (overlay) overlay.addEventListener('click', () => this.hideSkillExposeModal());
    if (searchInput) searchInput.addEventListener('input', (e) => this.handleSkillSearchInput(e.target.value));

    return modal;
  }
  
  // Render expose configuration with table layout
  renderExposeConfig(exposeConfig) {
    if (!exposeConfig || Object.keys(exposeConfig).length === 0) {
      const noInputsLabel = window.i18n?.getMessage('noExposableInputs') || 'No exposable inputs found in this workflow.';
      return `<div class="empty-state"><p>${noInputsLabel}</p></div>`;
    }

    const exposeInputLabel = window.i18n?.getMessage('exposeInput') || 'Expose Input';
    const fieldNameLabel = window.i18n?.getMessage('fieldName') || 'Field Name';
    const descriptionLabel = window.i18n?.getMessage('description') || 'Description';
    const currentValueLabel = window.i18n?.getMessage('currentValue') || 'Current Value';
    const requiredLabel = window.i18n?.getMessage('required') || 'required';

    let html = '';

    for (const [componentId, componentData] of Object.entries(exposeConfig)) {
      const componentName = componentData.component_name || componentId;
      const componentDescription = componentData.component_description || '';
      const inputs = componentData.inputs || {};

      if (Object.keys(inputs).length === 0) continue;

      html += `
        <div class="skill-component-section" data-component-id="${componentId}">
          <div class="component-header" data-component-id="${componentId}">
            <div class="component-info">
              <span class="component-id">${this.escapeHtml(componentId)}</span>
              ${componentDescription ? `<span class="component-description">${this.escapeHtml(componentDescription)}</span>` : ''}
            </div>
            <span class="component-collapse-icon">▼</span>
          </div>
          <div class="component-inputs">
            <table class="skill-inputs-table">
              <thead>
                <tr>
                  <th class="col-expose">${exposeInputLabel}</th>
                  <th class="col-field-name">${fieldNameLabel}</th>
                  <th class="col-description">${descriptionLabel}</th>
                  <th class="col-current-value">${currentValueLabel}</th>
                </tr>
              </thead>
              <tbody>
      `;

      for (const [inputName, inputData] of Object.entries(inputs)) {
        let displayName = inputData.display_name || inputName;
        let info = inputData.info || '';

        const type = inputData.type || 'str';
        const isExpose = inputData.is_expose || false;
        const required = inputData.required;

        // Format current value
        let currentValue = '';
        if (inputData.value !== undefined && inputData.value !== null && inputData.value !== '') {
          if (typeof inputData.value === 'boolean') {
            currentValue = `<span class="value-toggle">${inputData.value ? '✓' : '✗'}</span>`;
          } else {
            currentValue = this.escapeHtml(String(inputData.value));
          }
        } else {
          currentValue = '<span class="value-empty">-</span>';
        }

        html += `
          <tr class="input-row"
              data-search-text="${this.escapeHtml(componentId.toLowerCase())} ${this.escapeHtml(componentDescription.toLowerCase())} ${this.escapeHtml(displayName.toLowerCase())} ${this.escapeHtml(info.toLowerCase())}">
            <td class="col-expose">
              <label class="toggle-switch">
                <input type="checkbox"
                       class="skill-expose-checkbox"
                       data-component-id="${componentId}"
                       data-input-name="${inputName}"
                       ${isExpose ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
            </td>
            <td class="col-field-name">
              <div class="field-name-wrapper">
                <span class="field-name">${this.escapeHtml(displayName)}</span>
                <span class="field-type">${this.escapeHtml(type)}</span>
                ${required ? `<span class="required-badge">(${requiredLabel})</span>` : ''}
              </div>
            </td>
            <td class="col-description">${this.escapeHtml(info)}</td>
            <td class="col-current-value">${currentValue}</td>
          </tr>
        `;
      }

      html += `
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    return html;
  }
  
  // Hide skill expose modal
  hideSkillExposeModal() {
    const modal = document.getElementById('skill-expose-modal');
    if (!modal) return;

    // Revert checkbox if canceling
    const flowId = modal.dataset.flowId;
    const checkbox = document.querySelector(`.skill-toggle-input[data-flow-id="${flowId}"]`);
    if (checkbox) {
      const workflow = this.state.workflows.find(w => w.flow_id === flowId);
      checkbox.checked = workflow ? workflow.add_to_skill : false;
    }

    modal.classList.add('hidden');
  }

  // Handle skill search input
  handleSkillSearchInput(searchQuery) {
    const modal = document.getElementById('skill-expose-modal');
    if (!modal) return;

    const query = searchQuery.toLowerCase().trim();
    const sections = modal.querySelectorAll('.skill-component-section');

    sections.forEach(section => {
      const rows = section.querySelectorAll('.input-row');
      let hasVisibleRows = false;

      rows.forEach(row => {
        const searchText = row.dataset.searchText || '';
        if (!query || searchText.includes(query)) {
          row.style.display = '';
          hasVisibleRows = true;
        } else {
          row.style.display = 'none';
        }
      });

      // Hide the entire component section if no rows match
      if (hasVisibleRows) {
        section.style.display = '';
      } else {
        section.style.display = 'none';
      }
    });
  }
  
  // Save skill expose configuration
  async saveSkillExposeConfig() {
    const modal = document.getElementById('skill-expose-modal');
    if (!modal) return;
    
    const flowId = modal.dataset.flowId;
    const exposeConfig = JSON.parse(modal.dataset.exposeConfig || '{}');
    
    // Update expose config based on checkbox states
    const checkboxes = modal.querySelectorAll('.skill-expose-checkbox');
    checkboxes.forEach(checkbox => {
      const componentId = checkbox.dataset.componentId;
      const inputName = checkbox.dataset.inputName;
      
      if (exposeConfig[componentId] && exposeConfig[componentId].inputs && exposeConfig[componentId].inputs[inputName]) {
        exposeConfig[componentId].inputs[inputName].is_expose = checkbox.checked;
      }
    });
    
    try {
      // Save to backend
      await this.apiClient.updateWorkflowExposeConfig(flowId, true, exposeConfig);
      
      // Update workflow state
      const workflow = this.state.workflows.find(w => w.flow_id === flowId);
      if (workflow) {
        workflow.add_to_skill = true;
      }
      
      this.emit('notification', {
        message: 'Workflow skill configuration saved',
        type: 'success'
      });
      
      modal.classList.add('hidden');
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to save skill config:', error);
      this.emit('notification', {
        message: `Failed to save configuration: ${error.message}`,
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