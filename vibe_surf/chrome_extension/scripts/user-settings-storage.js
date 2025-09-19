// User Settings Storage Manager - Unified local storage management for user settings
// Supports Chrome extension storage API and localStorage with unified settings interface

class VibeSurfUserSettingsStorage {
  constructor() {
    this.storageKeys = {
      // Chrome storage keys
      userSettings: 'vibesurf-user-settings',
      
      // LocalStorage keys (for backward compatibility)
      theme: 'vibesurf-theme',
      defaultAsr: 'vibesurf-default-asr',
      defaultTts: 'vibesurf-default-tts',
      
      // New setting keys
      selectedLlmProfile: 'vibesurf-selected-llm-profile',
      selectedAgentMode: 'vibesurf-selected-agent-mode'
    };
    
    // Default settings
    this.defaultSettings = {
      // General settings
      theme: 'auto',
      defaultAsr: '',
      defaultTts: '',
      
      // UI state settings
      selectedLlmProfile: '',
      selectedAgentMode: 'thinking',
      
      // Additional settings can be extended here
      lastSessionId: '',
      rememberSelections: true,
      autoSaveSettings: true
    };
    
    this.eventListeners = new Map();
    this.isInitialized = false;
  }

  // Initialize the storage manager
  async initialize() {
    try {
      console.log('[UserSettingsStorage] Initializing user settings storage...');
      
      // Check if this is first run and migrate existing settings if needed
      await this.migrateExistingSettings();
      
      // Ensure all default settings exist
      await this.ensureDefaultSettings();
      
      this.isInitialized = true;
      console.log('[UserSettingsStorage] User settings storage initialized successfully');
      
      this.emit('initialized', await this.getAllSettings());
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to initialize:', error);
      throw error;
    }
  }

  // Migrate existing localStorage settings to unified storage
  async migrateExistingSettings() {
    try {
      console.log('[UserSettingsStorage] Checking for existing settings to migrate...');
      
      const existingSettings = {};
      
      // Check and migrate existing localStorage settings
      const localStorageKeys = [
        { old: this.storageKeys.theme, new: 'theme' },
        { old: this.storageKeys.defaultAsr, new: 'defaultAsr' },
        { old: this.storageKeys.defaultTts, new: 'defaultTts' }
      ];
      
      localStorageKeys.forEach(({ old, new: newKey }) => {
        const value = localStorage.getItem(old);
        if (value !== null) {
          existingSettings[newKey] = value;
          console.log(`[UserSettingsStorage] Found existing ${newKey}:`, value);
        }
      });
      
      // If there are existing settings, save them to the new storage system
      if (Object.keys(existingSettings).length > 0) {
        console.log('[UserSettingsStorage] Migrating existing settings:', existingSettings);
        await this.saveSettings(existingSettings);
      }
    } catch (error) {
      console.warn('[UserSettingsStorage] Failed to migrate existing settings:', error);
    }
  }

  // Ensure all default settings exist
  async ensureDefaultSettings() {
    try {
      const currentSettings = await this.getAllSettings();
      const mergedSettings = { ...this.defaultSettings, ...currentSettings };
      
      // Only save if there are missing settings
      if (Object.keys(currentSettings).length !== Object.keys(mergedSettings).length) {
        await this.saveSettings(mergedSettings);
        console.log('[UserSettingsStorage] Default settings ensured');
      }
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to ensure default settings:', error);
    }
  }

