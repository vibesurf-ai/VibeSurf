// Settings General Manager - Handles general settings like theme, environment variables, and voice defaults
// Extracted from VibeSurfSettingsManager to improve code organization

class VibeSurfSettingsGeneral {
  constructor(apiClient, userSettingsStorage, emit) {
    this.apiClient = apiClient;
    this.userSettingsStorage = userSettingsStorage;
    this.emit = emit;
    this.elements = {};
  }

  // Bind DOM elements related to general settings
  bindElements() {
    this.elements = {
      // General Settings
      themeSelect: document.getElementById('theme-select'),
      defaultAsrSelect: document.getElementById('default-asr-select'),
      defaultTtsSelect: document.getElementById('default-tts-select'),
      
      // Environment Variables
      envVariablesList: document.getElementById('env-variables-list'),
      saveEnvVarsBtn: document.getElementById('save-env-vars-btn'),
      
      // Backend URL
      backendUrl: document.getElementById('backend-url')
    };
  }

  // Bind events for general settings
  bindEvents() {
    // General settings
    this.elements.themeSelect?.addEventListener('change', this.handleThemeChange.bind(this));
    this.elements.defaultAsrSelect?.addEventListener('change', this.handleDefaultAsrChange.bind(this));
    this.elements.defaultTtsSelect?.addEventListener('change', this.handleDefaultTtsChange.bind(this));
    
    // Environment variables
    this.elements.saveEnvVarsBtn?.addEventListener('click', this.handleSaveEnvironmentVariables.bind(this));
    
    // Backend URL
    this.elements.backendUrl?.addEventListener('change', this.handleBackendUrlChange.bind(this));
  }

  // Load general settings
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
      
      console.log('[SettingsGeneral] General settings loaded successfully');
    } catch (error) {
      console.error('[SettingsGeneral] Failed to load general settings:', error);
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
      console.error('[SettingsGeneral] Failed to load voice profiles for general settings:', error);
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
          
          console.log('[SettingsGeneral] Auto-selecting latest ASR profile:', latestAsrProfile.voice_profile_name);
          
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
        console.log('[SettingsGeneral] Restoring saved ASR profile to UI:', savedAsrProfile);
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
          
          console.log('[SettingsGeneral] Auto-selecting latest TTS profile:', latestTtsProfile.voice_profile_name);
          
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
        console.log('[SettingsGeneral] Restoring saved TTS profile to UI:', savedTtsProfile);
        if (this.elements.defaultTtsSelect) {
          this.elements.defaultTtsSelect.value = savedTtsProfile;
        }
      }
      
    } catch (error) {
      console.error('[SettingsGeneral] Failed to auto-select latest voice profiles:', error);
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
      console.error('[SettingsGeneral] Failed to change default ASR profile:', error);
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
      console.error('[SettingsGeneral] Failed to change default TTS profile:', error);
      this.emit('notification', {
        message: 'Failed to change default TTS profile',
        type: 'error'
      });
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
      console.error('[SettingsGeneral] Failed to change theme:', error);
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

  async loadEnvironmentVariables() {
    try {
      const response = await this.apiClient.getEnvironmentVariables();
      console.log('[SettingsGeneral] Environment variables loaded:', response);
      const envVars = response.environments || response || {};
      this.renderEnvironmentVariables(envVars);
    } catch (error) {
      console.error('[SettingsGeneral] Failed to load environment variables:', error);
      this.renderEnvironmentVariables({});
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
      console.error('[SettingsGeneral] Failed to update environment variables:', error);
      this.emit('notification', {
        message: `Failed to update environment variables: ${error.message}`,
        type: 'error'
      });
    }
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
    console.log('[SettingsGeneral] Storage settings changed (bulk):', allSettings);
    
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

  // Update backend URL in the UI
  updateBackendUrl(url) {
    if (this.elements.backendUrl) {
      this.elements.backendUrl.value = url;
    }
  }

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSettingsGeneral = VibeSurfSettingsGeneral;
}