// Session Manager - Handles session lifecycle and activity monitoring
// Manages session creation, activity polling, and history

class VibeSurfSessionManager {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.currentSession = null;
    this.activityLogs = [];
    this.pollingInterval = null;
    this.pollingFrequency = 1000; // 1 second
    this.isPolling = false;
    this.eventListeners = new Map();
    
    this.bindMethods();
  }

  bindMethods() {
    this.handleActivityUpdate = this.handleActivityUpdate.bind(this);
    this.pollActivity = this.pollActivity.bind(this);
  }

  // Event system for UI updates
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.eventListeners.has(event)) {
      const callbacks = this.eventListeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[SessionManager] Event callback error for ${event}:`, error);
        }
      });
    }
  }

  // Session management
  async createSession(prefix = 'vibesurf_') {
    const sessionId = await this.apiClient.generateSessionId(prefix);
    
    this.currentSession = {
      id: sessionId,
      createdAt: new Date().toISOString(),
      status: 'active',
      taskHistory: [],
      currentTask: null
    };

    // Clear previous activity logs
    this.activityLogs = [];


    // Store session in background
    await this.storeSessionData();

    this.emit('sessionCreated', { sessionId, session: this.currentSession });
    
    return sessionId;
  }

  async loadSession(sessionId) {
    try {
      // Stop current polling
      this.stopActivityPolling();


      // Load session data from background
      const response = await chrome.runtime.sendMessage({
        type: 'GET_SESSION_DATA',
        data: { sessionId }
      });


      // Check if response is valid and has sessionData
      if (response && response.sessionData) {
        this.currentSession = {
          id: sessionId,
          ...response.sessionData
        };

        // Load activity logs from backend
        await this.loadSessionActivity();

        this.emit('sessionLoaded', { sessionId, session: this.currentSession });
        
        return true;
      } else if (response && response.error) {
        console.error('[SessionManager] Background error:', response.error);
        this.emit('sessionError', { error: response.error, sessionId });
        return false;
      } else {
        // Session not found in storage - create a new session with this ID
        
        this.currentSession = {
          id: sessionId,
          createdAt: new Date().toISOString(),
          status: 'active',
          taskHistory: [],
          currentTask: null
        };

        // Clear activity logs for new session
        this.activityLogs = [];

        // Try to load any existing activity logs from backend
        await this.loadSessionActivity();

        // Store the new session
        await this.storeSessionData();

        this.emit('sessionLoaded', { sessionId, session: this.currentSession });
        
        return true;
      }
    } catch (error) {
      console.error('[SessionManager] Failed to load session:', error);
      this.emit('sessionError', { error: error.message, sessionId });
      return false;
    }
  }

  async loadSessionActivity() {
    if (!this.currentSession) {
      console.warn('[SessionManager] No current session for activity loading');
      return;
    }

    try {
      const response = await this.apiClient.getSessionActivity(this.currentSession.id);
      
      
      // Check multiple possible response formats
      let activityLogs = null;
      if (response && response.data && response.data.activity_logs) {
        activityLogs = response.data.activity_logs;
      } else if (response && response.activity_logs) {
        activityLogs = response.activity_logs;
      } else if (response && Array.isArray(response)) {
        activityLogs = response;
      }
      
      if (activityLogs && Array.isArray(activityLogs)) {
        this.activityLogs = activityLogs;
        
        
        // Add timestamps to logs that don't have them
        this.activityLogs.forEach(log => {
          if (!log.timestamp) {
            log.timestamp = new Date().toISOString();
          }
        });
        
        this.emit('activityLogsLoaded', {
          sessionId: this.currentSession.id,
          logs: this.activityLogs
        });
      } else {
        // No existing activity logs
        this.activityLogs = [];
        this.lastMessageIndex = 0;
      }
    } catch (error) {
      console.error('[SessionManager] ❌ Failed to load session activity:', error);
      console.error('[SessionManager] Error details:', {
        message: error.message,
        stack: error.stack,
        sessionId: this.currentSession?.id
      });
      // Reset to safe defaults
      this.activityLogs = [];
    }
  }

  getCurrentSession() {
    return this.currentSession;
  }

  getCurrentSessionId() {
    return this.currentSession?.id || null;
  }

  // Task management
  async submitTask(taskData) {
    if (!this.currentSession) {
      throw new Error('No active session. Please create a session first.');
    }

    try {
      // ✅ 改进：提交新任务前先同步session的所有activity logs
      console.log('[SessionManager] 🔄 Syncing activity logs before task submission...');
      await this.syncActivityLogsFromServer();

      const taskPayload = {
        session_id: this.currentSession.id,
        ...taskData
      };

      const response = await this.apiClient.submitTask(taskPayload);
      
      // Update current session with task info
      this.currentSession.currentTask = {
        taskId: response.task_id,
        description: taskData.task_description,
        llmProfile: taskData.llm_profile_name,
        status: 'submitted',
        submittedAt: new Date().toISOString()
      };

      // Start activity polling
      this.startActivityPolling();

      // Store updated session
      await this.storeSessionData();

      this.emit('taskSubmitted', {
        sessionId: this.currentSession.id,
        task: this.currentSession.currentTask,
        response
      });

      return response;
    } catch (error) {
      console.error('[SessionManager] Task submission failed:', error);
      this.emit('taskError', { error: error.message, sessionId: this.currentSession.id });
      throw error;
    }
  }

  async pauseTask(reason = 'User requested pause') {
    try {
      const response = await this.apiClient.pauseTask(reason);
      
      if (this.currentSession?.currentTask) {
        this.currentSession.currentTask.status = 'paused';
        this.currentSession.currentTask.pausedAt = new Date().toISOString();
        await this.storeSessionData();
      }

      // Stop polling when task is paused
      this.stopActivityPolling();

      this.emit('taskPaused', { sessionId: this.currentSession?.id, response });
      
      return response;
    } catch (error) {
      console.error('[SessionManager] Task pause failed:', error);
      this.emit('taskError', { error: error.message, action: 'pause' });
      throw error;
    }
  }

  async resumeTask(reason = 'User requested resume') {
    try {
      const response = await this.apiClient.resumeTask(reason);
      
      if (this.currentSession?.currentTask) {
        this.currentSession.currentTask.status = 'running';
        this.currentSession.currentTask.resumedAt = new Date().toISOString();
        await this.storeSessionData();
      }

      // Restart polling when task is resumed
      this.startActivityPolling();

      this.emit('taskResumed', { sessionId: this.currentSession?.id, response });
      
      return response;
    } catch (error) {
      console.error('[SessionManager] Task resume failed:', error);
      this.emit('taskError', { error: error.message, action: 'resume' });
      throw error;
    }
  }

  async stopTask(reason = 'User requested stop') {
    try {
      const response = await this.apiClient.stopTask(reason);
      
      if (this.currentSession?.currentTask) {
        this.currentSession.currentTask.status = 'stopped';
        this.currentSession.currentTask.stoppedAt = new Date().toISOString();
        await this.storeSessionData();
      }

      // Stop polling when task is stopped
      this.stopActivityPolling();

      this.emit('taskStopped', { sessionId: this.currentSession?.id, response });
      
      return response;
    } catch (error) {
      console.error('[SessionManager] Task stop failed:', error);
      this.emit('taskError', { error: error.message, action: 'stop' });
      throw error;
    }
  }

  // Activity polling
  startActivityPolling() {
    if (this.isPolling) {
      return;
    }

    
    this.isPolling = true;
    // Use arrow function to preserve 'this' context
    this.pollingInterval = setInterval(() => {
      this.pollActivity();
    }, this.pollingFrequency);
    
    this.emit('pollingStarted', { sessionId: this.currentSession?.id });
  }

  stopActivityPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    
    this.isPolling = false;
    this.emit('pollingStopped', { sessionId: this.currentSession?.id });
  }

  async pollActivity() {
    if (!this.currentSession) {
      this.stopActivityPolling();
      return;
    }

    try {
      // ✅ 使用当前logs数量作为message_index，确保获取下一个预期的log
      const requestIndex = this.activityLogs.length;
      
      console.log(`[SessionManager] 🔄 Polling activity at index ${requestIndex}, current logs: ${this.activityLogs.length}`);
      
      // Poll for new activity at the next expected index
      const response = await this.apiClient.pollSessionActivity(
        this.currentSession.id,
        requestIndex
      );

      // Check both possible response formats
      const activityLog = response?.activity_log || response?.data?.activity_log;
      const totalAvailable = response?.total_available || response?.data?.total_available;

      if (response && activityLog) {
        const prevActivityLog = this.activityLogs.length > 0 ? this.activityLogs[this.activityLogs.length - 1] : null;
        
        // 检查是否为新的、不重复的activity log
        const isNewLog = !prevActivityLog || !this.areLogsEqual(prevActivityLog, activityLog);
        
        if (isNewLog) {
          // New activity log received
          const newLog = { ...activityLog };
          
          // Add timestamp if not present
          if (!newLog.timestamp) {
            newLog.timestamp = new Date().toISOString();
          }
          
          this.activityLogs.push(newLog);

          console.log(`[SessionManager] ✅ New activity received: ${newLog.agent_name} - ${newLog.agent_status}`);

          await this.handleActivityUpdate(newLog);

          this.emit('newActivity', {
            sessionId: this.currentSession.id,
            activity: newLog,
            allLogs: this.activityLogs
          });

          // Check if task is completed or terminated
          const terminalStatuses = ['done'];
          
          if (terminalStatuses.includes(newLog.agent_status?.toLowerCase())) {
            this.stopActivityPolling();
            
            if (this.currentSession.currentTask) {
              this.currentSession.currentTask.status = newLog.agent_status;
              this.currentSession.currentTask.completedAt = new Date().toISOString();
              await this.storeSessionData();
            }

            this.emit('taskCompleted', {
              sessionId: this.currentSession.id,
              status: newLog.agent_status,
              finalActivity: newLog
            });
          }
        } else {
          console.log(`[SessionManager] 🔄 Duplicate log detected, skipping`);
        }
      } else {
        // No new activity at this index
        console.log(`[SessionManager] 🔄 No new activity at index ${requestIndex}, waiting...`);
        
        // Check if we're behind based on server total
        if (totalAvailable && totalAvailable > this.activityLogs.length) {
          console.log(`[SessionManager] 🔄 Syncing logs: have ${this.activityLogs.length}, server has ${totalAvailable}`);
          await this.syncActivityLogs();
        }
      }
    } catch (error) {
      // Enhanced error logging for debugging
      console.error(`[SessionManager] ❌ Activity polling error at index ${this.activityLogs.length}:`, {
        error: error.message,
        sessionId: this.currentSession?.id,
        currentLogsLength: this.activityLogs.length,
        stack: error.stack
      });
      
      // Only emit polling errors for non-timeout/not-found errors
      if (!error.message.includes('timeout') && !error.message.includes('No activity log found')) {
        this.emit('pollingError', { error: error.message, sessionId: this.currentSession?.id });
      }
    }
  }

  areLogsEqual(log1, log2) {
    if (!log1 || !log2) return false;
    
    return log1.agent_name === log2.agent_name &&
           log1.agent_status === log2.agent_status &&
           log1.agent_msg === log2.agent_msg;
  }

  async syncActivityLogs() {
    if (!this.currentSession) return;
    
    try {
      
      // Get all activity logs from server
      const response = await this.apiClient.getSessionActivity(this.currentSession.id);
      
      // Check both possible response formats
      const activityLogs = response?.activity_logs || response?.data?.activity_logs;
      
      if (activityLogs) {
        const serverLogs = activityLogs;
        const missingLogs = serverLogs.slice(this.activityLogs.length);
        
        if (missingLogs.length > 0) {
          
          for (const log of missingLogs) {
            // Add timestamp if not present
            if (!log.timestamp) {
              log.timestamp = new Date().toISOString();
            }
            
            this.activityLogs.push(log);
            
            this.emit('newActivity', {
              sessionId: this.currentSession.id,
              activity: log,
              allLogs: this.activityLogs
            });
          }
        }
      }
    } catch (error) {
      console.error(`[SessionManager] ❌ Failed to sync activity logs:`, error);
    }
  }

  async syncActivityLogsFromServer() {
    if (!this.currentSession) return;
    
    try {
      console.log(`[SessionManager] 🔄 Syncing all activity logs from server for session: ${this.currentSession.id}`);
      
      // Get all activity logs from server
      const response = await this.apiClient.getSessionActivity(this.currentSession.id);
      
      // Check both possible response formats
      const serverLogs = response?.activity_logs || response?.data?.activity_logs || [];
      
      if (Array.isArray(serverLogs)) {
        // 完全同步：用服务器端的logs替换本地logs
        const previousCount = this.activityLogs.length;
        
        // 添加timestamp给没有的logs
        const processedLogs = serverLogs.map(log => ({
          ...log,
          timestamp: log.timestamp || new Date().toISOString()
        }));
        
        this.activityLogs = processedLogs;
        
        console.log(`[SessionManager] ✅ Activity logs synced: ${previousCount} -> ${this.activityLogs.length} logs`);
        
        // 触发日志加载事件，让UI更新
        this.emit('activityLogsLoaded', {
          sessionId: this.currentSession.id,
          logs: this.activityLogs
        });
      } else {
        console.log(`[SessionManager] 📝 No activity logs found on server for session: ${this.currentSession.id}`);
        this.activityLogs = [];
      }
    } catch (error) {
      console.error(`[SessionManager] ❌ Failed to sync activity logs from server:`, error);
      // 不抛出错误，允许任务提交继续进行
    }
  }

  async handleActivityUpdate(activityLog) {
    // Update current task status based on activity
    if (this.currentSession?.currentTask && activityLog.agent_status) {
      this.currentSession.currentTask.status = activityLog.agent_status;
      await this.storeSessionData();
    }

    // Store activity in background for persistence
    await chrome.runtime.sendMessage({
      type: 'STORE_SESSION_DATA',
      data: {
        sessionId: this.currentSession.id,
        lastActivity: activityLog,
        activityCount: this.activityLogs.length
      }
    });
  }

  // History management
  async getSessionHistory() {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'GET_SESSION_DATA'
      });

      return response.sessions || [];
    } catch (error) {
      console.error('[SessionManager] Failed to get session history:', error);
      return [];
    }
  }

  async getSessionTasks(sessionId) {
    try {
      const response = await this.apiClient.getSessionTasks(sessionId);
      return response.data?.tasks || [];
    } catch (error) {
      console.error('[SessionManager] Failed to get session tasks:', error);
      return [];
    }
  }

  // Storage helpers
  async storeSessionData() {
    if (!this.currentSession) return;

    try {
      await chrome.runtime.sendMessage({
        type: 'STORE_SESSION_DATA',
        data: {
          sessionId: this.currentSession.id,
          ...this.currentSession,
          activityLogs: this.activityLogs,
          lastUpdated: new Date().toISOString()
        }
      });
    } catch (error) {
      console.error('[SessionManager] Failed to store session data:', error);
    }
  }

  // File management for session
  async uploadFiles(files) {
    if (!this.currentSession) {
      throw new Error('No active session for file upload');
    }

    try {
      const response = await this.apiClient.uploadFiles(files, this.currentSession.id);
      
      this.emit('filesUploaded', {
        sessionId: this.currentSession.id,
        files: response.files
      });

      return response;
    } catch (error) {
      console.error('[SessionManager] File upload failed:', error);
      this.emit('fileUploadError', { error: error.message, sessionId: this.currentSession.id });
      throw error;
    }
  }

  // Cleanup
  destroy() {
    this.stopActivityPolling();
    this.eventListeners.clear();
    this.currentSession = null;
    this.activityLogs = [];
    
  }

  // Status helpers
  isSessionActive() {
    return this.currentSession && this.currentSession.status === 'active';
  }

  hasActiveTask() {
    return this.currentSession?.currentTask && 
           ['submitted', 'running', 'paused'].includes(this.currentSession.currentTask.status);
  }

  getTaskStatus() {
    return this.currentSession?.currentTask?.status || null;
  }

  getActivityLogs() {
    return [...this.activityLogs]; // Return copy
  }

  getLatestActivity() {
    return this.activityLogs[this.activityLogs.length - 1] || null;
  }

}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfSessionManager = VibeSurfSessionManager;
}