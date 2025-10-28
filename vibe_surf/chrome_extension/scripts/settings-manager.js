// Settings Manager - Handles settings UI coordination and delegates to specialized modules
// Manages coordination between general settings, profiles, integrations, and workflow

class VibeSurfSettingsManager {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.state = {
      // State is now managed by individual modules
    };
    this.elements = {};
    this.eventListeners = new Map();
    
    // Initialize user settings storage
    this.userSettingsStorage = new VibeSurfUserSettingsStorage();
    
    // Initialize specialized managers
    this.settingsGeneral = new VibeSurfSettingsGeneral(this.apiClient, this.userSettingsStorage, this.emit.bind(this));
    this.settingsProfiles = new VibeSurfSettingsProfiles(this.apiClient, this.emit.bind(this));
    this.settingsIntegrations = new VibeSurfSettingsIntegrations(this.apiClient, this.emit.bind(this));
    this.settingsWorkflow = new VibeSurfSettingsWorkflow(this.apiClient, this.emit.bind(this), this.userSettingsStorage);
    
    this.bindElements();
    this.bindEvents();
    this.initializeUserSettings();
  }

  bindElements() {
    this.elements = {
      // Settings Modal
      settingsModal: document.getElementById('settings-modal'),
      settingsTabs: document.querySelectorAll('.settings-tab'),
      settingsTabContents: document.querySelectorAll('.settings-tab-content')
    };
    
    // Delegate element binding to specialized managers
    this.settingsGeneral.bindElements();
    this.settingsProfiles.bindElements();
    // Integrations and workflow managers handle their own elements
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
    
    // Delegate event binding to specialized managers
    this.settingsGeneral.bindEvents();
    this.settingsProfiles.bindEvents();
    
    // Workflow events are now handled by VibeSurfSettingsWorkflow
    if (this.settingsWorkflow) {
      this.settingsWorkflow.bindEvents();
    }
    
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

  // Handle individual setting changes from storage - delegate to general settings
  handleStorageSettingChanged(data) {
    this.settingsGeneral.handleStorageSettingChanged(data);
  }

  // Handle bulk settings changes from storage - delegate to general settings
  handleStorageSettingsChanged(allSettings) {
    this.settingsGeneral.handleStorageSettingsChanged(allSettings);
  }

  handleKeydown(event) {
    // Close settings modal on Escape key
    if (event.key === 'Escape') {
      if (this.elements.settingsModal && !this.elements.settingsModal.classList.contains('hidden')) {
        this.hideModal();
      }
      // Close profile form modal on Escape key
      if (this.settingsProfiles.elements.profileFormModal && !this.settingsProfiles.elements.profileFormModal.classList.contains('hidden')) {
        this.settingsProfiles.closeProfileForm();
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
      this.settingsGeneral.loadEnvironmentVariables();
    }
    
    // If switching to integrations tab, load integrations data
    if (targetTabId === 'integrations') {
      if (this.settingsIntegrations) {
        this.settingsIntegrations.loadIntegrationsData();
      }
    }
    
    // If switching to workflow tab, load workflow content
    if (targetTabId === 'workflow') {
      if (this.settingsWorkflow) {
        this.settingsWorkflow.loadWorkflowContent();
      }
    }
  }

  // Data Loading - delegate to specialized managers
  async loadSettingsData() {
    try {
      // Load profiles data
      await this.settingsProfiles.loadAllProfiles();
      
      // Load general settings
      await this.settingsGeneral.loadGeneralSettings();
      
      // Load voice profiles for general settings dropdowns
      await this.settingsGeneral.loadVoiceProfilesForGeneral();
      
      // Load environment variables
      await this.settingsGeneral.loadEnvironmentVariables();
      
      // Emit event to update LLM profile select dropdown
      // This should happen AFTER all data is loaded but BEFORE user selections are restored
      this.emit('profilesUpdated', {
        llmProfiles: this.settingsProfiles.getLLMProfiles(),
        mcpProfiles: this.settingsProfiles.getMCPProfiles(),
        voiceProfiles: this.settingsProfiles.getVoiceProfiles()
      });
      
    } catch (error) {
      console.error('[SettingsManager] Failed to load settings data:', error);
      this.emit('error', { message: 'Failed to load settings data', error });
    }
  }

  // Delegate profile management to profiles module
  async handleAddProfile(type) {
    return this.settingsProfiles.handleAddProfile(type);
  }

  async showProfileForm(type, profile = null) {
    return this.settingsProfiles.showProfileForm(type, profile);
  }

  closeProfileForm() {
    return this.settingsProfiles.closeProfileForm();
  }

  // Delegate profile deletion to profiles module
  async handleDeleteProfile(type, profileId) {
    return this.settingsProfiles.handleDeleteProfile(type, profileId);
  }

  // Public interface - delegate to modules
  getState() {
    return {
      llmProfiles: this.settingsProfiles.getLLMProfiles(),
      mcpProfiles: this.settingsProfiles.getMCPProfiles(),
      voiceProfiles: this.settingsProfiles.getVoiceProfiles()
    };
  }

  getLLMProfiles() {
    return this.settingsProfiles.getLLMProfiles();
  }

  getMCPProfiles() {
    return this.settingsProfiles.getMCPProfiles();
  }

  getVoiceProfiles() {
    return this.settingsProfiles.getVoiceProfiles();
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
    this.settingsGeneral.updateBackendUrl(url);
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
      // Delegate to profiles module
      await this.settingsProfiles.navigateToLLMProfile(profileName);
    }, 100);
  }
  }

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSettingsManager = VibeSurfSettingsManager;
}