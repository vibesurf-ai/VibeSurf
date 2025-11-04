// Settings Integrations Manager - Handles Composio integrations functionality
// Manages API key setup, toolkits, and tools configuration

class VibeSurfSettingsIntegrations {
  constructor(apiClient, eventEmitter) {
    this.apiClient = apiClient;
    this.eventEmitter = eventEmitter;
    
    this.state = {
      // Integrations state
      composioApiKey: null,
      composioKeyValid: false,
      toolkits: [],
      filteredToolkits: [],
      currentToolkit: null,
      searchQuery: '',
      filterStatus: 'all'
    };
    
    this.elements = {};
    this.bindElements();
    this.bindEvents();
  }

  bindElements() {
    this.elements = {
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
      oauthCompleted: document.getElementById('oauth-completed')
    };
  }

  bindEvents() {
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
  }

  // Emit events through the event emitter
  emit(event, data) {
    this.eventEmitter(event, data);
  }

  // Utility method for escaping HTML
  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // === INTEGRATIONS FUNCTIONALITY ===
  
  // Load integrations data when tab is opened
  async loadIntegrationsData() {
    try {
      console.log('[SettingsIntegrations] Loading integrations data...');
      console.log('[SettingsIntegrations] API client available:', !!this.apiClient);
      
      // Show loading state immediately
      this.showIntegrationsLoading();
      
      // Check Composio status (which will handle instance restoration if needed)
      const status = await this.checkComposioStatus();
      
      console.log('[SettingsIntegrations] Status check result:', status);
      
      if (status && status.connected && status.key_valid) {
        console.log('[SettingsIntegrations] Valid Composio connection found, loading toolkits from database...');
        // Load toolkits from database (no sync by default for faster loading)
        await this.loadToolkits(false);
        console.log('[SettingsIntegrations] Toolkits loaded, showing integrations content...');
        this.showIntegrationsContent();
        console.log('[SettingsIntegrations] Integrations content shown');
      } else {
        console.log('[SettingsIntegrations] No valid Composio connection, showing setup modal automatically');
        console.log('[SettingsIntegrations] Status details - connected:', status?.connected, 'key_valid:', status?.key_valid);
        // Automatically show setup modal instead of setup UI
        this.hideIntegrationsLoading();
        this.showApiKeyModal();
      }
    } catch (error) {
      console.error('[SettingsIntegrations] Failed to load integrations data:', error);
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
      console.log('[SettingsIntegrations] Checking Composio status...');
      const response = await this.apiClient.getComposioStatus();
      console.log('[SettingsIntegrations] Composio status response:', response);
      
      // Use the new response format
      this.state.composioKeyValid = response.connected && response.key_valid;
      this.state.composioApiKey = response.has_key ? '***' : null;
      
      console.log('[SettingsIntegrations] Composio state updated:', {
        connected: response.connected,
        keyValid: response.key_valid,
        hasKey: response.has_key,
        instanceAvailable: response.instance_available,
        message: response.message
      });
      
      return response;
    } catch (error) {
      console.error('[SettingsIntegrations] Failed to check Composio status:', error);
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
    console.log('[SettingsIntegrations] showIntegrationsContent called');
    console.log('[SettingsIntegrations] composioStatus element exists:', !!this.elements.composioStatus);
    console.log('[SettingsIntegrations] toolkitsSection element exists:', !!this.elements.toolkitsSection);
    
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
      console.log('[SettingsIntegrations] toolkitsSection display set to block and hidden class removed');
    } else {
      console.error('[SettingsIntegrations] toolkitsSection element not found!');
    }
  }

  // Handle API key setup button click
  handleSetupApiKey() {
    console.log('[SettingsIntegrations] Setup API key button clicked');
    this.showApiKeyModal();
  }

  // Show API key modal
  showApiKeyModal() {
    console.log('[SettingsIntegrations] Showing API key modal');
    console.log('[SettingsIntegrations] Modal element exists:', !!this.elements.composioApiKeyModal);
    
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
      
      console.log('[SettingsIntegrations] API key modal shown successfully');
    } else {
      console.error('[SettingsIntegrations] API key modal element not found!');
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
      console.error('[SettingsIntegrations] Failed to verify API key:', error);
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
      console.log('[SettingsIntegrations] Loading Composio toolkits...');
      
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
      
      console.log('[SettingsIntegrations] Loaded toolkits:', this.state.toolkits.length);
      console.log('[SettingsIntegrations] Filtered toolkits:', this.state.filteredToolkits.length);
      
      if (forceSync && response.synced_count > 0) {
        this.emit('notification', {
          message: `Synced ${response.synced_count} new toolkits from Composio`,
          type: 'success'
        });
      }
      
    } catch (error) {
      console.error('[SettingsIntegrations] Failed to load toolkits:', error);
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
    console.log('[SettingsIntegrations] Filtered toolkits for rendering:', filtered.length);
    this.renderToolkits();
  }

