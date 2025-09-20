// File Manager - Handles file uploads, file links, and file operations
// Manages file selection, upload, display, and file:// protocol handling

class VibeSurfFileManager {
  constructor(sessionManager) {
    this.sessionManager = sessionManager;
    this.state = {
      uploadedFiles: [],
      isHandlingFileLink: false
    };
    this.elements = {};
    this.eventListeners = new Map();
    
    this.bindElements();
    this.bindEvents();
  }

  bindElements() {
    this.elements = {
      // File input and buttons
      attachFileBtn: document.getElementById('attach-file-btn'),
      fileInput: document.getElementById('file-input'),
      
      // File list container (created dynamically)
      uploadedFilesList: null
    };
  }

  bindEvents() {
    // File attachment
    this.elements.attachFileBtn?.addEventListener('click', this.handleAttachFiles.bind(this));
    this.elements.fileInput?.addEventListener('change', this.handleFileSelection.bind(this));
    
    // File link handling with delegation
    document.addEventListener('click', this.handleFileLinkClick.bind(this));
    
    // Listen for files uploaded event from session manager
    if (this.sessionManager) {
      this.sessionManager.on('filesUploaded', this.handleFilesUploaded.bind(this));
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
          console.error(`[FileManager] Event callback error for ${event}:`, error);
        }
      });
    }
  }

  // File Upload Handling
  handleAttachFiles() {
    this.elements.fileInput?.click();
  }

  async handleFileSelection(event) {
    const files = Array.from(event.target.files);
    
    if (files.length === 0) return;
    
    try {
      this.emit('loading', { message: `Uploading ${files.length} file(s)...` });
      
      const response = await this.sessionManager.uploadFiles(files);
      
      console.log('[FileManager] File upload response:', response);
      
      // SessionManager will emit 'filesUploaded' event, no need to handle manually
      // Remove duplicate handling that was causing files to appear twice
      
      this.emit('loading', { hide: true });
      this.emit('notification', {
        message: `${files.length} file(s) uploaded successfully`,
        type: 'success'
      });
      
      // Clear file input
      event.target.value = '';
    } catch (error) {
      this.emit('loading', { hide: true });
      this.emit('notification', {
        message: `File upload failed: ${error.message}`,
        type: 'error'
      });
    }
  }

  handleFilesUploaded(data) {
    console.log('[FileManager] Files uploaded event received:', data);
    
    // Ensure data.files is always an array - handle both single file and array cases
    let filesArray = [];
    if (data.files) {
      if (Array.isArray(data.files)) {
        filesArray = data.files;
      } else {
        // If single file object, wrap in array
        filesArray = [data.files];
        console.log('[FileManager] Single file detected, wrapping in array');
      }
    }
    
    console.log('[FileManager] Processing files array:', filesArray);
    
    if (filesArray.length > 0) {
      // Append new files to existing uploaded files (for multiple uploads)
      const newFiles = filesArray.map(file => ({
        id: file.file_id,
        name: file.original_filename,
        path: file.file_path,  // Updated to use file_path field
        size: file.file_size,
        type: file.mime_type,
        stored_filename: file.stored_filename,
        file_path: file.file_path  // Add file_path for backward compatibility
      }));
      
      console.log('[FileManager] Mapped new files:', newFiles);
      
      // Add to existing files instead of replacing
      this.state.uploadedFiles = [...this.state.uploadedFiles, ...newFiles];
      
      console.log('[FileManager] Updated uploaded files state:', this.state.uploadedFiles);
      
      // Update the visual file list
      this.updateFilesList();
    } else {
      console.warn('[FileManager] No files to process in uploaded data');
    }
  }

  // File List Management
  updateFilesList() {
    const container = this.getOrCreateFilesListContainer();
    
    // Debug logging to identify the issue
    console.log('[FileManager] updateFilesList called');
    console.log('[FileManager] uploadedFiles type:', typeof this.state.uploadedFiles);
    console.log('[FileManager] uploadedFiles isArray:', Array.isArray(this.state.uploadedFiles));
    console.log('[FileManager] uploadedFiles value:', this.state.uploadedFiles);
    
    // Ensure uploadedFiles is always an array
    if (!Array.isArray(this.state.uploadedFiles)) {
      console.error('[FileManager] uploadedFiles is not an array, resetting to empty array');
      this.state.uploadedFiles = [];
    }
    
    if (this.state.uploadedFiles.length === 0) {
      container.style.display = 'none';
      return;
    }
    
    container.style.display = 'block';
    
    // Build HTML safely with proper validation
    let filesHTML = '';
    try {
      filesHTML = this.state.uploadedFiles.map((file, index) => {
        console.log(`[FileManager] Processing file ${index}:`, file);
        
        // Validate file object structure
        if (!file || typeof file !== 'object') {
          console.error(`[FileManager] Invalid file object at index ${index}:`, file);
          return '';
        }
        
        // Extract properties safely with fallbacks
        const fileId = file.id || file.file_id || `file_${index}`;
        const fileName = file.name || file.original_filename || 'Unknown file';
        const filePath = file.path || file.file_path || file.stored_filename || 'Unknown path';
        
        console.log(`[FileManager] File display data: id=${fileId}, name=${fileName}, path=${filePath}`);
        
        return `
          <div class="file-item" data-file-id="${fileId}">
            <span class="file-name" title="${filePath}">${fileName}</span>
            <button class="file-remove-btn" title="Remove file" data-file-id="${fileId}">×</button>
          </div>
        `;
      }).join('');
    } catch (error) {
      console.error('[FileManager] Error generating files HTML:', error);
      filesHTML = '<div class="error-message">Error displaying files</div>';
    }
    
    container.innerHTML = `
      <div class="files-items">
        ${filesHTML}
      </div>
    `;
    
    // Add event listeners for remove buttons
    container.querySelectorAll('.file-remove-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const fileId = btn.dataset.fileId;
        this.removeUploadedFile(fileId);
      });
    });
  }

  getOrCreateFilesListContainer() {
    let container = document.getElementById('uploaded-files-list');
    
    if (!container) {
      container = document.createElement('div');
      container.id = 'uploaded-files-list';
      container.className = 'uploaded-files-container';
      
      // Insert after the textarea-container to avoid affecting button layout
      const taskInput = document.getElementById('task-input');
      if (taskInput) {
        const textareaContainer = taskInput.closest('.textarea-container');
        if (textareaContainer && textareaContainer.parentElement) {
          // Insert after the textarea-container but before the input-footer
          const inputFooter = textareaContainer.parentElement.querySelector('.input-footer');
          if (inputFooter) {
            textareaContainer.parentElement.insertBefore(container, inputFooter);
          } else {
            textareaContainer.parentElement.insertBefore(container, textareaContainer.nextSibling);
          }
        }
      }
    }
    
    return container;
  }

  removeUploadedFile(fileId) {
    console.log('[FileManager] Removing uploaded file:', fileId);
    
    // Remove from state
    this.state.uploadedFiles = this.state.uploadedFiles.filter(file => file.id !== fileId);
    
    // Update visual list
    this.updateFilesList();
    
    this.emit('notification', {
      message: 'File removed from upload list',
      type: 'info'
    });
  }

  clearUploadedFiles() {
    this.state.uploadedFiles = [];
    this.updateFilesList();
  }

  // File Link Handling
  handleFileLinkClick(event) {
    const target = event.target;
    
    // Check if clicked element is a file link
    if (target.matches('a.file-link') || target.closest('a.file-link')) {
      event.preventDefault();
      
      const fileLink = target.matches('a.file-link') ? target : target.closest('a.file-link');
      const filePath = fileLink.getAttribute('data-file-path');
      
      this.handleFileLink(filePath);
    }
  }

  async handleFileLink(filePath) {
    // Prevent multiple simultaneous calls
    if (this.state.isHandlingFileLink) {
      console.log('[FileManager] File link handling already in progress, skipping...');
      return;
    }
    
    this.state.isHandlingFileLink = true;
    
    try {
      console.log('[FileManager] Handling file link:', filePath);
      
      // Validate input
      if (!filePath || typeof filePath !== 'string') {
        throw new Error('Invalid file path provided');
      }
      
      // First decode the URL-encoded path safely
      let decodedPath;
      try {
        decodedPath = decodeURIComponent(filePath);
      } catch (decodeError) {
        console.warn('[FileManager] Failed to decode URL, using original path:', decodeError);
        decodedPath = filePath;
      }
      
      // Remove file:// protocol prefix and normalize
      let cleanPath = decodedPath.replace(/^file:\/\/\//, '').replace(/^file:\/\//, '');
      
      // Ensure path starts with / for Unix paths if not Windows drive
      if (!cleanPath.startsWith('/') && !cleanPath.match(/^[A-Za-z]:/)) {
        cleanPath = '/' + cleanPath;
      }
      
      // Convert all backslashes to forward slashes
      cleanPath = cleanPath.replace(/\\/g, '/');
      
      // Create proper file URL - always use triple slash for proper format
      const fileUrl = cleanPath.match(/^[A-Za-z]:/) ?
        `file:///${cleanPath}` :
        `file:///${cleanPath.replace(/^\//, '')}`;  // Remove leading slash and add triple slash
      
      console.log('[FileManager] Processed file URL:', fileUrl);
      
      // Show user notification about the action
      this.emit('notification', {
        message: `Opening file: ${cleanPath}`,
        type: 'info'
      });
      
      // Use setTimeout to prevent UI blocking and ensure proper cleanup
      setTimeout(async () => {
        try {
          // For user-clicked file links, use OPEN_FILE_URL to keep tab open
          // This prevents the auto-close behavior in OPEN_FILE_SYSTEM
          const fileOpenResponse = await Promise.race([
            chrome.runtime.sendMessage({
              type: 'OPEN_FILE_URL',
              data: { fileUrl: fileUrl }
            }),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error('File open timeout')), 5000)
            )
          ]);
          
          if (fileOpenResponse && fileOpenResponse.success) {
            this.emit('notification', {
              message: 'File opened in browser tab',
              type: 'success'
            });
            return;
          } else if (fileOpenResponse && fileOpenResponse.error) {
            console.warn('[FileManager] Background script file open failed:', fileOpenResponse.error);
          }
          
          // If OPEN_FILE_URL fails, try direct browser open with additional safety
          try {
            const opened = window.open(fileUrl, '_blank', 'noopener,noreferrer');
            if (opened && !opened.closed) {
              this.emit('notification', {
                message: 'File opened in browser',
                type: 'success'
              });
              return;
            }
          } catch (browserError) {
            console.error('[FileManager] Browser open failed:', browserError);
          }
          
          // Last resort: Copy path to clipboard
          await this.copyToClipboardFallback(fileUrl);
          
        } catch (error) {
          console.error('[FileManager] Error in async file handling:', error);
          
          // Provide more helpful error messages
          let userMessage = 'Unable to open file';
          if (error.message.includes('timeout')) {
            userMessage = 'File open operation timed out. Try copying the path manually.';
          } else if (error.message.includes('protocol')) {
            userMessage = 'Browser security restricts opening local files. File path copied to clipboard.';
          } else {
            userMessage = `Unable to open file: ${error.message}`;
          }
          
          this.emit('notification', {
            message: userMessage,
            type: 'error'
          });
          
          // Fallback to clipboard
          try {
            await this.copyToClipboardFallback(fileUrl);
          } catch (clipboardError) {
            console.error('[FileManager] Clipboard fallback also failed:', clipboardError);
          }
        } finally {
          this.state.isHandlingFileLink = false;
        }
      }, 50); // Small delay to prevent UI blocking
      
    } catch (error) {
      console.error('[FileManager] Error handling file link:', error);
      this.emit('notification', {
        message: `File link processing failed: ${error.message}`,
        type: 'error'
      });
      this.state.isHandlingFileLink = false;
    }
  }
  

  async copyToClipboardFallback(fileUrl) {
    try {
      await navigator.clipboard.writeText(fileUrl);
      this.emit('notification', {
        message: 'File URL copied to clipboard - paste in browser address bar',
        type: 'info'
      });
    } catch (clipboardError) {
      console.error('[FileManager] Clipboard failed:', clipboardError);
      this.emit('notification', {
        message: 'Unable to open file. URL: ' + fileUrl,
        type: 'warning'
      });
    }
  }

  // Utility Methods
  formatFileSize(bytes) {
    if (!bytes) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Public interface
  getUploadedFiles() {
    return [...this.state.uploadedFiles]; // Return copy
  }

  getUploadedFilesForTask() {
    if (this.state.uploadedFiles.length === 0) {
      return null;
    }

    console.log('[FileManager] Raw uploaded files state:', this.state.uploadedFiles);
    
    // Extract the first file path (backend expects single string)
    const firstFile = this.state.uploadedFiles[0];
    let filePath = null;
    
    if (typeof firstFile === 'string') {
      filePath = firstFile;
    } else if (firstFile && typeof firstFile === 'object') {
      // Extract path and normalize
      filePath = firstFile.file_path || firstFile.path || firstFile.stored_filename || firstFile.file_path;
      if (filePath) {
        filePath = filePath.replace(/\\/g, '/');
        console.log('[FileManager] Normalized file path:', filePath);
      }
    }
    
    if (filePath) {
      // Show info if multiple files uploaded but only first will be processed
      if (this.state.uploadedFiles.length > 1) {
        console.warn('[FileManager] Multiple files uploaded, but backend only supports single file. Using first file:', filePath);
        this.emit('notification', {
          message: `Multiple files uploaded. Only the first file "${firstFile.name || filePath}" will be processed.`,
          type: 'warning'
        });
      }
      
      return filePath;
    } else {
      console.error('[FileManager] Could not extract file path from uploaded file:', firstFile);
      return null;
    }
  }

  hasUploadedFiles() {
    return this.state.uploadedFiles.length > 0;
  }

  // Enable/disable file attachment based on task running state
  setEnabled(enabled) {
    if (this.elements.attachFileBtn) {
      this.elements.attachFileBtn.disabled = !enabled;
      
      if (enabled) {
        this.elements.attachFileBtn.classList.remove('task-running-disabled');
        this.elements.attachFileBtn.removeAttribute('title');
      } else {
        this.elements.attachFileBtn.classList.add('task-running-disabled');
        this.elements.attachFileBtn.setAttribute('title', 'Disabled while task is running');
      }
    }
  }

  // Get current state
  getState() {
    return { ...this.state };
  }

  // Update session manager reference
  setSessionManager(sessionManager) {
    this.sessionManager = sessionManager;
    
    // Re-bind files uploaded event
    if (this.sessionManager) {
      this.sessionManager.on('filesUploaded', this.handleFilesUploaded.bind(this));
    }
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfFileManager = VibeSurfFileManager;
}