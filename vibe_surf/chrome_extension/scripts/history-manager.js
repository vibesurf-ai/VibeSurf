// History Manager - Handles history modal, recent tasks, and session history
// Manages history display, pagination, search, and filtering

class VibeSurfHistoryManager {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.state = {
      historyMode: 'recent', // 'recent' or 'all'
      currentPage: 1,
      totalPages: 1,
      pageSize: 10,
      searchQuery: '',
      statusFilter: 'all',
      recentTasks: [],
      allSessions: []
    };
    this.elements = {};
    this.eventListeners = new Map();
    
    this.bindElements();
    this.bindEvents();
  }

  bindElements() {
    this.elements = {
      // History Modal
      historyModal: document.getElementById('history-modal'),
      
      // Recent Tasks Section
      recentTasksList: document.getElementById('recent-tasks-list'),
      viewMoreTasksBtn: document.getElementById('view-more-tasks-btn'),
      
      // All Sessions Section
      allSessionsSection: document.getElementById('all-sessions-section'),
      backToRecentBtn: document.getElementById('back-to-recent-btn'),
      sessionSearch: document.getElementById('session-search'),
      sessionFilter: document.getElementById('session-filter'),
      allSessionsList: document.getElementById('all-sessions-list'),
      
      // Pagination
      prevPageBtn: document.getElementById('prev-page-btn'),
      nextPageBtn: document.getElementById('next-page-btn'),
      pageInfo: document.getElementById('page-info')
    };
  }

  bindEvents() {
    // History modal close button
    const historyModalClose = this.elements.historyModal?.querySelector('.modal-close');
    if (historyModalClose) {
      historyModalClose.addEventListener('click', this.hideModal.bind(this));
    }
    
    // History modal overlay click to close
    const historyModalOverlay = this.elements.historyModal?.querySelector('.modal-overlay');
    if (historyModalOverlay) {
      historyModalOverlay.addEventListener('click', (event) => {
        if (event.target === historyModalOverlay) {
          this.hideModal();
        }
      });
    }
    
    // View More Tasks button
    this.elements.viewMoreTasksBtn?.addEventListener('click', this.handleViewMoreTasks.bind(this));
    
    // Back to Recent button
    this.elements.backToRecentBtn?.addEventListener('click', this.handleBackToRecent.bind(this));
    
    // Search and filter
    this.elements.sessionSearch?.addEventListener('input', this.handleSessionSearch.bind(this));
    this.elements.sessionFilter?.addEventListener('change', this.handleSessionFilter.bind(this));
    
    // Pagination
    this.elements.prevPageBtn?.addEventListener('click', this.handlePrevPage.bind(this));
    this.elements.nextPageBtn?.addEventListener('click', this.handleNextPage.bind(this));
    
    // Global keyboard shortcuts for this modal
    document.addEventListener('keydown', this.handleKeydown.bind(this));
  }

  handleKeydown(event) {
    // Close history modal on Escape key
    if (event.key === 'Escape') {
      if (this.elements.historyModal && !this.elements.historyModal.classList.contains('hidden')) {
        this.hideModal();
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
          console.error(`[HistoryManager] Event callback error for ${event}:`, error);
        }
      });
    }
  }

  // Public interface for showing history
  async showHistory() {
    try {
      this.emit('loading', { message: 'Loading recent tasks...' });
      
      // Reset to recent tasks view
      this.state.historyMode = 'recent';
      await this.loadRecentTasks();
      this.displayHistoryModal();
      
      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      this.emit('error', { message: `Failed to load history: ${error.message}` });
    }
  }

  // Event Handlers
  async handleViewMoreTasks() {
    try {
      console.log('[HistoryManager] View More Tasks clicked');
      this.emit('loading', { message: 'Loading all sessions...' });
      
      // Switch to all sessions view
      this.state.historyMode = 'all';
      console.log('[HistoryManager] Set history mode to "all"');
      
      await this.loadAllSessions();
      console.log('[HistoryManager] All sessions loaded, switching view');
      
      this.displayAllSessionsView();
      console.log('[HistoryManager] All sessions view displayed');
      
      this.emit('loading', { hide: true });
    } catch (error) {
      this.emit('loading', { hide: true });
      console.error('[HistoryManager] Error in handleViewMoreTasks:', error);
      this.emit('error', { message: `Failed to load sessions: ${error.message}` });
    }
  }

  handleBackToRecent() {
    this.state.historyMode = 'recent';
    this.displayRecentTasksView();
  }

  handleSessionSearch(event) {
    this.state.searchQuery = event.target.value.trim().toLowerCase();
    this.filterAndDisplaySessions();
  }

  handleSessionFilter(event) {
    this.state.statusFilter = event.target.value;
    this.filterAndDisplaySessions();
  }

  handlePrevPage() {
    if (this.state.currentPage > 1) {
      this.state.currentPage--;
      this.filterAndDisplaySessions();
    }
  }

  handleNextPage() {
    if (this.state.currentPage < this.state.totalPages) {
      this.state.currentPage++;
      this.filterAndDisplaySessions();
    }
  }

  // Data Loading Methods
  async loadRecentTasks() {
    try {
      console.log('[HistoryManager] Loading recent tasks...');
      const response = await this.apiClient.getRecentTasks();
      
      // Handle API response structure: { tasks: [...], total_count: ..., limit: ... }
      let tasks = [];
      if (response && response.tasks && Array.isArray(response.tasks)) {
        tasks = response.tasks;
      } else if (response && Array.isArray(response)) {
        tasks = response;
      } else if (response && response.data && Array.isArray(response.data)) {
        tasks = response.data;
      }
      
      // Take only the first 3 most recent tasks
      this.state.recentTasks = tasks.slice(0, 3);
      console.log('[HistoryManager] Recent tasks loaded:', this.state.recentTasks.length);
      
      return this.state.recentTasks;
    } catch (error) {
      console.error('[HistoryManager] Failed to load recent tasks:', error);
      this.state.recentTasks = [];
      throw error;
    }
  }

  async loadAllSessions() {
    try {
      console.log('[HistoryManager] Loading all sessions...');
      const response = await this.apiClient.getAllSessions();
      
      // Handle API response structure: { sessions: [...], total_count: ..., limit: ..., offset: ... }
      let sessions = [];
      if (response && response.sessions && Array.isArray(response.sessions)) {
        sessions = response.sessions;
      } else if (response && Array.isArray(response)) {
        sessions = response;
      } else if (response && response.data && Array.isArray(response.data)) {
        sessions = response.data;
      }
      
      this.state.allSessions = sessions;
      console.log('[HistoryManager] All sessions loaded:', this.state.allSessions.length);
      
      return this.state.allSessions;
    } catch (error) {
      console.error('[HistoryManager] Failed to load all sessions:', error);
      this.state.allSessions = [];
      throw error;
    }
  }

  // Display Methods
  displayHistoryModal() {
    if (this.state.historyMode === 'recent') {
      this.displayRecentTasksView();
    } else {
      this.displayAllSessionsView();
    }
    this.showModal();
  }

  displayRecentTasksView() {
    console.log('[HistoryManager] Switching to recent tasks view');
    
    // Show recent tasks section and hide all sessions section
    if (this.elements.recentTasksList && this.elements.allSessionsSection) {
      const recentParent = this.elements.recentTasksList.parentElement;
      if (recentParent) {
        recentParent.classList.remove('hidden');
        recentParent.style.display = 'block';
        console.log('[HistoryManager] Showed recent tasks section');
      }
      this.elements.allSessionsSection.classList.add('hidden');
      this.elements.allSessionsSection.style.display = 'none';
      console.log('[HistoryManager] Hidden all sessions section');
    }
    
    this.renderRecentTasks();
  }

  displayAllSessionsView() {
    console.log('[HistoryManager] Switching to all sessions view');
    console.log('[HistoryManager] Elements check:', {
      recentTasksList: !!this.elements.recentTasksList,
      allSessionsSection: !!this.elements.allSessionsSection,
      recentTasksParent: !!this.elements.recentTasksList?.parentElement
    });
    
    // Hide recent tasks section and show all sessions section
    if (this.elements.recentTasksList && this.elements.allSessionsSection) {
      const recentParent = this.elements.recentTasksList.parentElement;
      if (recentParent) {
        recentParent.style.display = 'none';
        recentParent.classList.add('hidden');
        console.log('[HistoryManager] Hidden recent tasks section');
      }
      
      // Remove hidden class and set display block
      this.elements.allSessionsSection.classList.remove('hidden');
      this.elements.allSessionsSection.style.display = 'block';
      console.log('[HistoryManager] Showed all sessions section - removed hidden class and set display block');
      
      // Debug: Check computed styles
      const computedStyle = window.getComputedStyle(this.elements.allSessionsSection);
      console.log('[HistoryManager] All sessions section computed display:', computedStyle.display);
      console.log('[HistoryManager] All sessions section classList:', this.elements.allSessionsSection.classList.toString());
      
    } else {
      console.error('[HistoryManager] Missing elements for view switching:', {
        recentTasksList: !!this.elements.recentTasksList,
        allSessionsSection: !!this.elements.allSessionsSection
      });
    }
    
    // Reset search and filter
    this.state.currentPage = 1;
    this.state.searchQuery = '';
    this.state.statusFilter = 'all';
    
    if (this.elements.sessionSearch) {
      this.elements.sessionSearch.value = '';
    }
    if (this.elements.sessionFilter) {
      this.elements.sessionFilter.value = 'all';
    }
    
    console.log('[HistoryManager] About to filter and display sessions');
    this.filterAndDisplaySessions();
  }

  renderRecentTasks() {
    if (!this.elements.recentTasksList) return;
    
    this.elements.recentTasksList.innerHTML = '';
    
    if (this.state.recentTasks.length === 0) {
      this.elements.recentTasksList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <div class="empty-state-title">No Recent Tasks</div>
          <div class="empty-state-description">Start a new task to see it here.</div>
        </div>
      `;
      return;
    }
    
    this.state.recentTasks.forEach(task => {
      const taskItem = this.createTaskItem(task);
      this.elements.recentTasksList.appendChild(taskItem);
    });
  }

  filterAndDisplaySessions() {
    if (!this.elements.allSessionsList) {
      console.error('[HistoryManager] allSessionsList element not found');
      return;
    }
    
    console.log('[HistoryManager] Filtering sessions. Total sessions:', this.state.allSessions.length);
    console.log('[HistoryManager] Search query:', this.state.searchQuery);
    console.log('[HistoryManager] Status filter:', this.state.statusFilter);
    
    let filteredSessions = [...this.state.allSessions]; // Create copy
    
    // Apply search filter
    if (this.state.searchQuery) {
      filteredSessions = filteredSessions.filter(session =>
        session.session_id.toLowerCase().includes(this.state.searchQuery) ||
        (session.description && session.description.toLowerCase().includes(this.state.searchQuery))
      );
    }
    
    // Apply status filter
    if (this.state.statusFilter !== 'all') {
      filteredSessions = filteredSessions.filter(session =>
        (session.status || 'active').toLowerCase() === this.state.statusFilter.toLowerCase()
      );
    }
    
    console.log('[HistoryManager] Filtered sessions count:', filteredSessions.length);
    
    // Calculate pagination
    const totalSessions = filteredSessions.length;
    this.state.totalPages = Math.ceil(totalSessions / this.state.pageSize);
    
    // Ensure current page is valid
    if (this.state.currentPage > this.state.totalPages) {
      this.state.currentPage = Math.max(1, this.state.totalPages);
    }
    
    // Get sessions for current page
    const startIndex = (this.state.currentPage - 1) * this.state.pageSize;
    const endIndex = startIndex + this.state.pageSize;
    const paginatedSessions = filteredSessions.slice(startIndex, endIndex);
    
    console.log('[HistoryManager] Paginated sessions for display:', paginatedSessions.length);
    
    // Render sessions
    this.renderSessionsList(paginatedSessions);
    
    // Update pagination controls
    this.updatePaginationControls();
  }

  renderSessionsList(sessions) {
    if (!this.elements.allSessionsList) {
      console.error('[HistoryManager] allSessionsList element not found for rendering');
      return;
    }
    
    console.log('[HistoryManager] Rendering sessions list with', sessions.length, 'sessions');
    
    this.elements.allSessionsList.innerHTML = '';
    
    if (sessions.length === 0) {
      console.log('[HistoryManager] No sessions to display, showing empty state');
      this.elements.allSessionsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">No Sessions Found</div>
          <div class="empty-state-description">Try adjusting your search or filter criteria.</div>
        </div>
      `;
      return;
    }
    
    sessions.forEach((session, index) => {
      console.log(`[HistoryManager] Creating session item ${index + 1}:`, session.session_id);
      const sessionItem = this.createSessionItem(session);
      this.elements.allSessionsList.appendChild(sessionItem);
    });
    
    console.log('[HistoryManager] Sessions list rendered successfully');
  }

  updatePaginationControls() {
    // Update pagination buttons
    if (this.elements.prevPageBtn) {
      this.elements.prevPageBtn.disabled = this.state.currentPage <= 1;
    }
    
    if (this.elements.nextPageBtn) {
      this.elements.nextPageBtn.disabled = this.state.currentPage >= this.state.totalPages;
    }
    
    // Update page info
    if (this.elements.pageInfo) {
      if (this.state.totalPages === 0) {
        this.elements.pageInfo.textContent = 'No results';
      } else {
        this.elements.pageInfo.textContent = `Page ${this.state.currentPage} of ${this.state.totalPages}`;
      }
    }
  }

  // Item Creation Methods
  createTaskItem(task) {
    const item = document.createElement('div');
    item.className = 'recent-task-item';
    
    const sessionId = task.session_id || 'Unknown';
    const taskDesc = task.description || task.task_description || 'No description';
    const timestamp = new Date(task.created_at || task.timestamp || Date.now()).toLocaleString();
    const status = task.status || 'completed';
    
    item.innerHTML = `
      <div class="task-item-header">
        <div class="task-session-id">${sessionId}</div>
        <div class="task-timestamp">${timestamp}</div>
      </div>
      <div class="task-description">${this.truncateText(taskDesc, 100)}</div>
      <div class="task-status">
        <span class="status-dot ${status}"></span>
        <span class="status-text">${status}</span>
      </div>
    `;
    
    item.addEventListener('click', () => {
      this.handleTaskItemClick(task);
    });
    
    return item;
  }

  createSessionItem(session) {
    const item = document.createElement('div');
    item.className = 'session-item';
    
    const sessionId = session.session_id || 'Unknown';
    const createdAt = new Date(session.created_at || session.timestamp || Date.now()).toLocaleString();
    const lastActivity = session.last_activity ? new Date(session.last_activity).toLocaleString() : 'No activity';
    const taskCount = session.task_count || 0;
    const status = session.status || 'active';
    
    item.innerHTML = `
      <div class="session-item-header">
        <div class="session-id">${sessionId}</div>
        <div class="session-timestamp">${createdAt}</div>
      </div>
      <div class="session-details">
        <div class="session-info">
          <span class="session-task-count">${taskCount} task(s)</span>
          <span class="session-last-activity">Last: ${lastActivity}</span>
        </div>
        <div class="session-status">
          <span class="status-dot ${status}"></span>
          <span class="status-text">${status}</span>
        </div>
      </div>
    `;
    
    // Add enhanced click handler with debugging
    item.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.handleSessionItemClick(session);
    });
    
    // Add visual feedback for clickability
    item.style.cursor = 'pointer';
    item.setAttribute('title', `Click to load session: ${sessionId}`);
    
    return item;
  }

  // Click Handlers
  async handleTaskItemClick(task) {
    try {
      console.log('[HistoryManager] Task item clicked:', task.session_id);
      const sessionId = task.session_id;
      if (!sessionId) {
        console.error('[HistoryManager] No session ID found in task data:', task);
        this.emit('error', { message: 'Invalid task - no session ID found' });
        return;
      }
      
      // Close the modal first
      this.hideModal();
      
      // Emit event to load session
      this.emit('loadSession', { sessionId });
      
    } catch (error) {
      console.error('[HistoryManager] Error in handleTaskItemClick:', error);
      this.emit('error', { message: `Failed to load task session: ${error.message}` });
    }
  }

  async handleSessionItemClick(session) {
    try {
      console.log('[HistoryManager] Session item clicked:', session.session_id);
      const sessionId = session.session_id;
      if (!sessionId) {
        console.error('[HistoryManager] No session ID found in session data:', session);
        this.emit('error', { message: 'Invalid session - no session ID found' });
        return;
      }
      
      // Close the modal first
      this.hideModal();
      
      // Emit event to load session
      this.emit('loadSession', { sessionId });
      
    } catch (error) {
      console.error('[HistoryManager] Error in handleSessionItemClick:', error);
      this.emit('error', { message: `Failed to load session: ${error.message}` });
    }
  }

  // Utility Methods
  truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
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

  showModal() {
    if (this.elements.historyModal) {
      this.elements.historyModal.classList.remove('hidden');
      this.elements.historyModal.classList.add('scale-in');
    }
  }

  hideModal() {
    if (this.elements.historyModal) {
      this.elements.historyModal.classList.add('hidden');
      this.elements.historyModal.classList.remove('scale-in');
    }
  }

  // Reset state when modal is closed
  reset() {
    this.state.historyMode = 'recent';
    this.state.currentPage = 1;
    this.state.searchQuery = '';
    this.state.statusFilter = 'all';
    
    if (this.elements.sessionSearch) {
      this.elements.sessionSearch.value = '';
    }
    if (this.elements.sessionFilter) {
      this.elements.sessionFilter.value = 'all';
    }
  }

  // Create a specific history item (can be overridden for custom history items)
  createHistoryItem(session) {
    const item = document.createElement('div');
    item.className = 'history-item';
    
    const createdAt = new Date(session.createdAt || session.lastUpdated).toLocaleString();
    const taskCount = session.taskHistory?.length || 0;
    
    item.innerHTML = `
      <div class="history-item-header">
        <span class="history-session-id">${session.sessionId}</span>
        <span class="history-timestamp">${createdAt}</span>
      </div>
      <div class="history-task">${taskCount} task(s)</div>
      <div class="history-status">
        <span class="status-dot ${session.status || 'active'}"></span>
        ${session.status || 'active'}
      </div>
    `;
    
    item.addEventListener('click', () => {
      this.emit('loadSession', { sessionId: session.sessionId });
      this.hideModal();
    });
    
    return item;
  }

  // Display generic history list (backwards compatibility)
  displayHistoryList(sessions) {
    if (!this.elements.recentTasksList) return;
    
    this.elements.recentTasksList.innerHTML = '';
    
    if (sessions.length === 0) {
      this.elements.recentTasksList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <div class="empty-state-title">No Sessions Found</div>
          <div class="empty-state-description">Create a new session to get started.</div>
        </div>
      `;
    } else {
      sessions.forEach(session => {
        const item = this.createHistoryItem(session);
        this.elements.recentTasksList.appendChild(item);
      });
    }
    
    this.showModal();
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfHistoryManager = VibeSurfHistoryManager;
}