  // Render toolkits list
  renderToolkits() {
    console.log('[SettingsIntegrations] renderToolkits called');
    console.log('[SettingsIntegrations] toolkitsList element exists:', !!this.elements.toolkitsList);
    
    if (!this.elements.toolkitsList) {
      console.error('[SettingsIntegrations] toolkitsList element not found!');
      return;
    }
    
    const toolkits = this.state.filteredToolkits;
    console.log('[SettingsIntegrations] Rendering toolkits:', toolkits.length);
    
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

    console.log('[SettingsIntegrations] Setting toolkits HTML, length:', toolkitsHTML.length);
    this.elements.toolkitsList.innerHTML = toolkitsHTML;
    console.log('[SettingsIntegrations] HTML set successfully');
    
    // Bind event listeners for toolkit interactions
    this.bindToolkitEvents();
    console.log('[SettingsIntegrations] Event binding completed');
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
      console.log(`[SettingsIntegrations] Toggling toolkit ${toolkitSlug}: ${isEnabled}`);
      
      const response = await this.apiClient.toggleComposioToolkit(toolkitSlug, isEnabled);
      
      if (response.requires_oauth && !response.connected) {
        // OAuth flow required
        console.log(`[SettingsIntegrations] OAuth required for ${toolkitSlug}, URL:`, response.oauth_url);
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
      console.error('[SettingsIntegrations] Failed to toggle toolkit:', error);
      
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
      console.log(`[SettingsIntegrations] Starting OAuth flow for ${toolkitSlug}`);
      
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
      console.error('[SettingsIntegrations] Failed to handle OAuth flow:', error);
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
      console.log(`[SettingsIntegrations] Checking OAuth completion for ${this.state.currentToolkit}`);
      
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
      console.error('[SettingsIntegrations] Failed to check OAuth completion:', error);
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
      console.error('[SettingsIntegrations] Failed to manage tools:', error);
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
      console.error('[SettingsIntegrations] Failed to load toolkit tools:', error);
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
      console.error('[SettingsIntegrations] No current toolkit selected for save');
      return;
    }

    try {
      console.log(`[SettingsIntegrations] Saving tools for ${this.state.currentToolkit}`);
      
      // Get all tools with their selection status as dictionary
      const toolCheckboxes = this.elements.toolsList?.querySelectorAll('.tool-checkbox-input');
      const selectedTools = {};
      
      if (toolCheckboxes) {
        console.log(`[SettingsIntegrations] Found ${toolCheckboxes.length} tool checkboxes`);
        toolCheckboxes.forEach(checkbox => {
          const toolName = checkbox.dataset.toolName;
          const isSelected = checkbox.checked;
          selectedTools[toolName] = isSelected;
          console.log(`[SettingsIntegrations] Tool ${toolName}: ${isSelected ? 'selected' : 'not selected'}`);
        });
      } else {
        console.warn('[SettingsIntegrations] No tool checkboxes found');
      }
      
      console.log(`[SettingsIntegrations] Selected tools:`, selectedTools);
      
      // Save tools selection
      const response = await this.apiClient.updateComposioToolkitTools(this.state.currentToolkit, selectedTools);
      console.log(`[SettingsIntegrations] Save response:`, response);
      
      this.emit('notification', {
        message: 'Tools configuration saved successfully',
        type: 'success'
      });
      
      // Close modal
      this.hideToolsModal();
      
    } catch (error) {
      console.error('[SettingsIntegrations] Failed to save tools:', error);
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
          console.error(`[SettingsIntegrations] Failed to check connection status for ${toolkit.slug}:`, error);
          // Keep as disconnected on error
          return { slug: toolkit.slug, connected: false, status: 'error' };
        }
      });
      
      const results = await Promise.all(connectionPromises);
      console.log('[SettingsIntegrations] Connection status check results:', results);
      
    } catch (error) {
      console.error('[SettingsIntegrations] Failed to update toolkit connection statuses:', error);
    }
  }

  // Get current state
  getState() {
    return { ...this.state };
  }
}

// Export for use in other modules
VibeSurfSettingsIntegrations.exportToWindow = function() {
  if (typeof window !== 'undefined') {
    window.VibeSurfSettingsIntegrations = VibeSurfSettingsIntegrations;
  }
};

// Call the export method
VibeSurfSettingsIntegrations.exportToWindow();