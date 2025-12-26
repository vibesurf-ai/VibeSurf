
// Settings Profiles Manager - Handles LLM, MCP, and Voice profile management
// Extracted from VibeSurfSettingsManager to improve code organization

class VibeSurfSettingsProfiles {
  constructor(apiClient, emit) {
    this.apiClient = apiClient;
    this.emit = emit;
    this.state = {
      llmProfiles: [],
      mcpProfiles: [],
      voiceProfiles: [],
      currentProfileForm: null
    };
    this.elements = {};
  }

  // Bind DOM elements related to profiles
  bindElements() {
    this.elements = {
      // LLM Profiles
      llmProfilesContainer: document.getElementById('llm-profiles-container'),
      addLlmProfileBtn: document.getElementById('add-llm-profile-btn'),
      
      // MCP Profiles
      mcpProfilesContainer: document.getElementById('mcp-profiles-container'),
      addMcpProfileBtn: document.getElementById('add-mcp-profile-btn'),
      
      // Voice Profiles
      voiceProfilesContainer: document.getElementById('voice-profiles-container'),
      addVoiceProfileBtn: document.getElementById('add-voice-profile-btn'),
      
      // Profile Form Modal
      profileFormModal: document.getElementById('profile-form-modal'),
      profileFormTitle: document.getElementById('profile-form-title'),
      profileForm: document.getElementById('profile-form'),
      profileFormCancel: document.getElementById('profile-form-cancel'),
      profileFormSubmit: document.getElementById('profile-form-submit'),
      profileFormClose: document.querySelector('.profile-form-close')
    };
  }

  // Bind events for profiles
  bindEvents() {
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
  }

  // Load all profile types
  async loadAllProfiles() {
    try {
      // Load LLM profiles
      await this.loadLLMProfiles();
      
      // Load MCP profiles
      await this.loadMCPProfiles();
      
      // Load Voice profiles
      await this.loadVoiceProfiles();
      
    } catch (error) {
      console.error('[SettingsProfiles] Failed to load profiles:', error);
      throw error;
    }
  }

  async loadLLMProfiles() {
    try {
      const response = await this.apiClient.getLLMProfiles(false); // Load all profiles, not just active
      console.log('[SettingsProfiles] LLM profiles loaded:', response);
      
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
      console.error('[SettingsProfiles] Failed to load LLM profiles:', error);
      this.state.llmProfiles = [];
      this.renderLLMProfiles([]);
    }
  }

  async loadMCPProfiles() {
    try {
      const response = await this.apiClient.getMCPProfiles(false); // Load all profiles, not just active
      console.log('[SettingsProfiles] MCP profiles loaded:', response);
      
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
      console.error('[SettingsProfiles] Failed to load MCP profiles:', error);
      this.state.mcpProfiles = [];
      this.renderMCPProfiles([]);
    }
  }

  async loadVoiceProfiles() {
    try {
      const response = await this.apiClient.getVoiceProfiles(false); // Load all profiles, not just active
      console.log('[SettingsProfiles] Voice profiles loaded:', response);
      
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
      console.error('[SettingsProfiles] Failed to load Voice profiles:', error);
      this.state.voiceProfiles = [];
      this.renderVoiceProfiles([]);
    }
  }

  // Profile Management
  async handleAddProfile(type) {
    try {
      this.showProfileForm(type);
    } catch (error) {
      console.error(`[SettingsProfiles] Failed to show ${type} profile form:`, error);
      this.emit('error', { message: `${window.i18n.getMessage('failedToShow')}${type} ${window.i18n.getMessage('profileForm')}` });
    }
  }

  async showProfileForm(type, profile = null) {
    const isEdit = profile !== null;
    const title = isEdit ? `${window.i18n.getMessage('edit')} ${type.toUpperCase()}` : `${window.i18n.getMessage('add')} ${type.toUpperCase()}`;
    
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
      console.error('[SettingsProfiles] Failed to fetch LLM providers:', error);
    }
    
    const providersOptions = providers.map(p =>
      `<option value="${p.name}" ${profile?.provider === p.name ? 'selected' : ''}>${p.display_name}</option>`
    ).join('');
    
