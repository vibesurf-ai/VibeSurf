// Settings Manager - Handles settings UI, profiles, and environment variables
// Manages LLM profiles, MCP profiles, and application settings

class VibeSurfSettingsManager {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.state = {
      llmProfiles: [],
      mcpProfiles: [],
      voiceProfiles: [],
      settings: {},
      currentProfileForm: null,
      // Integrations state
      composioApiKey: null,
      composioKeyValid: false,
      toolkits: [],
      filteredToolkits: [],
      currentToolkit: null,
      searchQuery: '',
      filterStatus: 'all',
      // Workflows state
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
      workflowJobMapping: new Map() // Map<workflowId, {jobId: string, completedAt: timestamp, eventCount: number}>
    };
    this.elements = {};
    this.eventListeners = new Map();
    
    // Schedule state for new interface
    this.scheduleState = {
      selectedTemplate: null,
      scheduleType: 'simple',
      cronExpression: '',
      isValid: false,
      previewTimes: []
    };
    
    // Initialize user settings storage
    this.userSettingsStorage = new VibeSurfUserSettingsStorage();
    
    this.bindElements();
    this.bindEvents();
    this.initializeUserSettings();
  }

  bindElements() {
    this.elements = {
      // Settings Modal
      settingsModal: document.getElementById('settings-modal'),
      settingsTabs: document.querySelectorAll('.settings-tab'),
      settingsTabContents: document.querySelectorAll('.settings-tab-content'),
      
      // Workflow Tab
      workflowTab: document.getElementById('workflow-tab'),
      createWorkflowBtn: document.getElementById('create-workflow-btn'),
      workflowSearch: document.getElementById('workflow-search'),
      workflowFilter: document.getElementById('workflow-filter'),
      workflowsList: document.getElementById('workflows-list'),
      workflowsLoading: document.getElementById('workflows-loading'),
      
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
      deleteConfirm: document.getElementById('delete-confirm'),
      
      // General Settings
      themeSelect: document.getElementById('theme-select'),
      defaultAsrSelect: document.getElementById('default-asr-select'),
      defaultTtsSelect: document.getElementById('default-tts-select'),
      
      // LLM Profiles
      llmProfilesContainer: document.getElementById('llm-profiles-container'),
      addLlmProfileBtn: document.getElementById('add-llm-profile-btn'),
      
      // MCP Profiles
      mcpProfilesContainer: document.getElementById('mcp-profiles-container'),
      addMcpProfileBtn: document.getElementById('add-mcp-profile-btn'),
      
      // Voice Profiles
      voiceProfilesContainer: document.getElementById('voice-profiles-container'),
      addVoiceProfileBtn: document.getElementById('add-voice-profile-btn'),
      
      // Integrations
      integrationsContainer: document.getElementById('integrations-container'),
      setupApiKeyBtn: document.getElementById('setup-api-key-btn'),
      composioStatus: document.getElementById('composio-status'),
      apiKeySetup: document.getElementById('api-key-setup'),
      toolkitsSection: document.getElementById('toolkits-section'),
      toolkitSearch: document.getElementById('toolkit-search'),
      toolkitFilter: document.getElementById('toolkit-filter'),
      toolkitsList: document.getElementById('toolkits-list'),
      toolkitsLoading: document.getElementById('toolkits-loading'),
      
      // Composio API Key Modal
      composioApiKeyModal: document.getElementById('composio-api-key-modal'),
      composioApiKeyInput: document.getElementById('composio-api-key-input'),
      openComposioLink: document.getElementById('open-composio-link'),
      apiKeyCancel: document.getElementById('api-key-cancel'),
      apiKeyConfirm: document.getElementById('api-key-confirm'),
      apiKeyValidation: document.getElementById('api-key-validation'),
      
      // Tools Management Modal
      toolsManagementModal: document.getElementById('tools-management-modal'),
      toolsModalTitle: document.getElementById('tools-modal-title'),
      toolkitLogo: document.getElementById('toolkit-logo-img'),
      toolkitName: document.getElementById('toolkit-name'),
      toolkitDescription: document.getElementById('toolkit-description'),
      toolsList: document.getElementById('tools-list'),
      toolsLoading: document.getElementById('tools-loading'),
      selectAllTools: document.getElementById('select-all-tools'),
      deselectAllTools: document.getElementById('deselect-all-tools'),
      toolsCancel: document.getElementById('tools-cancel'),
      toolsSave: document.getElementById('tools-save'),
      
      // OAuth Confirmation Modal
      oauthConfirmationModal: document.getElementById('oauth-confirmation-modal'),
      oauthNotCompleted: document.getElementById('oauth-not-completed'),
      oauthCompleted: document.getElementById('oauth-completed'),
      
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
      
      // Backend URL
      backendUrl: document.getElementById('backend-url')
    };
  }

  bindEvents() {
    // Settings modal close button
    const settingsModalClose = this.elements.settingsModal?.querySelector('.modal-close');
    if (settingsModalClose) {
      settingsModalClose.addEventListener('click', this.hideModal.bind(this));
    }
    
    // Settings tabs
    this.elements.settingsTabs?.forEach(tab => {
      tab.addEventListener('click', this.handleTabSwitch.bind(this));
    });
    
    // Profile management
    this.elements.addLlmProfileBtn?.addEventListener('click', () => this.handleAddProfile('llm'));
    this.elements.addMcpProfileBtn?.addEventListener('click', () => this.handleAddProfile('mcp'));
    this.elements.addVoiceProfileBtn?.addEventListener('click', () => this.handleAddProfile('voice'));
    
    // Profile form modal
    this.elements.profileFormCancel?.addEventListener('click', this.closeProfileForm.bind(this));
    this.elements.profileFormClose?.addEventListener('click', this.closeProfileForm.bind(this));
    
    // Profile form submission
    if (this.elements.profileForm) {
      this.elements.profileForm.addEventListener('submit', this.handleProfileFormSubmit.bind(this));
    }
    
    if (this.elements.profileFormSubmit) {
      this.elements.profileFormSubmit.addEventListener('click', this.handleProfileFormSubmitClick.bind(this));
    }
    
    // General settings
    this.elements.themeSelect?.addEventListener('change', this.handleThemeChange.bind(this));
    this.elements.defaultAsrSelect?.addEventListener('change', this.handleDefaultAsrChange.bind(this));
    this.elements.defaultTtsSelect?.addEventListener('change', this.handleDefaultTtsChange.bind(this));
    
    // Environment variables
    this.elements.saveEnvVarsBtn?.addEventListener('click', this.handleSaveEnvironmentVariables.bind(this));
    
    // Backend URL
    this.elements.backendUrl?.addEventListener('change', this.handleBackendUrlChange.bind(this));
    
    // Integrations
    this.elements.setupApiKeyBtn?.addEventListener('click', this.handleSetupApiKey.bind(this));
    this.elements.openComposioLink?.addEventListener('click', this.handleOpenComposioLink.bind(this));
    this.elements.apiKeyCancel?.addEventListener('click', this.hideApiKeyModal.bind(this));
    this.elements.apiKeyConfirm?.addEventListener('click', this.handleApiKeyConfirm.bind(this));
    this.elements.toolkitSearch?.addEventListener('input', this.handleToolkitSearch.bind(this));
    this.elements.toolkitFilter?.addEventListener('change', this.handleToolkitFilter.bind(this));
    
    // Tools Management Modal
    this.elements.selectAllTools?.addEventListener('click', this.handleSelectAllTools.bind(this));
    this.elements.deselectAllTools?.addEventListener('click', this.handleDeselectAllTools.bind(this));
    this.elements.toolsCancel?.addEventListener('click', this.hideToolsModal.bind(this));
    this.elements.toolsSave?.addEventListener('click', this.handleToolsSave.bind(this));
    
    // OAuth Confirmation Modal
    this.elements.oauthNotCompleted?.addEventListener('click', this.hideOAuthModal.bind(this));
    this.elements.oauthCompleted?.addEventListener('click', this.handleOAuthCompleted.bind(this));
    
    // API key toggle visibility
    const apiKeyToggle = this.elements.composioApiKeyModal?.querySelector('.api-key-toggle');
    if (apiKeyToggle) {
      apiKeyToggle.addEventListener('click', this.handleApiKeyToggle.bind(this));
    }
    
    // Modal close buttons for integrations modals
    const composioModalClose = this.elements.composioApiKeyModal?.querySelector('.modal-close');
    if (composioModalClose) {
      composioModalClose.addEventListener('click', this.hideApiKeyModal.bind(this));
    }
    
    const toolsModalClose = this.elements.toolsManagementModal?.querySelector('.modal-close');
    if (toolsModalClose) {
      toolsModalClose.addEventListener('click', this.hideToolsModal.bind(this));
    }
    
    const oauthModalClose = this.elements.oauthConfirmationModal?.querySelector('.modal-close');
    if (oauthModalClose) {
      oauthModalClose.addEventListener('click', this.hideOAuthModal.bind(this));
    }
    
    // Workflow tab events
    this.elements.createWorkflowBtn?.addEventListener('click', this.handleCreateWorkflow.bind(this));
    this.elements.workflowSearch?.addEventListener('input', this.handleWorkflowSearch.bind(this));
    this.elements.workflowFilter?.addEventListener('change', this.handleWorkflowFilter.bind(this));
    
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

    // --- New Schedule Modal Events ---
    // These are bound once to prevent duplicate listeners.
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
        // Re-validate to enable/disable save button
        this.updateScheduleSaveButton(this.scheduleState.isValid);
      });
    }
    // --- End New Schedule Modal Events ---
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', this.handleKeydown.bind(this));
  }

  // Initialize user settings storage
  async initializeUserSettings() {
    try {
      await this.userSettingsStorage.initialize();
      
      // Listen to storage events
      this.userSettingsStorage.on('settingChanged', this.handleStorageSettingChanged.bind(this));
      this.userSettingsStorage.on('settingsChanged', this.handleStorageSettingsChanged.bind(this));
      
    } catch (error) {
      console.error('[SettingsManager] Failed to initialize user settings storage:', error);
    }
  }

  // Handle individual setting changes from storage
  handleStorageSettingChanged(data) {
    
    // Apply setting changes to UI if needed
    switch (data.key) {
      case 'theme':
        this.applyTheme(data.value);
        if (this.elements.themeSelect) {
          this.elements.themeSelect.value = data.value;
        }
        break;
      case 'defaultAsr':
        if (this.elements.defaultAsrSelect) {
          this.elements.defaultAsrSelect.value = data.value;
        }
        break;
      case 'defaultTts':
        if (this.elements.defaultTtsSelect) {
          this.elements.defaultTtsSelect.value = data.value;
        }
        break;
    }
  }

  // Handle bulk settings changes from storage
  handleStorageSettingsChanged(allSettings) {
    console.log('[SettingsManager] Storage settings changed (bulk):', allSettings);
    
    // Apply bulk setting changes to UI if needed
    if (allSettings.theme) {
      this.applyTheme(allSettings.theme);
      if (this.elements.themeSelect) {
        this.elements.themeSelect.value = allSettings.theme;
      }
    }
    
    if (allSettings.defaultAsr && this.elements.defaultAsrSelect) {
      this.elements.defaultAsrSelect.value = allSettings.defaultAsr;
    }
    
    if (allSettings.defaultTts && this.elements.defaultTtsSelect) {
      this.elements.defaultTtsSelect.value = allSettings.defaultTts;
    }
  }

  handleKeydown(event) {
    // Close settings modal on Escape key
    if (event.key === 'Escape') {
      if (this.elements.settingsModal && !this.elements.settingsModal.classList.contains('hidden')) {
        this.hideModal();
      }
      // Close profile form modal on Escape key
      if (this.elements.profileFormModal && !this.elements.profileFormModal.classList.contains('hidden')) {
        this.closeProfileForm();
      }
    }
  }

  // Event system for communicating with main UI manager
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  emit(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[SettingsManager] Event callback error for ${event}:`, error);
        }
      });
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
    
    // If switching to general tab, ensure environment variables are loaded
    if (targetTabId === 'general') {
      this.loadEnvironmentVariables();
    }
    
    // If switching to integrations tab, load integrations data
    if (targetTabId === 'integrations') {
      this.loadIntegrationsData();
    }
    
    // If switching to workflow tab, load workflow content
    if (targetTabId === 'workflow') {
      this.loadWorkflowContent();
    }
  }

  // Data Loading
  async loadSettingsData() {
    try {
      // Load LLM profiles
      await this.loadLLMProfiles();
      
      // Load MCP profiles
      await this.loadMCPProfiles();
      
      // Load Voice profiles
      await this.loadVoiceProfiles();
      
      // Load environment variables
      await this.loadEnvironmentVariables();
      
      // Load general settings
      await this.loadGeneralSettings();
      
      // Load voice profiles for general settings dropdowns
      await this.loadVoiceProfilesForGeneral();
      
      // Emit event to update LLM profile select dropdown
      // This should happen AFTER all data is loaded but BEFORE user selections are restored
      this.emit('profilesUpdated', {
        llmProfiles: this.state.llmProfiles,
        mcpProfiles: this.state.mcpProfiles,
        voiceProfiles: this.state.voiceProfiles
      });
      
    } catch (error) {
      console.error('[SettingsManager] Failed to load settings data:', error);
      this.emit('error', { message: 'Failed to load settings data', error });
    }
  }

  async loadLLMProfiles() {
    try {
      const response = await this.apiClient.getLLMProfiles(false); // Load all profiles, not just active
      console.log('[SettingsManager] LLM profiles loaded:', response);
      
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
    } catch (error) {
      console.error('[SettingsManager] Failed to load LLM profiles:', error);
      this.state.llmProfiles = [];
      this.renderLLMProfiles([]);
    }
  }

  async loadMCPProfiles() {
    try {
      const response = await this.apiClient.getMCPProfiles(false); // Load all profiles, not just active
      console.log('[SettingsManager] MCP profiles loaded:', response);
      
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
      console.error('[SettingsManager] Failed to load MCP profiles:', error);
      this.state.mcpProfiles = [];
      this.renderMCPProfiles([]);
    }
  }

  async loadVoiceProfiles() {
    try {
      const response = await this.apiClient.getVoiceProfiles(false); // Load all profiles, not just active
      console.log('[SettingsManager] Voice profiles loaded:', response);
      
      // Handle different response structures
      let profiles = [];
      if (Array.isArray(response)) {
        profiles = response;
      } else if (response.profiles && Array.isArray(response.profiles)) {
        profiles = response.profiles;
      } else if (response.data && Array.isArray(response.data)) {
        profiles = response.data;
      }
      
      this.state.voiceProfiles = profiles;
      this.renderVoiceProfiles(profiles);
    } catch (error) {
      console.error('[SettingsManager] Failed to load Voice profiles:', error);
      this.state.voiceProfiles = [];
      this.renderVoiceProfiles([]);
    }
  }

  async loadEnvironmentVariables() {
    try {
      const response = await this.apiClient.getEnvironmentVariables();
      console.log('[SettingsManager] Environment variables loaded:', response);
      const envVars = response.environments || response || {};
      this.renderEnvironmentVariables(envVars);
    } catch (error) {
      console.error('[SettingsManager] Failed to load environment variables:', error);
      this.renderEnvironmentVariables({});
    }
  }

  async loadGeneralSettings() {
    try {
      // Load and apply theme setting from user settings storage
      const savedTheme = await this.userSettingsStorage.getTheme();
      if (this.elements.themeSelect) {
        this.elements.themeSelect.value = savedTheme;
      }
      this.applyTheme(savedTheme);
      
      // Voice profile defaults will be handled by autoSelectLatestVoiceProfiles
      // after voice profiles are loaded in loadVoiceProfilesForGeneral
      
      console.log('[SettingsManager] General settings loaded successfully');
    } catch (error) {
      console.error('[SettingsManager] Failed to load general settings:', error);
    }
  }

  async loadVoiceProfilesForGeneral() {
    try {
      // Load voice profiles for ASR and TTS dropdowns in general settings
      const response = await this.apiClient.getVoiceProfiles(false);
      
      // Handle different response structures
      let profiles = [];
      if (Array.isArray(response)) {
        profiles = response;
      } else if (response.profiles && Array.isArray(response.profiles)) {
        profiles = response.profiles;
      } else if (response.data && Array.isArray(response.data)) {
        profiles = response.data;
      }
      
      // Filter profiles by type
      const asrProfiles = profiles.filter(p => p.voice_model_type === 'asr' && p.is_active);
      const ttsProfiles = profiles.filter(p => p.voice_model_type === 'tts' && p.is_active);
      
      // Populate ASR dropdown
      if (this.elements.defaultAsrSelect) {
        this.elements.defaultAsrSelect.innerHTML = '<option value="">No ASR profile selected</option>';
        asrProfiles.forEach(profile => {
          const option = document.createElement('option');
          option.value = profile.voice_profile_name;
          option.textContent = profile.voice_profile_name;
          this.elements.defaultAsrSelect.appendChild(option);
        });
      }
      
      // Populate TTS dropdown
      if (this.elements.defaultTtsSelect) {
        this.elements.defaultTtsSelect.innerHTML = '<option value="">No TTS profile selected</option>';
        ttsProfiles.forEach(profile => {
          const option = document.createElement('option');
          option.value = profile.voice_profile_name;
          option.textContent = profile.voice_profile_name;
          this.elements.defaultTtsSelect.appendChild(option);
        });
      }
      
      // Auto-select latest updated profiles if no defaults are set
      await this.autoSelectLatestVoiceProfiles(asrProfiles, ttsProfiles);
      
    } catch (error) {
      console.error('[SettingsManager] Failed to load voice profiles for general settings:', error);
      // Populate with empty options on error
      if (this.elements.defaultAsrSelect) {
        this.elements.defaultAsrSelect.innerHTML = '<option value="">Failed to load ASR profiles</option>';
      }
      if (this.elements.defaultTtsSelect) {
        this.elements.defaultTtsSelect.innerHTML = '<option value="">Failed to load TTS profiles</option>';
      }
    }
  }

  async autoSelectLatestVoiceProfiles(asrProfiles, ttsProfiles) {
    try {
      // Get current saved defaults
      const savedAsrProfile = await this.userSettingsStorage.getDefaultAsr();
      const savedTtsProfile = await this.userSettingsStorage.getDefaultTts();
      
      // Check ASR profile
      if (!savedAsrProfile || !asrProfiles.find(p => p.voice_profile_name === savedAsrProfile)) {
        // No ASR profile selected or saved profile doesn't exist, select latest updated
        if (asrProfiles.length > 0) {
          // Sort by updated_at desc to get the latest updated profile
          const latestAsrProfile = asrProfiles.sort((a, b) => {
            const dateA = new Date(a.updated_at || a.created_at);
            const dateB = new Date(b.updated_at || b.created_at);
            return dateB - dateA; // DESC order
          })[0];
          
          console.log('[SettingsManager] Auto-selecting latest ASR profile:', latestAsrProfile.voice_profile_name);
          
          // Set as default in storage
          await this.userSettingsStorage.setDefaultAsr(latestAsrProfile.voice_profile_name);
          
          // Update UI
          if (this.elements.defaultAsrSelect) {
            this.elements.defaultAsrSelect.value = latestAsrProfile.voice_profile_name;
          }
          
          this.emit('notification', {
            message: `Auto-selected latest ASR profile: ${latestAsrProfile.voice_profile_name}`,
            type: 'info'
          });
        }
      } else {
        // Saved ASR profile exists and is valid - restore it to UI
        console.log('[SettingsManager] Restoring saved ASR profile to UI:', savedAsrProfile);
        if (this.elements.defaultAsrSelect) {
          this.elements.defaultAsrSelect.value = savedAsrProfile;
        }
      }
      
      // Check TTS profile
      if (!savedTtsProfile || !ttsProfiles.find(p => p.voice_profile_name === savedTtsProfile)) {
        // No TTS profile selected or saved profile doesn't exist, select latest updated
        if (ttsProfiles.length > 0) {
          // Sort by updated_at desc to get the latest updated profile
          const latestTtsProfile = ttsProfiles.sort((a, b) => {
            const dateA = new Date(a.updated_at || a.created_at);
            const dateB = new Date(b.updated_at || b.created_at);
            return dateB - dateA; // DESC order
          })[0];
          
          console.log('[SettingsManager] Auto-selecting latest TTS profile:', latestTtsProfile.voice_profile_name);
          
          // Set as default in storage
          await this.userSettingsStorage.setDefaultTts(latestTtsProfile.voice_profile_name);
          
          // Update UI
          if (this.elements.defaultTtsSelect) {
            this.elements.defaultTtsSelect.value = latestTtsProfile.voice_profile_name;
          }
          
          this.emit('notification', {
            message: `Auto-selected latest TTS profile: ${latestTtsProfile.voice_profile_name}`,
            type: 'info'
          });
        }
      } else {
        // Saved TTS profile exists and is valid - restore it to UI
        console.log('[SettingsManager] Restoring saved TTS profile to UI:', savedTtsProfile);
        if (this.elements.defaultTtsSelect) {
          this.elements.defaultTtsSelect.value = savedTtsProfile;
        }
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to auto-select latest voice profiles:', error);
    }
  }

  async handleDefaultAsrChange(event) {
    const selectedProfile = event.target.value;
    
    try {
      // Store ASR profile preference in user settings storage
      await this.userSettingsStorage.setDefaultAsr(selectedProfile);
      
      if (selectedProfile) {
        this.emit('notification', {
          message: `Default ASR profile set to ${selectedProfile}`,
          type: 'success'
        });
      } else {
        this.emit('notification', {
          message: 'Default ASR profile cleared',
          type: 'info'
        });
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to change default ASR profile:', error);
      this.emit('notification', {
        message: 'Failed to change default ASR profile',
        type: 'error'
      });
    }
  }

  async handleDefaultTtsChange(event) {
    const selectedProfile = event.target.value;
    
    try {
      // Store TTS profile preference in user settings storage
      await this.userSettingsStorage.setDefaultTts(selectedProfile);
      
      if (selectedProfile) {
        this.emit('notification', {
          message: `Default TTS profile set to ${selectedProfile}`,
          type: 'success'
        });
      } else {
        this.emit('notification', {
          message: 'Default TTS profile cleared',
          type: 'info'
        });
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to change default TTS profile:', error);
      this.emit('notification', {
        message: 'Failed to change default TTS profile',
        type: 'error'
      });
    }
  }

  // Profile Management
  async handleAddProfile(type) {
    try {
      this.showProfileForm(type);
    } catch (error) {
      console.error(`[SettingsManager] Failed to show ${type} profile form:`, error);
      this.emit('error', { message: `Failed to show ${type} profile form` });
    }
  }

  async showProfileForm(type, profile = null) {
    const isEdit = profile !== null;
    const title = isEdit ? `Edit ${type.toUpperCase()}` : `Add ${type.toUpperCase()}`;
    
    if (this.elements.profileFormTitle) {
      this.elements.profileFormTitle.textContent = title;
    }
    
    // Generate form content based on type
    let formHTML = '';
    if (type === 'llm') {
      formHTML = await this.generateLLMProfileForm(profile);
    } else if (type === 'mcp') {
      formHTML = this.generateMCPProfileForm(profile);
    } else if (type === 'voice') {
      formHTML = await this.generateVoiceProfileForm(profile);
    }
    
    if (this.elements.profileForm) {
      this.elements.profileForm.innerHTML = formHTML;
      this.elements.profileForm.dataset.type = type;
      this.elements.profileForm.dataset.mode = isEdit ? 'edit' : 'create';
      if (isEdit && profile) {
        this.elements.profileForm.dataset.profileId = profile.profile_name || profile.mcp_id || profile.voice_profile_name;
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
      console.error('[SettingsManager] Failed to fetch LLM providers:', error);
    }
    
    const providersOptions = providers.map(p =>
      `<option value="${p.name}" ${profile?.provider === p.name ? 'selected' : ''}>${p.display_name}</option>`
    ).join('');
    
    const selectedProvider = profile?.provider || (providers.length > 0 ? providers[0].name : '');
    const selectedProviderData = providers.find(p => p.name === selectedProvider);
    const models = selectedProviderData?.models || [];
    
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

  async generateVoiceProfileForm(profile = null) {
    // Fetch available voice models
    let models = [];
    try {
      const response = await this.apiClient.getVoiceModels();
      models = response.models || response || [];
    } catch (error) {
      console.error('[SettingsManager] Failed to fetch voice models:', error);
    }
    
    // Group models by type
    const asrModels = models.filter(m => m.model_type === 'asr');
    const ttsModels = models.filter(m => m.model_type === 'tts');
    
    const selectedModelType = profile?.voice_model_type || 'asr';
    const availableModels = selectedModelType === 'asr' ? asrModels : ttsModels;
    
    const modelsOptions = availableModels.map(m =>
      `<option value="${m.model_name}" ${profile?.voice_model_name === m.model_name ? 'selected' : ''}>${m.model_name}</option>`
    ).join('');
    
    // Convert existing meta params to JSON for editing
    let defaultMetaJson = '{}';
    if (profile?.voice_meta_params) {
      try {
        defaultMetaJson = JSON.stringify(profile.voice_meta_params, null, 2);
      } catch (error) {
        console.warn('[SettingsManager] Failed to stringify existing voice_meta_params:', error);
      }
    }
    
    return `
      <div class="form-group">
        <label class="form-label required">Profile Name</label>
        <input type="text" name="voice_profile_name" class="form-input" value="${profile?.voice_profile_name || ''}"
               placeholder="Enter a unique name for this profile" required ${profile ? 'readonly' : ''}>
        <div class="form-help">A unique identifier for this voice configuration</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">Model Type</label>
        <select name="voice_model_type" class="form-select" required>
          <option value="asr" ${selectedModelType === 'asr' ? 'selected' : ''}>ASR (Speech Recognition)</option>
          <option value="tts" ${selectedModelType === 'tts' ? 'selected' : ''}>TTS (Text to Speech)</option>
        </select>
        <div class="form-help">Choose the type of voice model</div>
      </div>
      
      <div class="form-group">
        <label class="form-label required">Voice Model</label>
        <select name="voice_model_name" class="form-select voice-model-select" required>
          <option value="">Select a model</option>
          ${modelsOptions}
        </select>
        <div class="form-help">Choose your voice model</div>
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
        <div class="form-help">Your voice provider's API key for authentication</div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Model Parameters (JSON)</label>
        <textarea name="voice_meta_params_json" class="form-textarea json-input" rows="4"
                  placeholder="Enter JSON configuration for model parameters (optional)">${defaultMetaJson}</textarea>
        <div class="json-validation-feedback"></div>
        <div class="form-help">
          Optional JSON configuration for model-specific parameters. Example:
          <br><code>{"language": "zh", "sample_rate": 16000}</code>
        </div>
      </div>
      
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-textarea" placeholder="Optional description for this profile">${profile?.description || ''}</textarea>
        <div class="form-help">Optional description to help identify this profile</div>
      </div>
      
      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_active" ${profile?.is_active !== false ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">Active</span>
        </label>
        <div class="form-help">Whether this voice profile is active and available for use</div>
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
        console.warn('[SettingsManager] Failed to stringify existing mcp_server_params:', error);
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
    console.log('[SettingsManager] Setting up profile form events');
    
    // Provider change handler for LLM profiles
    const providerSelect = this.elements.profileForm?.querySelector('select[name="provider"]');
    if (providerSelect) {
      providerSelect.addEventListener('change', this.handleProviderChange.bind(this));
    }
    
    // Voice model type change handler for Voice profiles
    const voiceModelTypeSelect = this.elements.profileForm?.querySelector('select[name="voice_model_type"]');
    if (voiceModelTypeSelect) {
      voiceModelTypeSelect.addEventListener('change', this.handleVoiceModelTypeChange.bind(this));
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
    }
    
    // JSON validation handler for MCP profiles
    const jsonInput = this.elements.profileForm?.querySelector('textarea[name="mcp_server_params_json"]');
    if (jsonInput) {
      jsonInput.addEventListener('input', this.handleJsonInputValidation.bind(this));
      jsonInput.addEventListener('blur', this.handleJsonInputValidation.bind(this));
      
      // Trigger initial validation
      this.handleJsonInputValidation({ target: jsonInput });
    }
    
    // JSON validation handler for Voice meta params
    const voiceJsonInput = this.elements.profileForm?.querySelector('textarea[name="voice_meta_params_json"]');
    if (voiceJsonInput) {
      voiceJsonInput.addEventListener('input', this.handleVoiceJsonInputValidation.bind(this));
      voiceJsonInput.addEventListener('blur', this.handleVoiceJsonInputValidation.bind(this));
      
      // Trigger initial validation
      this.handleVoiceJsonInputValidation({ target: voiceJsonInput });
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
    }
  }

  handleVoiceJsonInputValidation(event) {
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
        throw new Error('Voice meta parameters must be a JSON object');
      }
      
      // Success - no specific validation required for voice meta params (flexible structure)
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
    }
  }

  handleProfileFormSubmitClick(event) {
    console.log('[SettingsManager] Profile form submit button clicked');
    event.preventDefault();
    
    // Find the form and trigger submit
    const form = this.elements.profileForm;
    if (form) {
      const submitEvent = new Event('submit', { cancelable: true, bubbles: true });
      form.dispatchEvent(submitEvent);
    }
  }

  async handleVoiceModelTypeChange(event) {
    const selectedType = event.target.value;
    const modelSelect = this.elements.profileForm?.querySelector('select[name="voice_model_name"]');
    
    if (!selectedType || !modelSelect) {
      return;
    }
    
    // Clear current options
    modelSelect.innerHTML = '<option value="">Loading...</option>';
    
    try {
      const response = await this.apiClient.getVoiceModels(selectedType);
      const models = response.models || response || [];
      
      // Models are already filtered by the API, no need to filter again
      
      // Update select options
      modelSelect.innerHTML = '<option value="">Select a model</option>' +
        models.map(model =>
          `<option value="${model.model_name}">${model.model_name}</option>`
        ).join('');
        
    } catch (error) {
      console.error('[SettingsManager] Failed to fetch voice models for type:', error);
      modelSelect.innerHTML = '<option value="">Failed to load models</option>';
      
      // Show user-friendly error notification
      this.emit('notification', {
        message: `Failed to load models for ${selectedType}. Please try again.`,
        type: 'warning'
      });
    }
  }

  async handleProviderChange(event) {
    const selectedProvider = event.target.value;
    const modelInput = this.elements.profileForm?.querySelector('input[name="model"]');
    const modelDatalist = this.elements.profileForm?.querySelector('#model-options');
    
    if (!selectedProvider || !modelInput || !modelDatalist) {
      return;
    }
    
    // Always clear the model input when provider changes
    modelInput.value = '';
    modelInput.placeholder = `Loading ${selectedProvider} models...`;
    modelDatalist.innerHTML = '<option value="">Loading...</option>';
    
    try {
      const response = await this.apiClient.getLLMProviderModels(selectedProvider);
      const models = response.models || response || [];
      
      // Update datalist options
      modelDatalist.innerHTML = models.map(model =>
        `<option value="${model}">${model}</option>`
      ).join('');
      
      // Update placeholder to reflect the new provider
      modelInput.placeholder = models.length > 0
        ? `Select a ${selectedProvider} model or type custom model name`
        : `Enter ${selectedProvider} model name`;
        
    } catch (error) {
      console.error('[SettingsManager] Failed to fetch models for provider:', error);
      modelDatalist.innerHTML = '<option value="">Failed to load models</option>';
      modelInput.placeholder = `Enter ${selectedProvider} model name manually`;
      
      // Show user-friendly error notification
      this.emit('notification', {
        message: `Failed to load models for ${selectedProvider}. You can enter the model name manually.`,
        type: 'warning'
      });
    }
  }

  closeProfileForm() {
    if (this.elements.profileFormModal) {
      this.elements.profileFormModal.classList.add('hidden');
    }
  }

  async handleProfileFormSubmit(event) {
    event.preventDefault();
    console.log('[SettingsManager] Profile form submit triggered');
    
    const form = event.target;
    
    // Prevent multiple submissions
    if (form.dataset.submitting === 'true') {
      return;
    }
    
    const formData = new FormData(form);
    const type = form.dataset.type;
    const mode = form.dataset.mode;
    const profileId = form.dataset.profileId;
    
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
      }
    });
    
    for (const [key, value] of formData.entries()) {
      if (value.trim() !== '') {
        if (key === 'is_default' || key === 'is_active') {
          // Skip - already handled above
          continue;
        } else if (key === 'temperature') {
          const num = parseFloat(value);
          if (!isNaN(num) && num >= 0) {
            data[key] = num;
          }
        } else if (key === 'max_tokens') {
          const num = parseInt(value);
          if (!isNaN(num) && num > 0) {
            data[key] = num;
          }
        } else {
          data[key] = value;
        }
      }
    }
    
    // Handle Voice profile meta params structure - parse JSON input
    if (type === 'voice') {
      const jsonInput = data.voice_meta_params_json;
      
      if (jsonInput && jsonInput.trim()) {
        try {
          const parsedParams = JSON.parse(jsonInput);
          
          // Validate that it's an object (not array, string, etc.)
          if (typeof parsedParams !== 'object' || Array.isArray(parsedParams) || parsedParams === null) {
            throw new Error('Voice meta parameters must be a JSON object');
          }
          
          // Set the parsed parameters
          data.voice_meta_params = parsedParams;
          
        } catch (error) {
          console.error('[SettingsManager] Failed to parse Voice meta params JSON:', error);
          this.emit('error', { message: error.message });
          form.dataset.submitting = 'false';
          this.setProfileFormSubmitting(false);
          return;
        }
      }
      
      // Remove the JSON field as it's not needed in the API request
      delete data.voice_meta_params_json;
    }
    
    // Handle MCP server params structure - parse JSON input
    if (type === 'mcp') {
      const jsonInput = data.mcp_server_params_json;
      
      // Check if JSON was pre-validated
      const jsonTextarea = form.querySelector('textarea[name="mcp_server_params_json"]');
      if (jsonTextarea && jsonTextarea.dataset.isValid === 'false') {
        console.error('[SettingsManager] JSON validation failed during form submission');
        this.emit('error', { 
          message: jsonTextarea.dataset.errorMessage || 'Invalid JSON format'
        });
        form.dataset.submitting = 'false';
        this.setProfileFormSubmitting(false);
        return;
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
          
        } catch (error) {
          console.error('[SettingsManager] Failed to parse MCP server params JSON:', error);
          this.emit('error', { message: error.message });
          form.dataset.submitting = 'false';
          this.setProfileFormSubmitting(false);
          return;
        }
      }
      
      // Remove the JSON field as it's not needed in the API request
      delete data.mcp_server_params_json;
    }
    
    try {
      console.log(`[SettingsManager] Starting ${mode} operation for ${type} profile`);
      let response;
      
      if (mode === 'create') {
        if (type === 'llm') {
          response = await this.apiClient.createLLMProfile(data);
        } else if (type === 'voice') {
          response = await this.apiClient.createVoiceProfile(data);
        } else {
          response = await this.apiClient.createMCPProfile(data);
        }
      } else {
        if (type === 'llm') {
          response = await this.apiClient.updateLLMProfile(profileId, data);
        } else if (type === 'voice') {
          response = await this.apiClient.updateVoiceProfile(profileId, data);
        } else {
          response = await this.apiClient.updateMCPProfile(profileId, data);
        }
      }
      
      this.closeProfileForm();
      this.emit('notification', {
        message: `${type.toUpperCase()} profile ${mode === 'create' ? 'created' : 'updated'} successfully`,
        type: 'success'
      });
      
      // Refresh the settings data
      await this.loadSettingsData();
      
    } catch (error) {
      console.error(`[SettingsManager] Failed to ${mode} ${type} profile:`, error);
      
      // Handle specific error types for better user experience
      let errorMessage = error.message || 'Unknown error occurred';
      
      if (errorMessage.includes('already exists') || errorMessage.includes('already in use')) {
        this.highlightProfileNameError(errorMessage);
      } else if (errorMessage.includes('UNIQUE constraint')) {
        errorMessage = `Profile name '${data.profile_name || data.display_name}' already exists. Please choose a different name.`;
        this.highlightProfileNameError(errorMessage);
      }
      
      this.emit('notification', {
        message: `Failed to ${mode} ${type} profile: ${errorMessage}`,
        type: 'error'
      });
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
    }
  }

  async handleThemeChange(event) {
    const selectedTheme = event.target.value;
    
    try {
      // Store theme preference in user settings storage
      await this.userSettingsStorage.setTheme(selectedTheme);
      
      // Apply theme to document
      this.applyTheme(selectedTheme);
      
      this.emit('notification', {
        message: `Theme changed to ${selectedTheme}`,
        type: 'success'
      });
      
    } catch (error) {
      console.error('[SettingsManager] Failed to change theme:', error);
      this.emit('notification', {
        message: 'Failed to change theme',
        type: 'error'
      });
    }
  }


  applyTheme(theme) {
    const root = document.documentElement;
    
    if (theme === 'dark') {
      root.setAttribute('data-theme', 'dark');
      root.classList.add('dark-theme');
      root.classList.remove('light-theme');
    } else if (theme === 'light') {
      root.setAttribute('data-theme', 'light');
      root.classList.add('light-theme');
      root.classList.remove('dark-theme');
    } else { // auto
      root.classList.remove('dark-theme', 'light-theme');
      // Let system preference take over
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        root.setAttribute('data-theme', 'dark');
        root.classList.add('dark-theme');
      } else {
        root.setAttribute('data-theme', 'light');
        root.classList.add('light-theme');
      }
    }
    
    // Force a repaint to ensure theme changes are applied immediately
    document.body.style.display = 'none';
    document.body.offsetHeight; // trigger reflow
    document.body.style.display = '';
  }

  async handleBackendUrlChange(event) {
    const newUrl = event.target.value.trim();
    
    if (!newUrl) {
      this.emit('notification', {
        message: 'Backend URL cannot be empty',
        type: 'warning'
      });
      return;
    }
    
    try {
      // Validate URL format
      new URL(newUrl);
      
      // Update API client
      this.apiClient.setBaseURL(newUrl);
      
      // Emit event to update settings
      this.emit('settingsUpdated', { backendUrl: newUrl });
      
      this.emit('notification', {
        message: 'Backend URL updated successfully',
        type: 'success'
      });
      
    } catch (error) {
      this.emit('notification', {
        message: `Invalid backend URL: ${error.message}`,
        type: 'error'
      });
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
      this.emit('notification', {
        message: 'Environment variables updated successfully (backend URL variables are read-only)',
        type: 'success'
      });
    } catch (error) {
      console.error('[SettingsManager] Failed to update environment variables:', error);
      this.emit('notification', {
        message: `Failed to update environment variables: ${error.message}`,
        type: 'error'
      });
    }
  }

  // Rendering Methods
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

  renderVoiceProfiles(profiles) {
    const container = document.getElementById('voice-profiles-list');
    if (!container) return;

    if (profiles.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 14C19 18.5 15.5 22 11 22C6.5 22 3 18.5 3 14V12C3 7.5 6.5 4 11 4S19 7.5 19 12V14ZM11 8C8.8 8 7 9.8 7 12V14C7 16.2 8.8 18 11 18S15 16.2 15 14V12C15 9.8 13.2 8 11 8Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="11" cy="11" r="2" stroke="currentColor" stroke-width="2"/>
          </svg>
          <h3>No Voice Profiles</h3>
          <p>Create your first voice profile to enable speech features</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_active ? 'active' : 'inactive'}" data-profile-id="${profile.voice_profile_name}">
        <div class="profile-status ${profile.is_active ? 'active' : 'inactive'}">
          ${profile.is_active ? 'Active' : 'Inactive'}
        </div>
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.voice_profile_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.voice_model_name)} (${profile.voice_model_type.toUpperCase()})</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="Edit Profile" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="Delete Profile" data-profile-id="${profile.voice_profile_name}">
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
            <div class="profile-detail"><strong>Model:</strong> ${this.escapeHtml(profile.voice_model_name)}</div>
            <div class="profile-detail"><strong>Type:</strong> ${profile.voice_model_type.toUpperCase()}</div>
            ${profile.voice_meta_params ? `<div class="profile-detail"><strong>Parameters:</strong> ${Object.keys(profile.voice_meta_params).length} custom settings</div>` : ''}
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
        this.showProfileForm('voice', profile);
      });
    });

    container.querySelectorAll('.delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await this.handleDeleteProfile('voice', btn.dataset.profileId);
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
    
    // Emit confirmation request to main UI manager
    this.emit('confirmDeletion', {
      type,
      profileId,
      callback: () => this.performDeleteProfile(type, profileId)
    });
  }

  async handleDeleteDefaultProfile(profileId) {
    // Get other available profiles
    const otherProfiles = this.state.llmProfiles.filter(p => p.profile_name !== profileId);
    
    if (otherProfiles.length === 0) {
      // No other profiles available - cannot delete
      this.emit('error', {
        message: 'This is the only LLM profile configured. You cannot delete it without having at least one other profile.',
        details: 'Please create another LLM profile first, then you can delete this one.',
        buttons: [
          {
            text: 'Create New Profile',
            action: () => this.handleAddProfile('llm')
          }
        ]
      });
      return false;
    }
    
    // Show modal to select new default profile
    this.emit('selectNewDefault', {
      profileId,
      otherProfiles,
      callback: (newDefaultProfileId) => this.setNewDefaultAndDelete(newDefaultProfileId, profileId)
    });
  }

  async setNewDefaultAndDelete(newDefaultProfileId, profileToDelete) {
    try {
      this.emit('loading', { message: 'Updating default profile...' });
      
      // First, set the new default profile
      await this.apiClient.updateLLMProfile(newDefaultProfileId, { is_default: true });
      
      this.emit('loading', { message: 'Deleting profile...' });
      
      // Then delete the old default profile
      await this.apiClient.deleteLLMProfile(profileToDelete);
      
      this.emit('notification', {
        message: `Profile "${profileToDelete}" deleted and "${newDefaultProfileId}" set as default`,
        type: 'success'
      });
      
      // Refresh the settings data
      await this.loadSettingsData();
      
      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      console.error('[SettingsManager] Failed to set new default and delete profile:', error);
      this.emit('notification', {
        message: `Failed to update profiles: ${error.message}`,
        type: 'error'
      });
      throw error;
    }
  }

  async performDeleteProfile(type, profileId) {
    try {
      this.emit('loading', { message: `Deleting ${type} profile...` });
      
      if (type === 'llm') {
        await this.apiClient.deleteLLMProfile(profileId);
      } else if (type === 'voice') {
        await this.apiClient.deleteVoiceProfile(profileId);
      } else {
        await this.apiClient.deleteMCPProfile(profileId);
      }
      
      this.emit('notification', {
        message: `${type.toUpperCase()} profile deleted successfully`,
        type: 'success'
      });
      
      // Refresh the settings data
      await this.loadSettingsData();
      
      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      console.error(`[SettingsManager] Failed to delete ${type} profile:`, error);
      this.emit('notification', {
        message: `Failed to delete ${type} profile: ${error.message}`,
        type: 'error'
      });
    }
  }

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Public interface
  getState() {
    return { ...this.state };
  }

  getLLMProfiles() {
    return this.state.llmProfiles || [];
  }

  getMCPProfiles() {
    return this.state.mcpProfiles || [];
  }

  getVoiceProfiles() {
    return this.state.voiceProfiles || [];
  }

  showModal() {
    if (this.elements.settingsModal) {
      this.elements.settingsModal.classList.remove('hidden');
    }
  }

  showSettings() {
    this.showModal();
  }

  hideModal() {
    if (this.elements.settingsModal) {
      this.elements.settingsModal.classList.add('hidden');
    }
  }

  updateBackendUrl(url) {
    if (this.elements.backendUrl) {
      this.elements.backendUrl.value = url;
    }
  }

  // Navigate to specific LLM profile for editing
  async navigateToLLMProfile(profileName) {
    console.log('[SettingsManager] Navigating to LLM profile:', profileName);
    
    // First show the settings modal
    this.showSettings();
    
    // Switch to LLM profiles tab
    const llmTab = document.querySelector('.settings-tab[data-tab="llm-profiles"]');
    if (llmTab) {
      llmTab.click(); // This will trigger handleTabSwitch
    }
    
    // Wait a moment for tab switching to complete
    setTimeout(async () => {
      // Find the profile in the current state
      const profile = this.state.llmProfiles.find(p => p.profile_name === profileName);
      
      if (profile) {
        // Show the edit form for this profile
        await this.showProfileForm('llm', profile);
        console.log('[SettingsManager] LLM profile edit form shown for:', profileName);
      } else {
        console.warn('[SettingsManager] Profile not found:', profileName);
        this.emit('notification', {
          message: `LLM profile "${profileName}" not found. Please check if it still exists.`,
          type: 'warning'
        });
      }
    }, 100);
  }

  // === INTEGRATIONS FUNCTIONALITY ===
  
  // Load integrations data when tab is opened
  async loadIntegrationsData() {
    try {
      console.log('[SettingsManager] Loading integrations data...');
      console.log('[SettingsManager] API client available:', !!this.apiClient);
      
      // Show loading state immediately
      this.showIntegrationsLoading();
      
      // Check Composio status (which will handle instance restoration if needed)
      const status = await this.checkComposioStatus();
      
      console.log('[SettingsManager] Status check result:', status);
      
      if (status && status.connected && status.key_valid) {
        console.log('[SettingsManager] Valid Composio connection found, loading toolkits from database...');
        // Load toolkits from database (no sync by default for faster loading)
        await this.loadToolkits(false);
        console.log('[SettingsManager] Toolkits loaded, showing integrations content...');
        this.showIntegrationsContent();
        console.log('[SettingsManager] Integrations content shown');
      } else {
        console.log('[SettingsManager] No valid Composio connection, showing setup modal automatically');
        console.log('[SettingsManager] Status details - connected:', status?.connected, 'key_valid:', status?.key_valid);
        // Automatically show setup modal instead of setup UI
        this.hideIntegrationsLoading();
        this.showApiKeyModal();
      }
    } catch (error) {
      console.error('[SettingsManager] Failed to load integrations data:', error);
      this.hideIntegrationsLoading();
      this.emit('notification', {
        message: 'Failed to load integrations data',
        type: 'error'
      });
    }
  }

  // Check Composio API key status
  async checkComposioStatus() {
    try {
      console.log('[SettingsManager] Checking Composio status...');
      const response = await this.apiClient.getComposioStatus();
      console.log('[SettingsManager] Composio status response:', response);
      
      // Use the new response format
      this.state.composioKeyValid = response.connected && response.key_valid;
      this.state.composioApiKey = response.has_key ? '***' : null;
      
      console.log('[SettingsManager] Composio state updated:', {
        connected: response.connected,
        keyValid: response.key_valid,
        hasKey: response.has_key,
        instanceAvailable: response.instance_available,
        message: response.message
      });
      
      return response;
    } catch (error) {
      console.error('[SettingsManager] Failed to check Composio status:', error);
      this.state.composioKeyValid = false;
      this.state.composioApiKey = null;
      return {
        connected: false,
        key_valid: false,
        has_key: false,
        instance_available: false,
        message: 'Status check failed'
      };
    }
  }

  // Show integrations loading state
  showIntegrationsLoading() {
    if (this.elements.composioStatus) {
      this.elements.composioStatus.innerHTML = `
        <div class="status-item info">
          <div class="status-icon loading-spinner">⟳</div>
          <div class="status-content">
            <div class="status-title">Checking Connection</div>
            <div class="status-description">Verifying Composio integration status...</div>
          </div>
        </div>
      `;
    }
    
    if (this.elements.apiKeySetup) {
      this.elements.apiKeySetup.style.display = 'none';
    }
    
    if (this.elements.toolkitsSection) {
      this.elements.toolkitsSection.style.display = 'none';
    }
  }
  
  // Hide integrations loading state
  hideIntegrationsLoading() {
    // Loading state will be replaced by either connected status or setup modal
  }
  
  // Show integrations main content
  showIntegrationsContent() {
    console.log('[SettingsManager] showIntegrationsContent called');
    console.log('[SettingsManager] composioStatus element exists:', !!this.elements.composioStatus);
    console.log('[SettingsManager] toolkitsSection element exists:', !!this.elements.toolkitsSection);
    
    if (this.elements.composioStatus) {
      this.elements.composioStatus.innerHTML = `
        <div class="status-item success">
          <div class="status-icon">✓</div>
          <div class="status-content">
            <div class="status-title">Composio Connected</div>
            <div class="status-description">API key is valid and ready to use</div>
          </div>
          <button id="update-api-key-btn" class="btn btn-secondary btn-sm">
            Update Key
          </button>
        </div>
      `;
      
      // Re-bind the update button event
      const updateBtn = document.getElementById('update-api-key-btn');
      if (updateBtn) {
        updateBtn.addEventListener('click', this.handleSetupApiKey.bind(this));
      }
    }
    
    if (this.elements.apiKeySetup) {
      this.elements.apiKeySetup.style.display = 'none';
    }
    
    if (this.elements.toolkitsSection) {
      this.elements.toolkitsSection.classList.remove('hidden');
      this.elements.toolkitsSection.style.display = 'block';
      console.log('[SettingsManager] toolkitsSection display set to block and hidden class removed');
    } else {
      console.error('[SettingsManager] toolkitsSection element not found!');
    }
  }

  // Handle API key setup button click
  handleSetupApiKey() {
    console.log('[SettingsManager] Setup API key button clicked');
    this.showApiKeyModal();
  }

  // Show API key modal
  showApiKeyModal() {
    console.log('[SettingsManager] Showing API key modal');
    console.log('[SettingsManager] Modal element exists:', !!this.elements.composioApiKeyModal);
    
    if (this.elements.composioApiKeyModal) {
      this.elements.composioApiKeyModal.classList.remove('hidden');
      
      // Clear previous input and validation
      if (this.elements.composioApiKeyInput) {
        this.elements.composioApiKeyInput.value = '';
      }
      this.hideApiKeyValidation();
      
      // Focus on input
      setTimeout(() => {
        if (this.elements.composioApiKeyInput) {
          this.elements.composioApiKeyInput.focus();
        }
      }, 100);
      
      console.log('[SettingsManager] API key modal shown successfully');
    } else {
      console.error('[SettingsManager] API key modal element not found!');
    }
  }

  // Hide API key modal
  hideApiKeyModal() {
    if (this.elements.composioApiKeyModal) {
      this.elements.composioApiKeyModal.classList.add('hidden');
    }
  }

  // Handle Composio link open
  handleOpenComposioLink() {
    // Open Composio website in new tab using Chrome extension API
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.create({ url: 'https://composio.dev/' });
    } else {
      // Fallback for non-extension context
      window.open('https://composio.dev/', '_blank');
    }
  }

  // Handle API key confirm
  async handleApiKeyConfirm() {
    const apiKey = this.elements.composioApiKeyInput?.value?.trim();
    
    if (!apiKey) {
      this.showApiKeyValidation('Please enter an API key', 'error');
      return;
    }

    try {
      this.showApiKeyValidation('Validating API key...', 'info');
      
      const response = await this.apiClient.verifyComposioKey(apiKey);
      
      if (response.valid) {
        this.showApiKeyValidation('API key is valid!', 'success');
        
        // Update state
        this.state.composioKeyValid = true;
        this.state.composioApiKey = '***';
        
        // Show integrations content and load toolkits
        this.showIntegrationsContent();
        await this.loadToolkits(false);
        
        // Close modal after short delay
        setTimeout(() => {
          this.hideApiKeyModal();
        }, 1000);
        
        this.emit('notification', {
          message: 'Composio API key validated and saved successfully',
          type: 'success'
        });
        
      } else {
        this.showApiKeyValidation('Invalid API key. Please check and try again.', 'error');
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to verify API key:', error);
      this.showApiKeyValidation(`Failed to verify API key: ${error.message}`, 'error');
    }
  }

  // Show API key validation message
  showApiKeyValidation(message, type) {
    if (!this.elements.apiKeyValidation) return;
    
    const className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
    this.elements.apiKeyValidation.innerHTML = `
      <div class="validation-message ${className}">
        ${this.escapeHtml(message)}
      </div>
    `;
    this.elements.apiKeyValidation.style.display = 'block';
  }

  // Hide API key validation message
  hideApiKeyValidation() {
    if (this.elements.apiKeyValidation) {
      this.elements.apiKeyValidation.style.display = 'none';
      this.elements.apiKeyValidation.innerHTML = '';
    }
  }

  // Handle API key toggle visibility
  handleApiKeyToggle() {
    const input = this.elements.composioApiKeyInput;
    if (!input) return;
    
    const toggle = this.elements.composioApiKeyModal?.querySelector('.api-key-toggle');
    if (!toggle) return;
    
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    
    // Update icon
    const svg = toggle.querySelector('svg');
    if (svg) {
      svg.innerHTML = isPassword ?
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C7 20 2.73 16.39 1 12A18.45 18.45 0 0 1 5.06 5.06L17.94 17.94ZM9.9 4.24A9.12 9.12 0 0 1 12 4C17 4 21.27 7.61 23 12A18.5 18.5 0 0 1 19.42 16.42" stroke="currentColor" stroke-width="2" fill="none"/><path d="M1 1L23 23" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/>' :
        '<path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>';
    }
  }

  // Load toolkits from API
  async loadToolkits(forceSync = false) {
    try {
      console.log('[SettingsManager] Loading Composio toolkits...');
      
      if (this.elements.toolkitsLoading) {
        this.elements.toolkitsLoading.style.display = 'block';
      }
      
      // Load toolkits from database first (no API sync by default)
      const params = forceSync ? { sync_with_api: true } : { sync_with_api: false };
      const response = await this.apiClient.getComposioToolkits(params);
      
      // Handle different response structures
      this.state.toolkits = response.toolkits || response || [];
      
      // Convert toolkit data to frontend format with connection status
      this.state.toolkits = this.state.toolkits.map(toolkit => ({
        id: toolkit.id,
        name: toolkit.name,
        slug: toolkit.slug,
        description: toolkit.description || '',
        logo: toolkit.logo || '',
        app_url: toolkit.app_url || '',
        enabled: toolkit.enabled || false,
        tools: toolkit.tools || {},
        connected: false, // Will be updated by connection status check
        connection_status: toolkit.connection_status || 'unknown'
      }));

      // Check connection status for enabled toolkits
      await this.updateToolkitConnectionStatuses();
      
      // Apply current search and filter
      this.filterToolkits();
      
      console.log('[SettingsManager] Loaded toolkits:', this.state.toolkits.length);
      console.log('[SettingsManager] Filtered toolkits:', this.state.filteredToolkits.length);
      
      if (forceSync && response.synced_count > 0) {
        this.emit('notification', {
          message: `Synced ${response.synced_count} new toolkits from Composio`,
          type: 'success'
        });
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to load toolkits:', error);
      this.state.toolkits = [];
      this.state.filteredToolkits = [];
      this.renderToolkits();
      
      this.emit('notification', {
        message: 'Failed to load Composio toolkits',
        type: 'error'
      });
    } finally {
      if (this.elements.toolkitsLoading) {
        this.elements.toolkitsLoading.style.display = 'none';
      }
    }
  }

  // Handle toolkit search
  handleToolkitSearch(event) {
    this.state.searchQuery = event.target.value.toLowerCase().trim();
    this.filterToolkits();
  }

  // Handle toolkit filter
  handleToolkitFilter(event) {
    this.state.filterStatus = event.target.value;
    this.filterToolkits();
  }

  // Filter toolkits based on search and filter
  filterToolkits() {
    let filtered = [...this.state.toolkits];
    
    // Apply search filter
    if (this.state.searchQuery) {
      filtered = filtered.filter(toolkit =>
        toolkit.name.toLowerCase().includes(this.state.searchQuery) ||
        toolkit.description.toLowerCase().includes(this.state.searchQuery)
      );
    }
    
    // Apply status filter
    if (this.state.filterStatus !== 'all') {
      if (this.state.filterStatus === 'enabled') {
        filtered = filtered.filter(toolkit => toolkit.enabled === true);
      } else if (this.state.filterStatus === 'disabled') {
        filtered = filtered.filter(toolkit => toolkit.enabled === false);
      } else if (this.state.filterStatus === 'connected') {
        filtered = filtered.filter(toolkit => toolkit.connected === true);
      } else if (this.state.filterStatus === 'unconnected') {
        filtered = filtered.filter(toolkit => toolkit.connected === false);
      }
    }
    
    this.state.filteredToolkits = filtered;
    console.log('[SettingsManager] Filtered toolkits for rendering:', filtered.length);
    this.renderToolkits();
  }

  // Render toolkits list
  renderToolkits() {
    console.log('[SettingsManager] renderToolkits called');
    console.log('[SettingsManager] toolkitsList element exists:', !!this.elements.toolkitsList);
    
    if (!this.elements.toolkitsList) {
      console.error('[SettingsManager] toolkitsList element not found!');
      return;
    }
    
    const toolkits = this.state.filteredToolkits;
    console.log('[SettingsManager] Rendering toolkits:', toolkits.length);
    
    if (toolkits.length === 0) {
      const isEmpty = this.state.toolkits.length === 0;
      this.elements.toolkitsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔧</div>
          <div class="empty-state-title">${isEmpty ? 'No Toolkits Available' : 'No Matching Toolkits'}</div>
          <div class="empty-state-description">
            ${isEmpty ? 'No toolkits are available at the moment.' : 'Try adjusting your search or filter criteria.'}
          </div>
        </div>
      `;
      return;
    }

    const toolkitsHTML = toolkits.map(toolkit => `
      <div class="toolkit-card" data-toolkit-slug="${toolkit.slug}">
        <div class="toolkit-header">
          <div class="toolkit-logo">
            <img src="${toolkit.logo || 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJMMiA3TDEyIDEyTDIyIDdMMTIgMloiIHN0cm9rZT0iY3VycmVudENvbG9yIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8cGF0aCBkPSJNMiAxN0wxMiAyMkwyMiAxNyIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+CjxwYXRoIGQ9Ik0yIDEyTDEyIDE3TDIyIDEyIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+'}" alt="${this.escapeHtml(toolkit.name)}" class="toolkit-logo-img">
          </div>
          <div class="toolkit-info">
            <div class="toolkit-name">${this.escapeHtml(toolkit.name)}</div>
            <div class="toolkit-description">${this.escapeHtml(toolkit.description)}</div>
          </div>
          <div class="toolkit-actions">
            <label class="toolkit-toggle">
              <input type="checkbox" ${toolkit.enabled ? 'checked' : ''}
                     data-toolkit-slug="${toolkit.slug}"
                     class="toolkit-toggle-input">
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
        <div class="toolkit-footer">
          <button class="btn btn-secondary btn-sm toolkit-tools-btn"
                   data-toolkit-slug="${toolkit.slug}"
                   ${!toolkit.connected ? 'disabled' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2"/>
            </svg>
            Manage Tools
          </button>
          <div class="toolkit-status ${toolkit.connected ? 'connected' : 'disconnected'}">
            ${toolkit.connected ? 'Connected' : 'Not Connected'}
          </div>
        </div>
      </div>
    `).join('');

    console.log('[SettingsManager] Setting toolkits HTML, length:', toolkitsHTML.length);
    this.elements.toolkitsList.innerHTML = toolkitsHTML;
    console.log('[SettingsManager] HTML set successfully');
    
    // Bind event listeners for toolkit interactions
    this.bindToolkitEvents();
    console.log('[SettingsManager] Event binding completed');
  }

  // Bind toolkit event listeners
  bindToolkitEvents() {
    if (!this.elements.toolkitsList) return;
    
    // Bind toggle inputs
    const toggleInputs = this.elements.toolkitsList.querySelectorAll('.toolkit-toggle-input');
    toggleInputs.forEach(input => {
      input.addEventListener('change', this.handleToolkitToggle.bind(this));
    });
    
    // Bind manage tools buttons
    const toolsButtons = this.elements.toolkitsList.querySelectorAll('.toolkit-tools-btn');
    toolsButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const toolkitSlug = e.target.dataset.toolkitSlug;
        if (toolkitSlug && !e.target.disabled) {
          this.handleManageTools(toolkitSlug);
        }
      });
    });
    
    // Bind image error handlers to replace CSP-blocked onerror attributes
    const logoImages = this.elements.toolkitsList.querySelectorAll('.toolkit-logo-img');
    logoImages.forEach(img => {
      img.addEventListener('error', () => {
        img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJMMiA3TDEyIDEyTDIyIDdMMTIgMloiIHN0cm9rZT0iY3VycmVudENvbG9yIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8cGF0aCBkPSJNMiAxN0wxMiAyMkwyMiAxNyIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+CjxwYXRoIGQ9Ik0yIDEyTDEyIDE3TDIyIDEyIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+';
      });
    });
  }

  // Handle toolkit toggle
  async handleToolkitToggle(event) {
    const checkbox = event.target;
    const toolkitSlug = checkbox.dataset.toolkitSlug;
    const isEnabled = checkbox.checked;

    try {
      console.log(`[SettingsManager] Toggling toolkit ${toolkitSlug}: ${isEnabled}`);
      
      const response = await this.apiClient.toggleComposioToolkit(toolkitSlug, isEnabled);
      
      if (response.requires_oauth && !response.connected) {
        // OAuth flow required
        console.log(`[SettingsManager] OAuth required for ${toolkitSlug}, URL:`, response.oauth_url);
        await this.handleOAuthFlow(toolkitSlug, response.oauth_url);
        
        // Revert toggle until OAuth is complete
        checkbox.checked = !isEnabled;
        return;
      }
      
      // Update toolkit state
      const toolkit = this.state.toolkits.find(t => t.slug === toolkitSlug);
      if (toolkit) {
        toolkit.enabled = response.enabled;
        toolkit.connected = response.connected;
      }
      
      // Re-filter and render
      this.filterToolkits();
      
      this.emit('notification', {
        message: `Toolkit ${toolkit?.name || toolkitSlug} ${isEnabled ? 'enabled' : 'disabled'}`,
        type: 'success'
      });
      
    } catch (error) {
      console.error('[SettingsManager] Failed to toggle toolkit:', error);
      
      // Revert checkbox state
      checkbox.checked = !isEnabled;
      
      this.emit('notification', {
        message: `Failed to ${isEnabled ? 'enable' : 'disable'} toolkit: ${error.message}`,
        type: 'error'
      });
    }
  }

  // Handle OAuth flow
  async handleOAuthFlow(toolkitSlug, oauthUrl) {
    try {
      console.log(`[SettingsManager] Starting OAuth flow for ${toolkitSlug}`);
      
      // Open OAuth URL in new tab using Chrome extension API
      if (typeof chrome !== 'undefined' && chrome.tabs) {
        chrome.tabs.create({ url: oauthUrl });
      } else {
        // Fallback for non-extension context
        window.open(oauthUrl, '_blank');
      }
      
      // Show OAuth confirmation modal
      this.showOAuthModal(toolkitSlug);
      
    } catch (error) {
      console.error('[SettingsManager] Failed to handle OAuth flow:', error);
      this.emit('notification', {
        message: 'Failed to start OAuth flow',
        type: 'error'
      });
    }
  }

  // Show OAuth confirmation modal
  showOAuthModal(toolkitSlug) {
    this.state.currentToolkit = toolkitSlug;
    
    if (this.elements.oauthConfirmationModal) {
      this.elements.oauthConfirmationModal.classList.remove('hidden');
    }
  }

  // Hide OAuth confirmation modal
  hideOAuthModal() {
    if (this.elements.oauthConfirmationModal) {
      this.elements.oauthConfirmationModal.classList.add('hidden');
    }
    this.state.currentToolkit = null;
  }

  // Handle OAuth completed
  async handleOAuthCompleted() {
    if (!this.state.currentToolkit) {
      this.hideOAuthModal();
      return;
    }

    try {
      console.log(`[SettingsManager] Checking OAuth completion for ${this.state.currentToolkit}`);
      
      // Check connection status for the specific toolkit
      const statusResponse = await this.apiClient.getComposioToolkitConnectionStatus(this.state.currentToolkit);
      
      if (statusResponse.connected) {
        // Update state
        const stateToolkit = this.state.toolkits.find(t => t.slug === this.state.currentToolkit);
        if (stateToolkit) {
          stateToolkit.connected = true;
          stateToolkit.enabled = true;
        }
        
        // Re-load toolkits to get latest state
        await this.loadToolkits();
        
        this.emit('notification', {
          message: `${stateToolkit?.name || this.state.currentToolkit} connected successfully!`,
          type: 'success'
        });
      } else {
        this.emit('notification', {
          message: 'OAuth connection not detected. Please try again.',
          type: 'warning'
        });
      }
      
    } catch (error) {
      console.error('[SettingsManager] Failed to check OAuth completion:', error);
      this.emit('notification', {
        message: 'Failed to verify OAuth connection',
        type: 'error'
      });
    } finally {
      this.hideOAuthModal();
    }
  }

  // Handle manage tools
  async handleManageTools(toolkitSlug) {
    this.state.currentToolkit = toolkitSlug;
    
    try {
      const toolkit = this.state.toolkits.find(t => t.slug === toolkitSlug);
      if (!toolkit) {
        throw new Error('Toolkit not found');
      }
      
      this.showToolsModal(toolkit);
      await this.loadToolkitTools(toolkitSlug);
      
    } catch (error) {
      console.error('[SettingsManager] Failed to manage tools:', error);
      this.emit('notification', {
        message: 'Failed to load toolkit tools',
        type: 'error'
      });
    }
  }

  // Show tools management modal
  showToolsModal(toolkit) {
    if (!this.elements.toolsManagementModal) return;
    
    // Update modal title and info
    if (this.elements.toolsModalTitle) {
      this.elements.toolsModalTitle.textContent = `Manage ${toolkit.name} Tools`;
    }
    
    if (this.elements.toolkitLogo) {
      this.elements.toolkitLogo.src = toolkit.logo || '/default-toolkit-logo.svg';
      this.elements.toolkitLogo.alt = toolkit.name;
    }
    
    if (this.elements.toolkitName) {
      this.elements.toolkitName.textContent = toolkit.name;
    }
    
    // Show modal
    this.elements.toolsManagementModal.classList.remove('hidden');
  }

  // Hide tools management modal
  hideToolsModal() {
    if (this.elements.toolsManagementModal) {
      this.elements.toolsManagementModal.classList.add('hidden');
    }
    this.state.currentToolkit = null;
  }

  // Load toolkit tools
  async loadToolkitTools(toolkitSlug) {
    if (!this.elements.toolsList || !this.elements.toolsLoading) return;

    try {
      this.elements.toolsLoading.style.display = 'block';
      this.elements.toolsList.innerHTML = '';
      
      const response = await this.apiClient.getComposioToolkitTools(toolkitSlug);
      const tools = response.tools || response || [];
      
      this.renderTools(tools);
      
    } catch (error) {
      console.error('[SettingsManager] Failed to load toolkit tools:', error);
      this.elements.toolsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠</div>
          <div class="empty-state-title">Failed to Load Tools</div>
          <div class="empty-state-description">Unable to fetch tools for this toolkit.</div>
        </div>
      `;
    } finally {
      this.elements.toolsLoading.style.display = 'none';
    }
  }

  // Render tools list
  renderTools(tools) {
    if (!this.elements.toolsList) return;
    
    if (tools.length === 0) {
      this.elements.toolsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔧</div>
          <div class="empty-state-title">No Tools Available</div>
          <div class="empty-state-description">This toolkit has no tools available.</div>
        </div>
      `;
      return;
    }

    const toolsHTML = `
      <div class="tools-table">
        <div class="tools-header">
          <div class="tool-cell tool-checkbox">
            <input type="checkbox" id="select-all-tools-checkbox">
          </div>
          <div class="tool-cell tool-name">Tool Name</div>
          <div class="tool-cell tool-description">Description</div>
        </div>
        <div class="tools-body">
          ${tools.map(tool => `
            <div class="tool-row">
              <div class="tool-cell tool-checkbox">
                <input type="checkbox" class="tool-checkbox-input"
                       data-tool-name="${tool.name}"
                       ${tool.enabled ? 'checked' : ''}>
              </div>
              <div class="tool-cell tool-name">${this.escapeHtml(tool.name)}</div>
              <div class="tool-cell tool-description">${this.escapeHtml(tool.description || 'No description available')}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    this.elements.toolsList.innerHTML = toolsHTML;
    
    // Setup select all functionality
    const selectAllCheckbox = this.elements.toolsList.querySelector('#select-all-tools-checkbox');
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener('change', (e) => {
        const toolCheckboxes = this.elements.toolsList.querySelectorAll('.tool-checkbox-input');
        toolCheckboxes.forEach(checkbox => {
          checkbox.checked = e.target.checked;
        });
      });
    }
  }

  // Handle select all tools
  handleSelectAllTools() {
    const toolCheckboxes = this.elements.toolsList?.querySelectorAll('.tool-checkbox-input');
    if (toolCheckboxes) {
      toolCheckboxes.forEach(checkbox => {
        checkbox.checked = true;
      });
    }
  }

  // Handle deselect all tools
  handleDeselectAllTools() {
    const toolCheckboxes = this.elements.toolsList?.querySelectorAll('.tool-checkbox-input');
    if (toolCheckboxes) {
      toolCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
      });
    }
  }

  // Handle tools save
  async handleToolsSave() {
    if (!this.state.currentToolkit) {
      console.error('[SettingsManager] No current toolkit selected for save');
      return;
    }

    try {
      console.log(`[SettingsManager] Saving tools for ${this.state.currentToolkit}`);
      
      // Get all tools with their selection status as dictionary
      const toolCheckboxes = this.elements.toolsList?.querySelectorAll('.tool-checkbox-input');
      const selectedTools = {};
      
      if (toolCheckboxes) {
        console.log(`[SettingsManager] Found ${toolCheckboxes.length} tool checkboxes`);
        toolCheckboxes.forEach(checkbox => {
          const toolName = checkbox.dataset.toolName;
          const isSelected = checkbox.checked;
          selectedTools[toolName] = isSelected;
          console.log(`[SettingsManager] Tool ${toolName}: ${isSelected ? 'selected' : 'not selected'}`);
        });
      } else {
        console.warn('[SettingsManager] No tool checkboxes found');
      }
      
      console.log(`[SettingsManager] Selected tools:`, selectedTools);
      
      // Save tools selection
      const response = await this.apiClient.updateComposioToolkitTools(this.state.currentToolkit, selectedTools);
      console.log(`[SettingsManager] Save response:`, response);
      
      this.emit('notification', {
        message: 'Tools configuration saved successfully',
        type: 'success'
      });
      
      // Close modal
      this.hideToolsModal();
      
    } catch (error) {
      console.error('[SettingsManager] Failed to save tools:', error);
      this.emit('notification', {
        message: `Failed to save tools configuration: ${error.message}`,
        type: 'error'
      });
    }
  }
  
    // Update connection status for all enabled toolkits
    async updateToolkitConnectionStatuses() {
      try {
        const enabledToolkits = this.state.toolkits.filter(toolkit => toolkit.enabled);
        
        if (enabledToolkits.length === 0) {
          return;
        }
        
        // Check connection status for each enabled toolkit
        const connectionPromises = enabledToolkits.map(async (toolkit) => {
          try {
            const statusResponse = await this.apiClient.getComposioToolkitConnectionStatus(toolkit.slug);
            
            // Update toolkit connection status
            const toolkitIndex = this.state.toolkits.findIndex(t => t.slug === toolkit.slug);
            if (toolkitIndex !== -1) {
              this.state.toolkits[toolkitIndex].connected = statusResponse.connected;
              this.state.toolkits[toolkitIndex].connection_status = statusResponse.status;
            }
            
            return { slug: toolkit.slug, connected: statusResponse.connected, status: statusResponse.status };
          } catch (error) {
            console.error(`[SettingsManager] Failed to check connection status for ${toolkit.slug}:`, error);
            // Keep as disconnected on error
            return { slug: toolkit.slug, connected: false, status: 'error' };
          }
        });
        
        const results = await Promise.all(connectionPromises);
        console.log('[SettingsManager] Connection status check results:', results);
        
      } catch (error) {
        console.error('[SettingsManager] Failed to update toolkit connection statuses:', error);
      }
    }
    
    // === WORKFLOW TAB FUNCTIONALITY ===
    
    // Load workflow content when tab is opened
    async loadWorkflowContent() {
      try {
        console.log('[SettingsManager] Loading workflow content...');
        
        // Show loading state
        this.showWorkflowsLoading();
        
        // Load workflows from backend
        await this.loadWorkflows();
        
        console.log('[SettingsManager] Workflow content loaded');
        
      } catch (error) {
        console.error('[SettingsManager] Failed to load workflow content:', error);
        this.hideWorkflowsLoading();
        this.emit('notification', {
          message: 'Failed to load workflows',
          type: 'error'
        });
      }
    }
    
    // Load workflows from backend
    async loadWorkflows() {
      try {
        console.log('[SettingsManager] Loading workflows from backend...');
        console.log('[SettingsManager] API client base URL:', this.apiClient.baseURL);
        console.log('[SettingsManager] API client prefix:', this.apiClient.apiPrefix);
        
        const response = await this.apiClient.getWorkflows();
        console.log('[SettingsManager] Workflows response:', response);
        console.log('[SettingsManager] Response type:', typeof response);
        console.log('[SettingsManager] Response keys:', response ? Object.keys(response) : 'null response');
        
        // Handle different response structures
        let workflows = [];
        if (Array.isArray(response)) {
          workflows = response;
          console.log('[SettingsManager] Response is array, length:', workflows.length);
        } else if (response.flows && Array.isArray(response.flows)) {
          workflows = response.flows;
          console.log('[SettingsManager] Response has flows array, length:', workflows.length);
        } else if (response.data && Array.isArray(response.data)) {
          workflows = response.data;
          console.log('[SettingsManager] Response has data array, length:', workflows.length);
        } else {
          console.warn('[SettingsManager] Unexpected response structure:', response);
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
        
        console.log('[SettingsManager] Converted workflows:', this.state.workflows.length);
        console.log('[SettingsManager] First workflow sample:', this.state.workflows[0]);
        
        // Load schedule information for workflows
        await this.loadWorkflowSchedules();
        
        // Apply current search and filter
        this.filterWorkflows();
        
        console.log('[SettingsManager] Loaded workflows:', this.state.workflows.length);
        
      } catch (error) {
        console.error('[SettingsManager] Failed to load workflows:', error);
        console.error('[SettingsManager] Error details:', error.message);
        console.error('[SettingsManager] Error stack:', error.stack);
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
        console.log('[SettingsManager] Schedule API response:', response);
        
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
            console.warn('[SettingsManager] Unexpected schedule response format:', response);
          }
        }
        
        console.log('[SettingsManager] Processed schedules:', schedules);
        
        // Add schedule information to workflows
        if (Array.isArray(schedules) && schedules.length > 0) {
          this.state.workflows.forEach(workflow => {
            const schedule = schedules.find(s => s && s.flow_id === workflow.flow_id);
            workflow.scheduled = !!schedule;
            workflow.schedule = schedule;
          });
        } else {
          console.log('[SettingsManager] No schedules found or empty schedule array');
          // Set all workflows as unscheduled
          this.state.workflows.forEach(workflow => {
            workflow.scheduled = false;
            workflow.schedule = null;
          });
        }
        
      } catch (error) {
        console.error('[SettingsManager] Failed to load workflow schedules:', error);
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
    handleCreateWorkflow() {
      console.log('[SettingsManager] Create workflow button clicked');
      
      // Get backend URL from API client or settings
      const backendUrl = this.apiClient.baseURL || window.CONFIG?.BACKEND_URL || 'http://localhost:8000';
      const createUrl = `${backendUrl}/flows`;
      
      // Open in new tab using Chrome extension API
      if (typeof chrome !== 'undefined' && chrome.tabs) {
        chrome.tabs.create({ url: createUrl });
      } else {
        // Fallback for non-extension context
        window.open(createUrl, '_blank');
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
      console.log('[SettingsManager] Filtered workflows for rendering:', filtered.length);
      this.renderWorkflows();
    }
    
    // Render workflows list
    renderWorkflows() {
      console.log('[SettingsManager] renderWorkflows called');
      
      if (!this.elements.workflowsList) {
        console.error('[SettingsManager] workflowsList element not found!');
        return;
      }
      
      this.hideWorkflowsLoading();
      
      const workflows = this.state.filteredWorkflows;
      console.log('[SettingsManager] Rendering workflows:', workflows.length);
      
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
        console.error('[SettingsManager] Failed to copy flow ID:', error);
        this.emit('notification', {
          message: 'Failed to copy flow ID',
          type: 'error'
        });
      }
    }
    
    // Handle workflow run
    async handleWorkflowRun(workflowId) {
      try {
        console.log(`[SettingsManager] Running workflow ${workflowId}`);
        
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
        console.error('[SettingsManager] Failed to run workflow:', error);
        this.emit('notification', {
          message: `Failed to run workflow: ${error.message}`,
          type: 'error'
        });
      }
    }
    
    // Handle workflow pause
    async handleWorkflowPause(workflowId, jobId) {
      try {
        console.log(`[SettingsManager] Pausing workflow ${workflowId}, job ${jobId}`);
        
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
        console.error('[SettingsManager] Failed to pause workflow:', error);
        this.emit('notification', {
          message: `Failed to pause workflow: ${error.message}`,
          type: 'error'
        });
      }
    }
    
    // Unified event fetching with caching to prevent competition
    async fetchWorkflowEvents(jobId, options = {}) {
      const { forceRefresh = false, maxAge = 10000, preserveCache = true, workflowId = null } = options;
      
      console.log(`[SettingsManager] 🔄 FETCHING EVENTS for job ${jobId}`, {
        forceRefresh,
        maxAge,
        preserveCache,
        workflowId
      });
      
      // Check cache first
      const cached = this.state.eventCache.get(jobId);
      const now = Date.now();
      
      console.log(`[SettingsManager] Cache check:`, {
        exists: !!cached,
        isPersistent: cached?.isPersistent,
        isComplete: cached?.isComplete,
        eventCount: cached?.events?.length || 0,
        workflowId: cached?.workflowId,
        ageMs: cached ? now - cached.lastFetch : 'N/A'
      });
      
      // Persistent cache for completed workflows - NEVER refresh unless explicitly forced
      if (cached && cached.isPersistent && !forceRefresh) {
        console.log(`[SettingsManager] ✅ Using persistent cached events for completed job ${jobId}, count: ${cached.events.length}`);
        return cached.events;
      }
      
      // For completed workflows, always prefer cached events to prevent loss
      if (cached && cached.isComplete && cached.events.length > 0 && !forceRefresh) {
        console.log(`[SettingsManager] Using cached events for completed job ${jobId}, preventing loss of ${cached.events.length} events`);
        return cached.events;
      }
      
      if (cached && !forceRefresh && (now - cached.lastFetch) < maxAge) {
        console.log(`[SettingsManager] Using cached events for job ${jobId}, cache hit preventing duplicate API call`);
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
              console.warn(`[SettingsManager] Failed to parse event line: ${trimmedLine}`, e);
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
            console.log(`[SettingsManager] Preserving ${cached.events.length} cached events for job ${jobId} - API returned empty result`);
            finalEvents = cached.events;
            shouldUpdateCache = false; // Don't update cache with empty result
          } else if (events.length < cached.events.length && !hasEndEvent) {
            // API returned fewer events and workflow not complete - suspicious, preserve cache
            console.log(`[SettingsManager] Preserving ${cached.events.length} cached events for job ${jobId} - API returned fewer events (${events.length})`);
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
            console.log(`[SettingsManager] Marking job ${jobId} cache as persistent with ${finalEvents.length} events`);
            
            // Update workflow-to-job mapping for completed workflows
            if (cacheEntry.workflowId) {
              this.state.workflowJobMapping.set(cacheEntry.workflowId, {
                jobId: jobId,
                completedAt: now,
                eventCount: finalEvents.length
              });
              console.log(`[SettingsManager] Updated workflow mapping: ${cacheEntry.workflowId} -> ${jobId}`);
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
              console.error(`[SettingsManager] Error notifying event subscriber:`, e);
            }
          });
        }
        
        return finalEvents;
        
      } catch (error) {
        console.error(`[SettingsManager] Failed to fetch events for job ${jobId}:`, error);
        // Return cached events if available on error
        if (cached && cached.events.length > 0) {
          console.log(`[SettingsManager] Returning cached events due to API error for job ${jobId}`);
          return cached.events;
        }
        throw error;
      }
    }
    
    // Subscribe to event updates for a job
    subscribeToEvents(jobId, callback) {
      console.log(`[SettingsManager] subscribeToEvents called for job ${jobId}`);
      
      if (!this.state.eventSubscribers.has(jobId)) {
        this.state.eventSubscribers.set(jobId, new Set());
        console.log(`[SettingsManager] Created new subscriber set for job ${jobId}`);
      }
      this.state.eventSubscribers.get(jobId).add(callback);
      console.log(`[SettingsManager] Subscribed to events for job ${jobId}, total subscribers: ${this.state.eventSubscribers.get(jobId).size}`);
      
      // Return unsubscribe function
      return () => {
        console.log(`[SettingsManager] Unsubscribe function called for job ${jobId}`);
        const subscribers = this.state.eventSubscribers.get(jobId);
        if (subscribers) {
          subscribers.delete(callback);
          console.log(`[SettingsManager] Removed subscriber for job ${jobId}, remaining subscribers: ${subscribers.size}`);
          if (subscribers.size === 0) {
            this.state.eventSubscribers.delete(jobId);
            console.log(`[SettingsManager] Removed empty subscriber set for job ${jobId}`);
          }
        }
        console.log(`[SettingsManager] Unsubscribed from events for job ${jobId}`);
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
        console.log(`[SettingsManager] Stopped monitoring job ${jobId}`);
      };
      
      const checkStatus = async (events, isComplete) => {
        try {
          if (isComplete || !this.state.runningJobs.has(workflowId)) {
            // Workflow finished, remove from running jobs
            console.log(`[SettingsManager] ⚠️ WORKFLOW COMPLETION DETECTED: ${workflowId}, jobId: ${jobId}`);
            console.log(`[SettingsManager] Events received: ${events.length}, isComplete: ${isComplete}`);
            console.log(`[SettingsManager] RunningJobs before deletion:`, Array.from(this.state.runningJobs.keys()));
            
            this.state.runningJobs.delete(workflowId);
            console.log(`[SettingsManager] RunningJobs after deletion:`, Array.from(this.state.runningJobs.keys()));
            
            // Mark cache as persistent for completed workflows - NEVER allow overwriting
            const cached = this.state.eventCache.get(jobId);
            console.log(`[SettingsManager] Existing cache for job ${jobId}:`, {
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
                console.log(`[SettingsManager] Updated workflow mapping on completion: ${cached.workflowId} -> ${jobId}`);
              }
              
              console.log(`[SettingsManager] ✅ PERMANENTLY cached job ${jobId} with ${events.length} events - cache is now read-only`);
            } else {
              console.log(`[SettingsManager] ❌ FAILED to cache job ${jobId} - cached: ${!!cached}, events: ${events.length}`);
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
          console.error('[SettingsManager] Failed to check workflow status:', error);
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
          console.log(`[SettingsManager] Job ${jobId} cache is persistent, stopping monitoring`);
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
            console.log(`[SettingsManager] Job ${jobId} completed during fetch, stopping monitoring`);
            stopMonitoring();
            return;
          }
          
          // Schedule next fetch
          if (!monitoringStopped) {
            monitoringInterval = setTimeout(fetchEvents, 7000);
          }
        } catch (error) {
          console.error(`[SettingsManager] Failed to fetch events for job ${jobId}:`, error);
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
      console.log(`[SettingsManager] 📋 OPENING LOGS: workflowId=${workflowId}, jobId=${jobId}`);
      
      const workflow = this.state.workflows.find(w => w.flow_id === workflowId);
      if (!workflow) {
        console.log(`[SettingsManager] ❌ Workflow not found: ${workflowId}`);
        return;
      }
      
      console.log(`[SettingsManager] Found workflow: ${workflow.name}`);
      console.log(`[SettingsManager] Is workflow running?`, this.state.runningJobs.has(workflowId));
      
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
          console.log(`[SettingsManager] Found mapped jobId for workflow ${workflowId}: ${effectiveJobId}`);
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
            
            console.log(`[SettingsManager] No mapping found, using most recent cached job for workflow ${workflowId}: ${effectiveJobId}`);
            this.state.currentLogsJobId = effectiveJobId;
          } else {
            console.log(`[SettingsManager] No cached logs found for workflow ${workflowId}`);
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
        
        console.log(`[SettingsManager] Loading logs for job ${jobId}`);
        console.log(`[SettingsManager] Current workflow:`, this.state.currentLogsWorkflow?.name);
        console.log(`[SettingsManager] Running jobs:`, Array.from(this.state.runningJobs.keys()));
        
        // First, ALWAYS check persistent cache - this is the key fix
        let events = [];
        const cached = this.state.eventCache.get(jobId);
        
        console.log(`[SettingsManager] Cache status for job ${jobId}:`, {
          exists: !!cached,
          isPersistent: cached?.isPersistent,
          isComplete: cached?.isComplete,
          eventCount: cached?.events?.length || 0,
          lastFetch: cached?.lastFetch ? new Date(cached.lastFetch).toLocaleTimeString() : 'never'
        });
        
        // Prioritize persistent cached events (completed workflows)
        if (cached && cached.isPersistent && cached.events.length > 0) {
          console.log(`[SettingsManager] Using PERSISTENT cached events for completed job ${jobId}, count: ${cached.events.length}`);
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
          console.log(`[SettingsManager] Using cached events for job ${jobId}, count: ${cached.events.length}`);
          events = cached.events;
          
          // Render cached events immediately for better UX
          this.renderWorkflowLogs(events);
          
          // Check if this is a completed workflow that should be marked as persistent
          if (cached.isComplete && !cached.isPersistent) {
            console.log(`[SettingsManager] Marking completed job ${jobId} as persistent to prevent future overwrites`);
            this.state.eventCache.set(jobId, {
              ...cached,
              isPersistent: true,
              completedAt: cached.completedAt || Date.now()
            });
          }
          
          // Only fetch fresh events for running jobs (don't fetch for completed jobs)
          if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id) && !cached.isComplete && !cached.isPersistent) {
            console.log(`[SettingsManager] Job still running, fetching fresh events in background`);
            this.fetchWorkflowEvents(jobId, { preserveCache: true, maxAge: 2000 }).then(freshEvents => {
              if (freshEvents.length > events.length) {
                console.log(`[SettingsManager] Fresh events available, updating logs: ${freshEvents.length} events`);
                this.renderWorkflowLogs(freshEvents);
              }
            }).catch(error => {
              console.warn(`[SettingsManager] Background event fetch failed for job ${jobId}:`, error);
            });
          } else if (cached.isComplete || cached.isPersistent) {
            console.log(`[SettingsManager] Using completed workflow logs from cache, no fresh fetch needed`);
            // Update job info display to show completion status
            if (this.elements.logsJobId) {
              this.elements.logsJobId.textContent = `${jobId} (Completed)`;
            }
          }
        } else {
          console.log(`[SettingsManager] No cached events, fetching fresh for job ${jobId}`);
          // Only fetch fresh if no cache exists - but preserve any existing cache
          // Pass workflow context for proper association
          events = await this.fetchWorkflowEvents(jobId, {
            forceRefresh: false,
            preserveCache: true,
            workflowId: this.state.currentLogsWorkflow?.flow_id
          });
          console.log(`[SettingsManager] Fetched ${events.length} fresh events for job ${jobId}`);
          this.renderWorkflowLogs(events);
        }
        
        // Set up real-time updates ONLY if job is still running
        if (this.state.runningJobs.has(this.state.currentLogsWorkflow?.flow_id)) {
          console.log(`[SettingsManager] Job is still running, setting up real-time log updates`);
          
          let unsubscribe;
          const updateLogs = (newEvents, isComplete) => {
            console.log(`[SettingsManager] Real-time log update with ${newEvents.length} events, complete: ${isComplete}`);
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
              console.log(`[SettingsManager] Cleaning up log subscription for job ${jobId}`);
              unsubscribe();
            }
            // Restore original method
            this.hideLogsModal = originalHideLogsModal;
            originalHideLogsModal();
          };
        } else {
          console.log(`[SettingsManager] Job not running, no real-time updates needed for job ${jobId}`);
        }
        
      } catch (error) {
        console.error('[SettingsManager] Failed to load workflow logs:', error);
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
      
      console.log(`[SettingsManager] Rendering logs with ${events.length} events`);
      
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
      
      console.log(`[SettingsManager] Rendered ${events.length} enhanced log entries`);
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
        console.log(`[SettingsManager] Refreshing logs for job ${this.state.currentLogsJobId}`);
        try {
          // Force refresh to get latest events, but preserve cache if API returns empty
          const events = await this.fetchWorkflowEvents(this.state.currentLogsJobId, {
            forceRefresh: true,
            preserveCache: true
          });
          console.log(`[SettingsManager] Refreshed logs with ${events.length} events`);
          if (events.length > 0) {
            this.renderWorkflowLogs(events);
          } else {
            this.emit('notification', {
              message: 'No new log events available',
              type: 'info'
            });
          }
        } catch (error) {
          console.error('[SettingsManager] Failed to refresh logs:', error);
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
      
      console.log('[SettingsManager] Schedule type changed to:', scheduleType);
      
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
      console.log('[SettingsManager] Updating UI for schedule type:', scheduleType);
      
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

    // Handle natural language input
    async handleNaturalLanguageInput() {
      const naturalInput = document.getElementById('natural-schedule-input');
      if (!naturalInput) return;
      
      const text = naturalInput.value.trim();
      if (!text) return;
      
      // Simple natural language parsing (can be enhanced with a proper NLP library)
      const cronExpression = this.parseNaturalLanguageToCron(text);
      
      if (cronExpression) {
        this.scheduleState.cronExpression = cronExpression;
        this.validateAndPreviewSchedule();
      }
    }

    // Parse natural language to cron expression
    parseNaturalLanguageToCron(text) {
      const lowerText = text.toLowerCase();
      
      // Common patterns
      if (lowerText.includes('every day') || lowerText.includes('daily')) {
        if (lowerText.includes('at')) {
          const timeMatch = lowerText.match(/at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?/);
          if (timeMatch) {
            let hour = parseInt(timeMatch[1]);
            const minute = timeMatch[2] ? parseInt(timeMatch[2]) : 0;
            const ampm = timeMatch[3];
            
            if (ampm === 'pm' && hour !== 12) hour += 12;
            if (ampm === 'am' && hour === 12) hour = 0;
            
            return `${minute} ${hour} * * *`;
          }
        }
        return '0 0 * * *'; // Default to midnight
      }
      
      if (lowerText.includes('every weekday') || lowerText.includes('monday to friday')) {
        if (lowerText.includes('at')) {
          const timeMatch = lowerText.match(/at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?/);
          if (timeMatch) {
            let hour = parseInt(timeMatch[1]);
            const minute = timeMatch[2] ? parseInt(timeMatch[2]) : 0;
            const ampm = timeMatch[3];
            
            if (ampm === 'pm' && hour !== 12) hour += 12;
            if (ampm === 'am' && hour === 12) hour = 0;
            
            return `${minute} ${hour} * * 1-5`;
          }
        }
        return '0 9 * * 1-5'; // Default to 9 AM weekdays
      }
      
      if (lowerText.includes('every week') || lowerText.includes('weekly')) {
        return '0 0 * * 0'; // Sunday at midnight
      }
      
      if (lowerText.includes('every month') || lowerText.includes('monthly')) {
        return '0 0 1 * *'; // 1st of month at midnight
      }
      
      return null;
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
        console.warn('[SettingsManager] Cron expression validation failed:', error);
        return false;
      }
    }

    // Generate schedule preview
    generateSchedulePreview(cronExpression, count = 5) {
      const previewTimes = [];
      
      try {
        if (typeof cronParser !== 'undefined') {
          // Use professional cron-parser library
          const interval = cronParser.parseExpression(cronExpression);
          
          for (let i = 0; i < count; i++) {
            try {
              const nextDate = interval.next();
              if (nextDate) {
                previewTimes.push(new Date(nextDate.toString()));
              }
            } catch (e) {
              break; // No more occurrences
            }
          }
        } else {
          // Fallback to basic preview generation
          const now = new Date();
          
          if (cronExpression.includes('* * * * *')) {
            // Every minute
            for (let i = 1; i <= count; i++) {
              const nextTime = new Date(now.getTime() + i * 60000);
              previewTimes.push(nextTime);
            }
          } else if (cronExpression.includes('0 * * * *')) {
            // Every hour
            for (let i = 1; i <= count; i++) {
              const nextTime = new Date(now.getTime() + i * 3600000);
              nextTime.setMinutes(0, 0, 0);
              previewTimes.push(nextTime);
            }
          } else if (cronExpression.includes('0 0 * * *')) {
            // Daily at midnight
            for (let i = 1; i <= count; i++) {
              const nextTime = new Date(now);
              nextTime.setDate(nextTime.getDate() + i);
              nextTime.setHours(0, 0, 0, 0);
              previewTimes.push(nextTime);
            }
          } else {
            // Default to some reasonable future times
            for (let i = 1; i <= count; i++) {
              const nextTime = new Date(now.getTime() + i * 86400000); // Add days
              previewTimes.push(nextTime);
            }
          }
        }
      } catch (error) {
        console.warn('[SettingsManager] Failed to generate schedule preview:', error);
        // Return empty array on error
        return [];
      }
      
      return previewTimes;
    }


    // Update schedule save button
    updateScheduleSaveButton(isValid) {
      const saveButton = document.getElementById('schedule-save');
      if (!saveButton) return;
      
      const enabledCheckbox = document.getElementById('schedule-enabled');
      const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;
      
      saveButton.disabled = !isValid || !isEnabled;
    }

    // Set schedule type
    setScheduleType(type) {
      const radio = document.querySelector(`input[name="schedule-type"][value="${type}"]`);
      if (radio) {
        radio.checked = true;
        this.handleScheduleTypeChange(type);
      }
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

    // Find matching template for cron expression
    findMatchingTemplate(cronExpression) {
      const templates = this.elements.workflowScheduleModal.querySelectorAll('.schedule-template-btn');
      for (let template of templates) {
        if (template.dataset.cron === cronExpression) {
          return template;
        }
      }
      return null;
    }
    
    // Hide schedule modal
    hideScheduleModal() {
      if (this.elements.workflowScheduleModal) {
        this.elements.workflowScheduleModal.classList.add('hidden');
      }
      this.state.currentScheduleWorkflow = null;
    }
    
    
    // Handle schedule preview update
    
    // Handle schedule save
    async handleScheduleSave() {
      if (!this.state.currentScheduleWorkflow) return;
      
      try {
        const workflowId = this.state.currentScheduleWorkflow.flow_id;
        const enabledCheckbox = document.getElementById('schedule-enabled');
        const isEnabled = enabledCheckbox ? enabledCheckbox.checked : true;
        
        // If schedule is disabled, remove it
        if (!isEnabled && this.state.currentScheduleWorkflow.schedule) {
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
        console.error('[SettingsManager] Failed to save schedule:', error);
        this.emit('notification', {
          message: `Failed to save schedule: ${error.message}`,
          type: 'error'
        });
      }
    }
    
    // Handle workflow edit
    handleWorkflowEdit(workflowId) {
      console.log(`[SettingsManager] Edit workflow ${workflowId}`);
      
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
        console.error('[SettingsManager] Failed to delete workflow:', error);
        this.emit('notification', {
          message: `Failed to delete workflow: ${error.message}`,
          type: 'error'
        });
      }
    }
  }

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSettingsManager = VibeSurfSettingsManager;
}