  // Get all settings from storage
  async getAllSettings() {
    try {
      console.log('[UserSettingsStorage] getAllSettings called');
      
      if (chrome && chrome.storage && chrome.storage.local) {
        console.log('[UserSettingsStorage] Using Chrome storage API');
        // Use Chrome storage API with proper promise wrapping
        const result = await new Promise((resolve, reject) => {
          chrome.storage.local.get(this.storageKeys.userSettings, (result) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve(result);
            }
          });
        });
        const settings = result[this.storageKeys.userSettings] || {};
        console.log('[UserSettingsStorage] Retrieved settings from Chrome storage:', settings);
        return settings;
      } else {
        console.log('[UserSettingsStorage] Using localStorage fallback');
        // Fallback to localStorage
        const stored = localStorage.getItem(this.storageKeys.userSettings);
        const settings = stored ? JSON.parse(stored) : {};
        console.log('[UserSettingsStorage] Retrieved settings from localStorage:', settings);
        return settings;
      }
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to get all settings:', error);
      // Fallback to localStorage if Chrome storage fails
      try {
        const stored = localStorage.getItem(this.storageKeys.userSettings);
        const settings = stored ? JSON.parse(stored) : {};
        console.log('[UserSettingsStorage] Fallback to localStorage successful:', settings);
        return settings;
      } catch (fallbackError) {
        console.error('[UserSettingsStorage] localStorage fallback also failed:', fallbackError);
        return {};
      }
    }
  }

  // Save settings to storage
  async saveSettings(settings) {
    try {
      console.log('[UserSettingsStorage] saveSettings called with:', settings);
      
      if (chrome && chrome.storage && chrome.storage.local) {
        console.log('[UserSettingsStorage] Using Chrome storage API for save');
        // Use Chrome storage API with proper promise wrapping
        await new Promise((resolve, reject) => {
          chrome.storage.local.set({
            [this.storageKeys.userSettings]: settings
          }, () => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve();
            }
          });
        });
        console.log('[UserSettingsStorage] Settings saved to Chrome storage successfully');
      } else {
        console.log('[UserSettingsStorage] Using localStorage for save');
        // Fallback to localStorage
        localStorage.setItem(this.storageKeys.userSettings, JSON.stringify(settings));
        console.log('[UserSettingsStorage] Settings saved to localStorage successfully');
      }
      
      console.log('[UserSettingsStorage] Settings saved:', settings);
      this.emit('settingsChanged', settings);
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to save settings:', error);
      // Fallback to localStorage if Chrome storage fails
      try {
        console.log('[UserSettingsStorage] Attempting localStorage fallback for save');
        localStorage.setItem(this.storageKeys.userSettings, JSON.stringify(settings));
        console.log('[UserSettingsStorage] Settings saved to localStorage fallback successfully');
        this.emit('settingsChanged', settings);
      } catch (fallbackError) {
        console.error('[UserSettingsStorage] localStorage fallback save also failed:', fallbackError);
        throw error; // Throw original error
      }
    }
  }

  // Get a specific setting value
  async getSetting(key) {
    try {
      const allSettings = await this.getAllSettings();
      return allSettings[key] !== undefined ? allSettings[key] : this.defaultSettings[key];
    } catch (error) {
      console.error(`[UserSettingsStorage] Failed to get setting ${key}:`, error);
      return this.defaultSettings[key];
    }
  }

  // Set a specific setting value
  async setSetting(key, value) {
    try {
      const allSettings = await this.getAllSettings();
      allSettings[key] = value;
      await this.saveSettings(allSettings);
      
      console.log(`[UserSettingsStorage] Setting updated: ${key} = ${value}`);
      this.emit('settingChanged', { key, value, allSettings });
    } catch (error) {
      console.error(`[UserSettingsStorage] Failed to set setting ${key}:`, error);
      throw error;
    }
  }

  // Update multiple settings at once
  async updateSettings(updates) {
    try {
      const allSettings = await this.getAllSettings();
      const updatedSettings = { ...allSettings, ...updates };
      await this.saveSettings(updatedSettings);
      
      console.log('[UserSettingsStorage] Multiple settings updated:', updates);
      this.emit('settingsUpdated', { updates, allSettings: updatedSettings });
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to update settings:', error);
      throw error;
    }
  }

  // Remove a setting
  async removeSetting(key) {
    try {
      const allSettings = await this.getAllSettings();
      delete allSettings[key];
      await this.saveSettings(allSettings);
      
      console.log(`[UserSettingsStorage] Setting removed: ${key}`);
      this.emit('settingRemoved', { key, allSettings });
    } catch (error) {
      console.error(`[UserSettingsStorage] Failed to remove setting ${key}:`, error);
      throw error;
    }
  }

  // Clear all settings (reset to defaults)
  async clearAllSettings() {
    try {
      await this.saveSettings(this.defaultSettings);
      console.log('[UserSettingsStorage] All settings cleared, reset to defaults');
      this.emit('settingsCleared', this.defaultSettings);
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to clear settings:', error);
      throw error;
    }
  }

  // Specific methods for commonly used settings

  // Theme settings
  async getTheme() {
    return await this.getSetting('theme');
  }

  async setTheme(theme) {
    await this.setSetting('theme', theme);
    // Also update localStorage for backward compatibility
    localStorage.setItem(this.storageKeys.theme, theme);
  }

  // LLM Profile settings
  async getSelectedLlmProfile() {
    const profile = await this.getSetting('selectedLlmProfile');
    console.log('[UserSettingsStorage] getSelectedLlmProfile returning:', profile);
    return profile;
  }

  async setSelectedLlmProfile(profileName) {
    console.log('[UserSettingsStorage] setSelectedLlmProfile called with:', profileName);
    await this.setSetting('selectedLlmProfile', profileName);
    console.log('[UserSettingsStorage] setSelectedLlmProfile completed');
  }

  // Agent Mode settings
  async getSelectedAgentMode() {
    const mode = await this.getSetting('selectedAgentMode');
    console.log('[UserSettingsStorage] getSelectedAgentMode returning:', mode);
    return mode;
  }

  async setSelectedAgentMode(mode) {
    console.log('[UserSettingsStorage] setSelectedAgentMode called with:', mode);
    await this.setSetting('selectedAgentMode', mode);
    console.log('[UserSettingsStorage] setSelectedAgentMode completed');
  }

  // Default Voice settings
  async getDefaultAsr() {
    return await this.getSetting('defaultAsr');
  }

  async setDefaultAsr(asrProfile) {
    await this.setSetting('defaultAsr', asrProfile);
    // Also update localStorage for backward compatibility
    localStorage.setItem(this.storageKeys.defaultAsr, asrProfile);
  }

  async getDefaultTts() {
    return await this.getSetting('defaultTts');
  }

  async setDefaultTts(ttsProfile) {
    await this.setSetting('defaultTts', ttsProfile);
    // Also update localStorage for backward compatibility
    localStorage.setItem(this.storageKeys.defaultTts, ttsProfile);
  }

  // Event system for components to listen to setting changes
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.eventListeners.has(event)) {
      const listeners = this.eventListeners.get(event);
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[UserSettingsStorage] Event callback error for ${event}:`, error);
        }
      });
    }
  }

  // Export settings for backup
  async exportSettings() {
    try {
      const allSettings = await this.getAllSettings();
      return {
        version: '1.0',
        timestamp: new Date().toISOString(),
        settings: allSettings
      };
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to export settings:', error);
      throw error;
    }
  }

  // Import settings from backup
  async importSettings(exportedData) {
    try {
      if (!exportedData || !exportedData.settings) {
        throw new Error('Invalid settings data');
      }
      
      await this.saveSettings(exportedData.settings);
      console.log('[UserSettingsStorage] Settings imported successfully');
      return true;
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to import settings:', error);
      throw error;
    }
  }

  // Get storage info
  async getStorageInfo() {
    try {
      const allSettings = await this.getAllSettings();
      const settingsSize = JSON.stringify(allSettings).length;
      
      return {
        isInitialized: this.isInitialized,
        settingsCount: Object.keys(allSettings).length,
        estimatedSize: settingsSize,
        storageType: (chrome && chrome.storage && chrome.storage.local) ? 'chrome.storage.local' : 'localStorage',
        lastUpdated: allSettings.lastUpdated || null
      };
    } catch (error) {
      console.error('[UserSettingsStorage] Failed to get storage info:', error);
      return null;
    }
  }

  // Destroy the storage manager
  destroy() {
    this.eventListeners.clear();
    this.isInitialized = false;
    console.log('[UserSettingsStorage] Storage manager destroyed');
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfUserSettingsStorage = VibeSurfUserSettingsStorage;
}