    const selectedProvider = profile?.provider || (providers.length > 0 ? providers[0].name : '');
    const selectedProviderData = providers.find(p => p.name === selectedProvider);
    const models = selectedProviderData?.models || [];
    
    return `
      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('profileName')}</label>
        <input type="text" name="profile_name" class="form-input" value="${profile?.profile_name || ''}"
               placeholder="${window.i18n.getMessage('enterUniqueName')}" required ${profile ? 'readonly' : ''}>
        <div class="form-help">${window.i18n.getMessage('uniqueIdentifierConfig')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('provider')}</label>
        <select name="provider" class="form-select" required>
          <option value="">${window.i18n.getMessage('selectProvider')}</option>
          ${providersOptions}
        </select>
        <div class="form-help">${window.i18n.getMessage('chooseLLMProvider')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('model')}</label>
        <input type="text" name="model" class="form-input model-input" value="${profile?.model || ''}"
               list="model-options" placeholder="${window.i18n.getMessage('selectModelOrCustom')}" required
               autocomplete="off">
        <datalist id="model-options">
          ${models.map(model => `<option value="${model}">${model}</option>`).join('')}
        </datalist>
        <div class="form-help">${window.i18n.getMessage('chooseFromListOrCustom')}</div>
      </div>

      <div class="form-group api-key-field">
        <label class="form-label required">${window.i18n.getMessage('apiKey')}</label>
        <input type="password" name="api_key" class="form-input api-key-input"
               placeholder="${profile ? window.i18n.getMessage('leaveEmptyKeepKey') : window.i18n.getMessage('enterYourApiKey')}"
               ${profile ? '' : 'required'}>
        <button type="button" class="api-key-toggle" title="${window.i18n.getMessage('toggleVisibility')}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/>
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
          </svg>
        </button>
        <div class="form-help">${window.i18n.getMessage('providerApiKeyAuth')}</div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('baseUrl')}</label>
        <input type="url" name="base_url" class="form-input" value="${profile?.base_url || ''}"
               placeholder="https://api.openai.com/v1">
        <div class="form-help">${window.i18n.getMessage('customApiEndpoint')}</div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('temperature')}</label>
        <input type="number" name="temperature" class="form-input" value="${profile?.temperature || ''}"
               min="0" max="2" step="0.1" placeholder="0.7">
        <div class="form-help">${window.i18n.getMessage('temperatureHelp')}</div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('maxTokens')}</label>
        <input type="number" name="max_tokens" class="form-input" value="${profile?.max_tokens || ''}"
               min="1" max="128000" placeholder="4096">
        <div class="form-help">${window.i18n.getMessage('maxTokensHelp')}</div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('description')}</label>
        <textarea name="description" class="form-textarea" placeholder="${window.i18n.getMessage('optionalDescription')}">${profile?.description || ''}</textarea>
        <div class="form-help">${window.i18n.getMessage('optionalDescriptionHelp')}</div>
      </div>

      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_default" ${profile?.is_default ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">${window.i18n.getMessage('setAsDefaultProfile')}</span>
        </label>
        <div class="form-help">${window.i18n.getMessage('defaultProfileHelp')}</div>
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
      console.error('[SettingsProfiles] Failed to fetch voice models:', error);
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
        console.warn('[SettingsProfiles] Failed to stringify existing voice_meta_params:', error);
      }
    }
    
    return `
      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('profileName')}</label>
        <input type="text" name="voice_profile_name" class="form-input" value="${profile?.voice_profile_name || ''}"
               placeholder="${window.i18n.getMessage('enterUniqueName')}" required ${profile ? 'readonly' : ''}>
        <div class="form-help">${window.i18n.getMessage('uniqueIdentifierConfig').replace('LLM', 'voice')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('modelType')}</label>
        <select name="voice_model_type" class="form-select" required>
          <option value="asr" ${selectedModelType === 'asr' ? 'selected' : ''}>ASR (Speech Recognition)</option>
          <option value="tts" ${selectedModelType === 'tts' ? 'selected' : ''}>TTS (Text to Speech)</option>
        </select>
        <div class="form-help">${window.i18n.getMessage('chooseVoiceModelType')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('voiceModel')}</label>
        <select name="voice_model_name" class="form-select voice-model-select" required>
          <option value="">${window.i18n.getMessage('selectModel')}</option>
          ${modelsOptions}
        </select>
        <div class="form-help">${window.i18n.getMessage('chooseYourVoiceModel')}</div>
      </div>

      <div class="form-group api-key-field">
        <label class="form-label required">${window.i18n.getMessage('apiKey')}</label>
        <input type="password" name="api_key" class="form-input api-key-input"
               placeholder="${profile ? window.i18n.getMessage('leaveEmptyKeepKey') : window.i18n.getMessage('enterYourApiKey')}"
               ${profile ? '' : 'required'}>
        <button type="button" class="api-key-toggle" title="${window.i18n.getMessage('toggleVisibility')}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/>
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
          </svg>
        </button>
        <div class="form-help">${window.i18n.getMessage('voiceProviderApiKeyAuth')}</div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('modelParameters')}</label>
        <textarea name="voice_meta_params_json" class="form-textarea json-input" rows="4"
                  placeholder="${window.i18n.getMessage('enterJsonModelParams')}">${defaultMetaJson}</textarea>
        <div class="json-validation-feedback"></div>
        <div class="form-help">
          ${window.i18n.getMessage('modelParametersHelp')}
          <br><code>{"language": "zh", "sample_rate": 16000}</code>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('description')}</label>
        <textarea name="description" class="form-textarea" placeholder="${window.i18n.getMessage('optionalDescription')}">${profile?.description || ''}</textarea>
        <div class="form-help">${window.i18n.getMessage('optionalDescriptionHelp')}</div>
      </div>

      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_active" ${profile?.is_active !== false ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">${window.i18n.getMessage('active')}</span>
        </label>
        <div class="form-help">${window.i18n.getMessage('activeProfileHelp')}</div>
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
        console.warn('[SettingsProfiles] Failed to stringify existing mcp_server_params:', error);
      }
    }
    
    return `
      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('displayName')}</label>
        <input type="text" name="display_name" class="form-input" value="${profile?.display_name || ''}"
               placeholder="${window.i18n.getMessage('enterFriendlyName')}" required ${profile ? 'readonly' : ''}>
        <div class="form-help">${window.i18n.getMessage('userFriendlyNameMcp')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('serverName')}</label>
        <input type="text" name="mcp_server_name" class="form-input" value="${profile?.mcp_server_name || ''}"
               placeholder="${window.i18n.getMessage('serverNamePlaceholder')}" required>
        <div class="form-help">${window.i18n.getMessage('mcpServerIdentifier')}</div>
      </div>

      <div class="form-group">
        <label class="form-label required">${window.i18n.getMessage('serverParameters')}</label>
        <textarea name="mcp_server_params_json" class="form-textarea json-input" rows="8"
                  placeholder="${window.i18n.getMessage('enterJsonMcpParams')}" required>${defaultJson}</textarea>
        <div class="json-validation-feedback"></div>
        <div class="form-help">
          ${window.i18n.getMessage('mcpParamsHelp')}
          <br><code>{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]}</code>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">${window.i18n.getMessage('description')}</label>
        <textarea name="description" class="form-textarea" placeholder="${window.i18n.getMessage('optionalDescriptionMcp')}">${profile?.description || ''}</textarea>
        <div class="form-help">${window.i18n.getMessage('optionalDescriptionHelp')}</div>
      </div>

      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
          <input type="checkbox" name="is_active" ${profile?.is_active !== false ? 'checked' : ''}>
          <span class="form-label" style="margin: 0;">${window.i18n.getMessage('active')}</span>
        </label>
        <div class="form-help">${window.i18n.getMessage('activeMcpProfileHelp')}</div>
      </div>
    `;
  }

  setupProfileFormEvents() {
    console.log('[SettingsProfiles] Setting up profile form events');
    
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
        throw new Error(window.i18n.getMessage('invalidJsonMcp'));
      }

      // Validate required fields
      if (!parsed.command || typeof parsed.command !== 'string') {
        throw new Error(window.i18n.getMessage('missingInvalidCommand'));
      }

      // Validate args if present
      if (parsed.args && !Array.isArray(parsed.args)) {
        throw new Error(window.i18n.getMessage('argsMustBeArray'));
      }

      // Success
      feedbackElement.innerHTML = `<span class="json-success">${window.i18n.getMessage('validJson')}</span>`;
      textarea.classList.remove('json-invalid');
      textarea.classList.add('json-valid');

      // Store valid state for form submission
      textarea.dataset.isValid = 'true';

    } catch (error) {
      const errorMessage = error.message;
      feedbackElement.innerHTML = `<span class="json-error">${window.i18n.getMessage('invalidJson')}${errorMessage}</span>`;
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
        throw new Error(window.i18n.getMessage('invalidJsonVoice'));
      }

      // Success - no specific validation required for voice meta params (flexible structure)
      feedbackElement.innerHTML = `<span class="json-success">${window.i18n.getMessage('validJson')}</span>`;
      textarea.classList.remove('json-invalid');
      textarea.classList.add('json-valid');

      // Store valid state for form submission
      textarea.dataset.isValid = 'true';

    } catch (error) {
      const errorMessage = error.message;
      feedbackElement.innerHTML = `<span class="json-error">${window.i18n.getMessage('invalidJson')}${errorMessage}</span>`;
      textarea.classList.remove('json-valid');
      textarea.classList.add('json-invalid');

      // Store invalid state for form submission
      textarea.dataset.isValid = 'false';
      textarea.dataset.errorMessage = errorMessage;
    }
  }

  handleProfileFormSubmitClick(event) {
    console.log('[SettingsProfiles] Profile form submit button clicked');
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
    modelSelect.innerHTML = `<option value="">${window.i18n.getMessage('loading')}</option>`;

    try {
      const response = await this.apiClient.getVoiceModels(selectedType);
      const models = response.models || response || [];

      // Models are already filtered by the API, no need to filter again

      // Update select options
      modelSelect.innerHTML = `<option value="">${window.i18n.getMessage('selectModel')}</option>` +
        models.map(model =>
          `<option value="${model.model_name}">${model.model_name}</option>`
        ).join('');

    } catch (error) {
      console.error('[SettingsProfiles] Failed to fetch voice models for type:', error);
      modelSelect.innerHTML = `<option value="">${window.i18n.getMessage('failedToLoadModels')}</option>`;

      // Show user-friendly error notification
      this.emit('notification', {
        message: window.i18n.getMessage('failedToLoadModelsForType', [selectedType]),
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
    modelInput.placeholder = window.i18n.getMessage('loadingProviderModels', [selectedProvider]);
    modelDatalist.innerHTML = `<option value="">${window.i18n.getMessage('loading')}</option>`;

    try {
      const response = await this.apiClient.getLLMProviderModels(selectedProvider);
      const models = response.models || response || [];

      // Update datalist options
      modelDatalist.innerHTML = models.map(model =>
        `<option value="${model}">${model}</option>`
      ).join('');

      // Update placeholder to reflect the new provider
      modelInput.placeholder = models.length > 0
        ? window.i18n.getMessage('selectProviderModelOrCustom', [selectedProvider])
        : window.i18n.getMessage('enterProviderModelManually', [selectedProvider]);

    } catch (error) {
      console.error('[SettingsProfiles] Failed to fetch models for provider:', error);
      modelDatalist.innerHTML = `<option value="">${window.i18n.getMessage('failedToLoadModels')}</option>`;
      modelInput.placeholder = window.i18n.getMessage('enterProviderModelManually', [selectedProvider]);

      // Show user-friendly error notification
      this.emit('notification', {
        message: window.i18n.getMessage('failedToLoadModelsManually', [selectedProvider]),
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
    console.log('[SettingsProfiles] Profile form submit triggered');
    
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
          console.error('[SettingsProfiles] Failed to parse Voice meta params JSON:', error);
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
        console.error('[SettingsProfiles] JSON validation failed during form submission');
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
          console.error('[SettingsProfiles] Failed to parse MCP server params JSON:', error);
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
      console.log(`[SettingsProfiles] Starting ${mode} operation for ${type} profile`);
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
      
      // Refresh the profiles data
      await this.loadAllProfiles();
      
      // Emit event for profile updates
      this.emit('profilesUpdated', {
        llmProfiles: this.state.llmProfiles,
        mcpProfiles: this.state.mcpProfiles,
        voiceProfiles: this.state.voiceProfiles
      });
      
    } catch (error) {
      console.error(`[SettingsProfiles] Failed to ${mode} ${type} profile:`, error);
      
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
      submitButton.textContent = isSubmitting ? window.i18n.getMessage('saving') : window.i18n.getMessage('saveProfile');
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
          <h3>${window.i18n.getMessage('noLLMProfiles')}</h3>
          <p>${window.i18n.getMessage('createFirstLLMProfile')}</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_default ? 'default' : ''}" data-profile-id="${profile.profile_name}">
        ${profile.is_default ? `<div class="profile-badge">${window.i18n.getMessage('default')}</div>` : ''}
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.profile_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.provider)}</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="${window.i18n.getMessage('editProfile')}" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="${window.i18n.getMessage('deleteProfile')}" data-profile-id="${profile.profile_name}">
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
            ${profile.base_url ? `<div class="profile-detail"><strong>${window.i18n.getMessage('base_url')}:</strong> ${this.escapeHtml(profile.base_url)}</div>` : ''}
            ${profile.temperature !== undefined ? `<div class="profile-detail"><strong>${window.i18n.getMessage('temperature_detail')}:</strong> ${profile.temperature}</div>` : ''}
            ${profile.max_tokens ? `<div class="profile-detail"><strong>${window.i18n.getMessage('max_tokens_detail')}:</strong> ${profile.max_tokens}</div>` : ''}
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
          <h3>${window.i18n.getMessage('noMCPProfiles')}</h3>
          <p>${window.i18n.getMessage('createFirstMCPProfile')}</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_active ? 'active' : 'inactive'}" data-profile-id="${profile.mcp_id}">
        <div class="profile-status ${profile.is_active ? 'active' : 'inactive'}">
          ${profile.is_active ? window.i18n.getMessage('active') : window.i18n.getMessage('inactive')}
        </div>
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.display_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.mcp_server_name)}</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="${window.i18n.getMessage('editProfile')}" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="${window.i18n.getMessage('deleteProfile')}" data-profile-id="${profile.mcp_id}">
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
            <div class="profile-detail"><strong>${window.i18n.getMessage('command')}:</strong> ${this.escapeHtml(profile.mcp_server_params?.command || 'N/A')}</div>
            ${profile.mcp_server_params?.args?.length ? `<div class="profile-detail"><strong>${window.i18n.getMessage('args')}:</strong> ${profile.mcp_server_params.args.join(', ')}</div>` : ''}
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
          <h3>${window.i18n.getMessage('noVoiceProfiles')}</h3>
          <p>${window.i18n.getMessage('createFirstVoiceProfile')}</p>
        </div>
      `;
      return;
    }

    const profilesHTML = profiles.map(profile => `
      <div class="profile-card ${profile.is_active ? 'active' : 'inactive'}" data-profile-id="${profile.voice_profile_name}">
        <div class="profile-status ${profile.is_active ? 'active' : 'inactive'}">
          ${profile.is_active ? window.i18n.getMessage('active') : window.i18n.getMessage('inactive')}
        </div>
        <div class="profile-header">
          <div class="profile-title">
            <h3>${this.escapeHtml(profile.voice_profile_name)}</h3>
            <span class="profile-provider">${this.escapeHtml(profile.voice_model_name)} (${profile.voice_model_type.toUpperCase()})</span>
          </div>
          <div class="profile-actions">
            <button class="profile-action-btn edit" title="${window.i18n.getMessage('editProfile')}" data-profile='${JSON.stringify(profile)}'>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89783 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="profile-action-btn delete" title="${window.i18n.getMessage('deleteProfile')}" data-profile-id="${profile.voice_profile_name}">
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
            <div class="profile-detail"><strong>${window.i18n.getMessage('modelDetail')}:</strong> ${this.escapeHtml(profile.voice_model_name)}</div>
            <div class="profile-detail"><strong>${window.i18n.getMessage('typeDetail')}:</strong> ${profile.voice_model_type.toUpperCase()}</div>
            ${profile.voice_meta_params ? `<div class="profile-detail"><strong>${window.i18n.getMessage('parameters')}:</strong> ${Object.keys(profile.voice_meta_params).length} ${window.i18n.getMessage('customSettings')}</div>` : ''}
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
        message: window.i18n.getMessage('onlyLLMProfileError'),
        details: window.i18n.getMessage('onlyLLMProfileErrorDetails'),
        buttons: [
          {
            text: window.i18n.getMessage('createNewProfile'),
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
      this.emit('loading', { message: window.i18n.getMessage('updatingDefaultProfile') });

      // First, set the new default profile
      await this.apiClient.updateLLMProfile(newDefaultProfileId, { is_default: true });

      this.emit('loading', { message: window.i18n.getMessage('deletingProfile') });

      // Then delete the old default profile
      await this.apiClient.deleteLLMProfile(profileToDelete);

      this.emit('notification', {
        message: window.i18n.getMessage('profileDeletedSetDefault', [profileToDelete, newDefaultProfileId]),
        type: 'success'
      });

      // Refresh the profiles data
      await this.loadAllProfiles();

      // Emit event for profile updates
      this.emit('profilesUpdated', {
        llmProfiles: this.state.llmProfiles,
        mcpProfiles: this.state.mcpProfiles,
        voiceProfiles: this.state.voiceProfiles
      });

      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      console.error('[SettingsProfiles] Failed to set new default and delete profile:', error);
      this.emit('notification', {
        message: `${window.i18n.getMessage('failedToUpdateProfiles')}: ${error.message}`,
        type: 'error'
      });
      throw error;
    }
  }

  async performDeleteProfile(type, profileId) {
    try {
      this.emit('loading', { message: `${window.i18n.getMessage('deleting')} ${type} ${window.i18n.getMessage('profile').toLowerCase()}...` });

      if (type === 'llm') {
        await this.apiClient.deleteLLMProfile(profileId);
      } else if (type === 'voice') {
        await this.apiClient.deleteVoiceProfile(profileId);
      } else {
        await this.apiClient.deleteMCPProfile(profileId);
      }

      this.emit('notification', {
        message: `${type.toUpperCase()} ${window.i18n.getMessage('deletedSuccessfully')}`,
        type: 'success'
      });

      // Refresh the profiles data
      await this.loadAllProfiles();

      // Emit event for profile updates
      this.emit('profilesUpdated', {
        llmProfiles: this.state.llmProfiles,
        mcpProfiles: this.state.mcpProfiles,
        voiceProfiles: this.state.voiceProfiles
      });

      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      console.error(`[SettingsProfiles] Failed to delete ${type} profile:`, error);
      this.emit('notification', {
        message: `${window.i18n.getMessage('failedToDelete', [type])}: ${error.message}`,
        type: 'error'
      });
    }
  }

  // Navigate to specific LLM profile for editing
  async navigateToLLMProfile(profileName) {
    console.log('[SettingsProfiles] Navigating to LLM profile:', profileName);

    // Find the profile in the current state
    const profile = this.state.llmProfiles.find(p => p.profile_name === profileName);

    if (profile) {
      // Show the edit form for this profile
      await this.showProfileForm('llm', profile);
      console.log('[SettingsProfiles] LLM profile edit form shown for:', profileName);
    } else {
      console.warn('[SettingsProfiles] Profile not found:', profileName);
      this.emit('notification', {
        message: `LLM ${window.i18n.getMessage('profileNotFound').replace(' profile', '')} "${profileName}".`,
        type: 'warning'
      });
    }
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

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Re-render all profile lists with current language
   * This should be called when language changes to update dynamically rendered content
   */
  rerenderAllProfiles() {
    console.log('[SettingsProfiles] Re-rendering all profiles for language change');
    this.renderLLMProfiles(this.state.llmProfiles);
    this.renderMCPProfiles(this.state.mcpProfiles);
    this.renderVoiceProfiles(this.state.voiceProfiles);
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSettingsProfiles = VibeSurfSettingsProfiles;
}