/**
 * VibeSurf i18n Helper Utility
 *
 * Provides helper functions for internationalization in the VibeSurf Chrome Extension.
 * Uses Chrome's built-in chrome.i18n API for message translation.
 *
 * Usage:
 *   // Get a translated message
 *   const message = i18n.getMessage('appName');
 *
 *   // Get a message with placeholders
 *   const message = i18n.getMessage('pageOf', ['1', '5']);
 *
 *   // Translate all elements with data-i18n attribute
 *   i18n.translatePage();
 *
 *   // Translate a specific element
 *   i18n.translateElement(element);
 */

const VibeSurfI18n = (function() {
  'use strict';

  const STORAGE_KEY = 'vibesurf_locale';
  const SUPPORTED_LOCALES = ['en', 'zh_CN'];

  // Cache for loaded messages to support dynamic language switching
  let messageCache = {};
  let currentLocale = null;

  /**
   * Load messages from a locale file
   * @param {string} locale - The locale code (e.g., 'en', 'zh_CN')
   * @returns {Promise<Object>} The messages object
   */
  async function loadMessages(locale) {
    // Try to load from _locales folder
    try {
      const url = chrome.runtime.getURL(`_locales/${locale}/messages.json`);
      console.log(`[i18n] Loading messages from: ${url}`);

      const response = await fetch(url);
      console.log(`[i18n] Fetch response status: ${response.status}, ok: ${response.ok}`);

      if (!response.ok) {
        throw new Error(`Failed to load messages for locale: ${locale}, status: ${response.status}`);
      }

      const data = await response.json();
      const keyCount = Object.keys(data).length;
      console.log(`[i18n] ✓ Loaded ${keyCount} messages for locale: ${locale}`);

      // Verify some common keys exist
      if (data['inputPlaceholder']) {
        console.log(`[i18n] ✓ Found inputPlaceholder: ${data['inputPlaceholder'].message}`);
      }

      return data;
    } catch (error) {
      console.error(`[i18n] ✗ Failed to load messages for ${locale}:`, error);
      // Fallback to English
      if (locale !== 'en') {
        try {
          console.log(`[i18n] Trying fallback to English messages...`);
          const url = chrome.runtime.getURL(`_locales/en/messages.json`);
          const response = await fetch(url);
          if (response.ok) {
            const data = await response.json();
            console.log(`[i18n] ✓ Loaded ${Object.keys(data).length} fallback English messages`);
            return data;
          }
        } catch (fallbackError) {
          console.error('[i18n] ✗ Failed to load fallback English messages:', fallbackError);
        }
      }
      console.error(`[i18n] ✗ Returning empty messages object for locale: ${locale}`);
      return {};
    }
  }

  /**
   * Initialize the i18n system by loading messages
   * @param {string} locale - The locale code (e.g., 'en', 'zh_CN')
   */
  async function initialize(locale) {
    if (!messageCache[locale]) {
      messageCache[locale] = await loadMessages(locale);
    }
    currentLocale = locale;
  }

  /**
   * Get the current locale
   * @returns {string} The current locale code (e.g., 'en', 'zh_CN')
   */
  function getCurrentLocale() {
    return currentLocale || 'en';
  }

  /**
   * Get the message for the given key
   * @param {string} messageName - The message key
   * @param {string[]} [substitutions] - Optional substitutions for placeholders
   * @returns {string} The translated message
   */
  function getMessage(messageName, substitutions) {
    const locale = getCurrentLocale();
    const messages = messageCache[locale] || {};

    // Debug logging
    if (Object.keys(messages).length === 0) {
      console.warn(`[i18n] No messages loaded for locale: ${locale}. messageCache is empty.`);
    }

    let message = messages[messageName]?.message;

    // Handle placeholders
    if (message && substitutions) {
      substitutions.forEach((sub, index) => {
        message = message.replace(`$${index + 1}`, sub);
      });
    }

    // If message not found in our cache, try Chrome's native i18n API as fallback
    if (!message && typeof chrome !== 'undefined' && chrome.i18n) {
      try {
        message = chrome.i18n.getMessage(messageName);
        if (message) {
          console.log(`[i18n] Using Chrome native i18n for key: ${messageName}`);
        }
      } catch (e) {
        // Chrome i18n failed, continue
      }
    }

    const result = message || messageName;
    if (result === messageName && !messages[messageName]) {
      console.warn(`[i18n] Message not found for key: "${messageName}" in locale: ${locale}`);
    }

    return result;
  }

  /**
   * Format a message with plural forms
   * Chrome Extension i18n handles plurals via the placeholders system
   * @param {string} messageName - The message key
   * @param {number} count - The count for pluralization
   * @param {string[]} [additionalSubstitutions] - Additional substitutions
   * @returns {string} The translated and formatted message
   */
  function getPluralMessage(messageName, count, additionalSubstitutions = []) {
    return getMessage(messageName, [count.toString(), ...additionalSubstitutions]);
  }

  /**
   * Translate a single element
   * Handles various data attributes:
   * - data-i18n: Sets textContent
   * - data-i18n-placeholder: Sets placeholder attribute
   * - data-i18n-title: Sets title attribute
   * - data-i18n-alt: Sets alt attribute
   * - data-i18n-html: Sets innerHTML (use with caution)
   *
   * @param {HTMLElement} element - The element to translate
   */
  function translateElement(element) {
    if (!element) return;

    // Translate text content
    const key = element.getAttribute('data-i18n');
    if (key) {
      const substitutions = element.getAttribute('data-i18n-args');
      const args = substitutions ? JSON.parse(substitutions) : undefined;
      element.textContent = getMessage(key, args);
    }

    // Translate placeholder attribute
    const placeholderKey = element.getAttribute('data-i18n-placeholder');
    if (placeholderKey) {
      element.placeholder = getMessage(placeholderKey);
    }

    // Translate title attribute
    const titleKey = element.getAttribute('data-i18n-title');
    if (titleKey) {
      element.title = getMessage(titleKey);
    }

    // Translate alt attribute
    const altKey = element.getAttribute('data-i18n-alt');
    if (altKey) {
      element.alt = getMessage(altKey);
    }

    // Translate innerHTML (use with caution - only for trusted content)
    const htmlKey = element.getAttribute('data-i18n-html');
    if (htmlKey) {
      element.innerHTML = getMessage(htmlKey);
    }

    // Translate value attribute for inputs
    const valueKey = element.getAttribute('data-i18n-value');
    if (valueKey) {
      element.value = getMessage(valueKey);
    }
  }

  /**
   * Translate all elements in the document with data-i18n attributes
   * @param {HTMLElement|string} [context=document] - The context to search in (defaults to document)
   */
  function translatePage(context = document) {
    const root = typeof context === 'string' ?
      document.querySelector(context) : context;

    if (!root) return;

    const locale = getCurrentLocale();

    // Check if messages are loaded for the current locale
    if (!messageCache[locale] || Object.keys(messageCache[locale]).length === 0) {
      console.warn(`[i18n] Messages not loaded for locale: ${locale}. Attempting to load now...`);
      // Don't return - try to proceed anyway
    }

    console.log('[i18n] translatePage called, current locale:', locale, 'cache size:', messageCache[locale] ? Object.keys(messageCache[locale]).length : 0);

    // Find all elements with data-i18n attributes
    const selectors = [
      '[data-i18n]',
      '[data-i18n-placeholder]',
      '[data-i18n-title]',
      '[data-i18n-alt]',
      '[data-i18n-html]',
      '[data-i18n-value]'
    ];

    let totalElements = 0;
    selectors.forEach(selector => {
      const elements = root.querySelectorAll(selector);
      if (elements.length > 0) {
        console.log(`[i18n] Found ${elements.length} elements with ${selector}`);
        totalElements += elements.length;
      }
      elements.forEach(translateElement);
    });

    console.log(`[i18n] Translated ${totalElements} elements for locale: ${locale}`);
  }

  /**
   * Set the application locale and switch to it dynamically
   * This loads the messages for the new locale and applies them to the page.
   *
   * @param {string} locale - The locale to set
   * @returns {Promise<void>}
   */
  async function setLocale(locale) {
    if (!SUPPORTED_LOCALES.includes(locale)) {
      console.warn(`Unsupported locale: ${locale}. Supported: ${SUPPORTED_LOCALES.join(', ')}`);
      return;
    }

    // Load messages for the new locale if not cached
    if (!messageCache[locale]) {
      messageCache[locale] = await loadMessages(locale);
    }

    // Update current locale
    currentLocale = locale;

    // Store in chrome.storage.local
    return new Promise((resolve, reject) => {
      chrome.storage.local.set({ [STORAGE_KEY]: locale }, () => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve();
        }
      });
    });
  }

  /**
   * Get the stored locale preference
   * @returns {Promise<string>} The stored locale or 'en' as default
   */
  function getStoredLocale() {
    return new Promise((resolve) => {
      chrome.storage.local.get([STORAGE_KEY], (result) => {
        resolve(result[STORAGE_KEY] || 'en');
      });
    });
  }

  /**
   * Initialize locale from location-based detection if not already set
   * This should be called on app startup when no user preference exists
   * @param {Function} apiClientGetter - Function that returns the API client instance
   * @returns {Promise<string>} The locale that was set (or already existed)
   */
  async function initializeLocaleFromLocation(apiClientGetter) {
    return new Promise((resolve) => {
      chrome.storage.local.get([STORAGE_KEY], async (result) => {
        const existingLocale = result[STORAGE_KEY];

        // If user already has a preference, use it and initialize messages
        if (existingLocale) {
          console.log('[i18n] Using existing locale preference:', existingLocale);
          // Load messages for the existing locale
          await initialize(existingLocale);
          resolve(existingLocale);
          return;
        }

        // No preference exists, detect from location
        try {
          const apiClient = apiClientGetter();
          if (!apiClient) {
            console.warn('[i18n] No API client available, using default locale: en');
            await initialize('en');
            await setLocale('en');
            resolve('en');
            return;
          }

          const response = await apiClient.getLanguageFromLocation();
          const detectedLocale = response.suggested_language || 'en';

          console.log('[i18n] Detected locale from location:', {
            country: response.country,
            locale: detectedLocale,
            from_ip: response.detected_from_ip
          });

          // Initialize messages for the detected locale
          await initialize(detectedLocale);

          // Save the detected locale
          await setLocale(detectedLocale);
          resolve(detectedLocale);
        } catch (error) {
          console.error('[i18n] Failed to detect locale from location, using default:', error);
          await initialize('en');
          await setLocale('en');
          resolve('en');
        }
      });
    });
  }

  /**
   * Get all available locales
   * @returns {Array<{code: string, name: string}>} Array of available locales
   */
  function getAvailableLocales() {
    return [
      { code: 'en', name: 'English' },
      { code: 'zh_CN', name: '简体中文' }
    ];
  }

  /**
   * Translate a date according to the current locale
   * @param {Date|string|number} date - The date to format
   * @param {Object} [options] - Intl.DateTimeFormat options
   * @returns {string} The formatted date string
   */
  function formatDate(date, options = {}) {
    const dateObj = date instanceof Date ? date : new Date(date);
    const locale = getCurrentLocale();
    const defaultOptions = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    };

    return new Intl.DateTimeFormat(locale, { ...defaultOptions, ...options }).format(dateObj);
  }

  /**
   * Format a relative time (e.g., "5 minutes ago")
   * @param {Date|string|number} date - The date to compare
   * @returns {string} The relative time string
   */
  function formatRelativeTime(date) {
    const dateObj = date instanceof Date ? date : new Date(date);
    const now = new Date();
    const diffMs = now - dateObj;
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    const locale = getCurrentLocale();

    if (diffMinutes < 1) {
      return getMessage('justNow') || 'Just now';
    } else if (diffMinutes < 60) {
      return getPluralMessage('minutesAgo', diffMinutes);
    } else if (diffHours < 24) {
      return getPluralMessage('hoursAgo', diffHours);
    } else {
      return formatDate(dateObj, { month: 'short', day: 'numeric' });
    }
  }

  /**
   * Format a number according to the current locale
   * @param {number} number - The number to format
   * @param {Object} [options] - Intl.NumberFormat options
   * @returns {string} The formatted number string
   */
  function formatNumber(number, options = {}) {
    const locale = getCurrentLocale();
    return new Intl.NumberFormat(locale, options).format(number);
  }

  /**
   * Create a template tag function for easy message interpolation
   * Usage: i18n.t`hello ${name}` -> gets 'hello' message and substitutes 'name'
   *
   * @param {TemplateStringsArray} strings - The template strings
   * @param {...any} values - The substitution values
   * @returns {string} The translated string
   */
  function t(strings, ...values) {
    const key = strings[0];
    return getMessage(key, values);
  }

  // Public API
  return {
    // Core methods
    getMessage,
    getPluralMessage,
    translateElement,
    translatePage,

    // Locale management
    initialize,
    getCurrentLocale,
    setLocale,
    getStoredLocale,
    getAvailableLocales,
    initializeLocaleFromLocation,

    // Formatting utilities
    formatDate,
    formatRelativeTime,
    formatNumber,

    // Template tag
    t,

    // Constants
    SUPPORTED_LOCALES
  };
})();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VibeSurfI18n;
}

// Auto-assign to window for browser usage
if (typeof window !== 'undefined') {
  window.i18n = VibeSurfI18n;
}
