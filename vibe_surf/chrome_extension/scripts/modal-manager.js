// Modal Manager - Handles modal dialogs and user confirmations
// Manages warning modals, confirmation dialogs, and generic modal utilities

class VibeSurfModalManager {
  constructor() {
    this.state = {
      activeModals: new Set(),
      modalCounter: 0
    };
    this.eventListeners = new Map();
    
    this.bindGlobalEvents();
  }

  bindGlobalEvents() {
    // Handle escape key to close modals
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeTopModal();
      }
    });
    
    // Handle background clicks to close modals
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) {
        this.closeModal(e.target.querySelector('.modal'));
      }
    });
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
          console.error(`[ModalManager] Event callback error for ${event}:`, error);
        }
      });
    }
  }

  // Warning Modal
  showWarningModal(title, message, options = {}) {
    const {
      confirmText = 'OK',
      showCancel = false,
      cancelText = 'Cancel',
      onConfirm = null,
      onCancel = null,
      className = ''
    } = options;

    const modalId = this.generateModalId();
    
    // Add warning icon to title and always show cancel for warning modals
    const warningTitle = `⚠️ ${title}`;
    const shouldShowCancel = showCancel || true; // Always show cancel for warning modals
    
    const modalHTML = `
      <div class="modal-overlay dynamic-modal warning-modal" id="${modalId}-overlay">
        <div class="modal warning-modal ${className}" id="${modalId}">
          <div class="modal-content">
            <div class="modal-header">
              <h3>${this.escapeHtml(warningTitle)}</h3>
            </div>
            <div class="modal-body">
              <p>${this.escapeHtml(message)}</p>
            </div>
            <div class="modal-footer">
              ${shouldShowCancel ? `<button class="btn-secondary modal-cancel-btn" data-modal-id="${modalId}">${this.escapeHtml(cancelText)}</button>` : ''}
              <button class="btn-primary modal-confirm-btn" data-modal-id="${modalId}">${this.escapeHtml(confirmText)}</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Add to DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById(`${modalId}-overlay`);
    
    // Track active modal
    this.state.activeModals.add(modalId);
    
    // Add event listeners
    this.bindModalEvents(modalId, { onConfirm, onCancel });
    
    // Show modal
    requestAnimationFrame(() => {
      overlay.classList.add('show');
    });
    
    return modalId;
  }

  // Confirmation Modal
  showConfirmModal(title, message, options = {}) {
    const {
      confirmText = 'Confirm',
      cancelText = 'Cancel',
      onConfirm = null,
      onCancel = null,
      className = '',
      type = 'question' // question, danger, info
    } = options;

    const modalId = this.generateModalId();
    
    const iconMap = {
      question: '❓',
      danger: '🚨',
      info: 'ℹ️'
    };
    
    const icon = iconMap[type] || iconMap.question;
    
    // Add icon to title and remove close button
    const iconTitle = `${icon} ${title}`;
    
    const modalHTML = `
      <div class="modal-overlay dynamic-modal" id="${modalId}-overlay">
        <div class="modal confirm-modal ${className}" id="${modalId}">
          <div class="modal-content">
            <div class="modal-header">
              <h3>${this.escapeHtml(iconTitle)}</h3>
            </div>
            <div class="modal-body">
              <p>${this.escapeHtml(message)}</p>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary modal-cancel-btn" data-modal-id="${modalId}">${this.escapeHtml(cancelText)}</button>
              <button class="btn-primary modal-confirm-btn" data-modal-id="${modalId}" ${type === 'danger' ? 'data-danger="true"' : ''}>${this.escapeHtml(confirmText)}</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Add to DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById(`${modalId}-overlay`);
    
    // Track active modal
    this.state.activeModals.add(modalId);
    
    // Add event listeners
    this.bindModalEvents(modalId, { onConfirm, onCancel });
    
    // Show modal
    requestAnimationFrame(() => {
      overlay.classList.add('show');
    });
    
    return modalId;
  }

  // Generic Modal Creator
  createModal(content, options = {}) {
    const {
      title = '',
      className = '',
      showCloseButton = true,
      backdrop = true,
      onShow = null,
      onHide = null
    } = options;

    const modalId = this.generateModalId();
    
    const modalHTML = `
      <div class="modal-overlay dynamic-modal ${backdrop ? 'backdrop' : ''}" id="${modalId}-overlay">
        <div class="modal ${className}" id="${modalId}">
          <div class="modal-content">
            ${title || showCloseButton ? `
              <div class="modal-header">
                ${title ? `<h3>${this.escapeHtml(title)}</h3>` : ''}
                ${showCloseButton ? `<button class="modal-close-btn" data-modal-id="${modalId}">×</button>` : ''}
              </div>
            ` : ''}
            <div class="modal-body">
              ${content}
            </div>
          </div>
        </div>
      </div>
    `;

    // Add to DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById(`${modalId}-overlay`);
    
    // Track active modal
    this.state.activeModals.add(modalId);
    
    // Add basic event listeners
    this.bindModalEvents(modalId, { onShow, onHide });
    
    // Show modal
    requestAnimationFrame(() => {
      overlay.classList.add('show');
      if (onShow) onShow(modal);
    });
    
    return {
      modalId,
      modal,
      overlay,
      close: () => this.closeModal(modal)
    };
  }

  // Modal Event Binding
  bindModalEvents(modalId, callbacks = {}) {
    const { onConfirm, onCancel, onShow, onHide } = callbacks;
    
    // Close button
    const closeBtn = document.querySelector(`[data-modal-id="${modalId}"].modal-close-btn`);
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.closeModal(document.getElementById(modalId));
        if (onCancel) onCancel();
      });
    }
    
    // Confirm button
    const confirmBtn = document.querySelector(`[data-modal-id="${modalId}"].modal-confirm-btn`);
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => {
        if (onConfirm) {
          const result = onConfirm();
          // Only close if callback doesn't return false
          if (result !== false) {
            this.closeModal(document.getElementById(modalId));
          }
        } else {
          this.closeModal(document.getElementById(modalId));
        }
      });
    }
    
    // Cancel button
    const cancelBtn = document.querySelector(`[data-modal-id="${modalId}"].modal-cancel-btn`);
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        this.closeModal(document.getElementById(modalId));
        if (onCancel) onCancel();
      });
    }
  }

  // Close Modal
  closeModal(modal) {
    if (!modal) return;
    
    const modalId = modal.id;
    const overlay = document.getElementById(`${modalId}-overlay`);
    
    if (overlay) {
      overlay.classList.remove('show');
      
      // Remove from DOM after animation
      setTimeout(() => {
        if (overlay.parentNode) {
          overlay.parentNode.removeChild(overlay);
        }
        this.state.activeModals.delete(modalId);
      }, 300); // Match CSS transition duration
    }
  }

  // Close the topmost modal
  closeTopModal() {
    const modalIds = Array.from(this.state.activeModals);
    if (modalIds.length > 0) {
      const topModalId = modalIds[modalIds.length - 1];
      const modal = document.getElementById(topModalId);
      if (modal) {
        this.closeModal(modal);
      }
    }
  }

  // Close all modals
  closeAllModals() {
    const modalIds = Array.from(this.state.activeModals);
    modalIds.forEach(modalId => {
      const modal = document.getElementById(modalId);
      if (modal) {
        this.closeModal(modal);
      }
    });
  }

  // Utility Methods
  generateModalId() {
    return `modal-${++this.state.modalCounter}-${Date.now()}`;
  }

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Promise-based modal methods
  showWarningModalAsync(title, message, options = {}) {
    return new Promise((resolve) => {
      this.showWarningModal(title, message, {
        ...options,
        onConfirm: () => {
          if (options.onConfirm) options.onConfirm();
          resolve(true);
        },
        onCancel: () => {
          if (options.onCancel) options.onCancel();
          resolve(false);
        }
      });
    });
  }

  showConfirmModalAsync(title, message, options = {}) {
    return new Promise((resolve) => {
      this.showConfirmModal(title, message, {
        ...options,
        onConfirm: async () => {
          try {
            let result = true;
            if (options.onConfirm) {
              result = await options.onConfirm();
              // If onConfirm returns false, don't resolve with true
              if (result === false) {
                resolve(false);
                return;
              }
            }
            resolve(true);
          } catch (error) {
            console.error('[ModalManager] onConfirm error:', error);
            resolve(false);
          }
        },
        onCancel: async () => {
          try {
            if (options.onCancel) {
              await options.onCancel();
            }
            resolve(false);
          } catch (error) {
            console.error('[ModalManager] onCancel error:', error);
            resolve(false);
          }
        }
      });
    });
  }

  // Modal state queries
  hasActiveModals() {
    return this.state.activeModals.size > 0;
  }

  getActiveModalCount() {
    return this.state.activeModals.size;
  }

  isModalActive(modalId) {
    return this.state.activeModals.has(modalId);
  }

  // Quick notification modal (auto-close)
  showNotificationModal(message, type = 'info', duration = 3000) {
    const typeIcons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };
    
    const icon = typeIcons[type] || typeIcons.info;
    const typeClass = `notification-${type}`;
    
    const modalData = this.createModal(`
      <div class="notification-content">
        <div class="notification-icon">${icon}</div>
        <div class="notification-message">${this.escapeHtml(message)}</div>
      </div>
    `, {
      className: `notification-modal ${typeClass}`,
      showCloseButton: false,
      backdrop: false
    });
    
    // Auto-close after duration
    if (duration > 0) {
      setTimeout(() => {
        modalData.close();
      }, duration);
    }
    
    return modalData.modalId;
  }

  // Quick input modal
  showInputModal(title, placeholder = '', defaultValue = '', options = {}) {
    const {
      inputType = 'text',
      confirmText = 'OK',
      cancelText = 'Cancel',
      onConfirm = null,
      onCancel = null,
      validator = null
    } = options;

    return new Promise((resolve) => {
      const inputId = `input-${Date.now()}`;
      
      const modalData = this.createModal(`
        <div class="input-modal-content">
          <label for="${inputId}" class="input-label">${title}</label>
          <input type="${inputType}" id="${inputId}" class="modal-input" 
                 placeholder="${this.escapeHtml(placeholder)}" 
                 value="${this.escapeHtml(defaultValue)}">
          <div class="modal-footer">
            <button class="btn-secondary input-cancel-btn">${this.escapeHtml(cancelText)}</button>
            <button class="btn-primary input-confirm-btn">${this.escapeHtml(confirmText)}</button>
          </div>
        </div>
      `, {
        className: 'input-modal',
        showCloseButton: true
      });
      
      const input = document.getElementById(inputId);
      const confirmBtn = modalData.modal.querySelector('.input-confirm-btn');
      const cancelBtn = modalData.modal.querySelector('.input-cancel-btn');
      
      // Focus input
      setTimeout(() => input.focus(), 100);
      
      const handleConfirm = () => {
        const value = input.value.trim();
        
        if (validator && !validator(value)) {
          return; // Don't close modal if validation fails
        }
        
        modalData.close();
        if (onConfirm) onConfirm(value);
        resolve(value);
      };
      
      const handleCancel = () => {
        modalData.close();
        if (onCancel) onCancel();
        resolve(null);
      };
      
      confirmBtn.addEventListener('click', handleConfirm);
      cancelBtn.addEventListener('click', handleCancel);
      
      // Enter key to confirm
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          handleConfirm();
        }
      });
    });
  }

  // Get current state
  getState() {
    return { ...this.state };
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfModalManager = VibeSurfModalManager;
}