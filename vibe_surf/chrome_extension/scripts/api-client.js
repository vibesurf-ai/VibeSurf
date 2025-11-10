// API Client - VibeSurf Backend Communication
// Handles all HTTP requests to the VibeSurf backend API

class VibeSurfAPIClient {
  constructor(baseURL = null) {
    // Use configuration file values as defaults
    const config = window.VIBESURF_CONFIG || {};
    this.baseURL = (baseURL || config.BACKEND_URL || 'http://localhost:9335').replace(/\/$/, ''); // Remove trailing slash
    this.apiPrefix = config.API_PREFIX || '/api';
    this.timeout = config.DEFAULT_TIMEOUT || 30000;
    this.retryAttempts = config.RETRY_ATTEMPTS || 3;
    this.retryDelay = config.RETRY_DELAY || 1000;
  }

  // Utility method to build full URL
  buildURL(endpoint) {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${this.baseURL}${this.apiPrefix}${cleanEndpoint}`;
  }

  // Generic HTTP request method with error handling and retries
  async request(method, endpoint, options = {}) {
    const {
      data,
      params,
      headers = {},
      timeout = this.timeout,
      retries = this.retryAttempts,
      ...fetchOptions
    } = options;

    const url = new URL(this.buildURL(endpoint));
    
    // Add query parameters
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null) {
          url.searchParams.append(key, params[key]);
        }
      });
    }

    const config = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
      signal: AbortSignal.timeout(timeout),
      ...fetchOptions
    };

    // Add body for POST/PUT requests
    if (data && method !== 'GET') {
      if (data instanceof FormData) {
        // Remove Content-Type for FormData (browser will set it with boundary)
        delete config.headers['Content-Type'];
        config.body = data;
      } else {
        config.body = JSON.stringify(data);
      }
    }

    let lastError;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        
        const response = await fetch(url, config);
        
        // Handle different response types
        const contentType = response.headers.get('content-type');
        let responseData;
        
        if (contentType && contentType.includes('application/json')) {
          responseData = await response.json();
        } else {
          responseData = await response.text();
        }

        if (!response.ok) {
          throw new APIError(
            responseData.detail || responseData.message || `HTTP ${response.status}`,
            response.status,
            responseData
          );
        }

        return responseData;

      } catch (error) {
        lastError = error;
        console.error(`[API] ${method} ${url} - Error (attempt ${attempt + 1}):`, error);

        // Don't retry on certain errors
        if (error instanceof APIError) {
          if (error.status >= 400 && error.status < 500) {
            throw error; // Client errors shouldn't be retried
          }
          
          // Don't retry on LLM connection failures
          if (error.data && error.data.error === 'llm_connection_failed') {
            console.log('[API] LLM connection failed - skipping retry');
            throw error;
          }
        }

        // Don't retry on timeout for the last attempt
        if (attempt === retries) {
          break;
        }

        // Wait before retry
        await this.delay(this.retryDelay * (attempt + 1));
      }
    }

    throw lastError;
  }

  // HTTP method helpers
  async get(endpoint, options = {}) {
    return this.request('GET', endpoint, options);
  }

  async post(endpoint, data, options = {}) {
    return this.request('POST', endpoint, { data, ...options });
  }

  async put(endpoint, data, options = {}) {
    return this.request('PUT', endpoint, { data, ...options });
  }

  async delete(endpoint, options = {}) {
    return this.request('DELETE', endpoint, options);
  }

  // Health check - special method that bypasses API prefix
  async healthCheck() {
    try {
      // Build URL without API prefix for health endpoint
      const url = `${this.baseURL}/health`;
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(5000)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      console.log('[API] Health check - Success');
      return { status: 'healthy', data };
    } catch (error) {
      console.error('[API] Health check - Error:', error);
      return { status: 'unhealthy', error: error.message };
    }
  }

  // System status
  async getSystemStatus() {
    return this.get('/status');
  }

  // Task Management APIs
  async submitTask(taskData) {
    const {
      session_id,
      task_description,
      llm_profile_name,
      upload_files_path,
      mcp_server_config,
      agent_mode
    } = taskData;

    return this.post('/tasks/submit', {
      session_id,
      task_description,
      llm_profile_name,
      upload_files_path,
      mcp_server_config,
      agent_mode
    });
  }

  async getTaskStatus() {
    return this.get('/tasks/status');
  }

  async checkTaskRunning() {
    try {
      const status = await this.getTaskStatus();
      
      // console.log('[API] Task status check result:', {
      //   has_active_task: status.has_active_task,
      //   active_task: status.active_task
      // });
      
      // Check if there's an active task and its status
      const hasActiveTask = status.has_active_task;
      const activeTask = status.active_task;
      
      if (!hasActiveTask || !activeTask) {
        return { isRunning: false, taskInfo: null };
      }
      
      // Check if the active task is in a "running" state
      const runningStates = ['running', 'submitted', 'paused'];
      const taskStatus = activeTask.status || '';
      const isRunning = runningStates.includes(taskStatus.toLowerCase());
      
      // console.log('[API] Task running check:', {
      //   taskStatus,
      //   isRunning,
      //   runningStates
      // });
      
      return {
        isRunning,
        taskInfo: hasActiveTask ? activeTask : null
      };
    } catch (error) {
      console.error('[API] Failed to check task status:', error);
      return { isRunning: false, taskInfo: null };
    }
  }

  async pauseTask(reason = 'User requested pause') {
    return this.post('/tasks/pause', { reason });
  }

  async resumeTask(reason = 'User requested resume') {
    return this.post('/tasks/resume', { reason });
  }

  async stopTask(reason = 'User requested stop') {
    return this.post('/tasks/stop', { reason });
  }

  async addNewTask(newTask) {
    return this.post('/tasks/add-new-task', { reason: newTask });
  }

  // Activity APIs
  async getTaskInfo(taskId) {
    return this.get(`/activity/${taskId}`);
  }

  async getSessionTasks(sessionId) {
    return this.get(`/activity/sessions/${sessionId}/tasks`);
  }

  async getSessionActivity(sessionId, params = {}) {
    return this.get(`/activity/sessions/${sessionId}/activity`, { params });
  }

  async getLatestActivity(sessionId) {
    return this.get(`/activity/sessions/${sessionId}/latest_activity`);
  }

  async getRecentTasks(limit = -1) {
    return this.get('/activity/tasks', { params: { limit } });
  }

  async getAllSessions(limit = -1, offset = 0) {
    return this.get('/activity/sessions', { params: { limit, offset } });
  }

  // Real-time activity polling
  async pollSessionActivity(sessionId, messageIndex = null, interval = 1000) {
    const params = messageIndex !== null ? { message_index: messageIndex } : {};
    
    console.log(`[API] Polling session activity:`, {
      sessionId,
      messageIndex,
      params,
      url: `/activity/sessions/${sessionId}/activity`
    });
    
    try {
      const response = await this.getSessionActivity(sessionId, params);
      console.log(`[API] Poll response:`, {
        hasActivityLog: !!response.activity_log,
        messageIndex: response.message_index,
        agentName: response.activity_log?.agent_name,
        agentStatus: response.activity_log?.agent_status
      });
      return response;
    } catch (error) {
      console.error('[API] Activity polling error:', error);
      throw error;
    }
  }

  // File Management APIs
  async uploadFiles(files, sessionId = null) {
    const formData = new FormData();
    
    // Add files
    for (const file of files) {
      formData.append('files', file);
    }
    
    // Add session ID if provided
    if (sessionId) {
      formData.append('session_id', sessionId);
    }

    return this.post('/files/upload', formData);
  }

  async listFiles(sessionId = null, limit = 50, offset = 0) {
    const params = { limit, offset };
    if (sessionId) {
      params.session_id = sessionId;
    }
    
    return this.get('/files', { params });
  }

  async downloadFile(fileId) {
    const url = this.buildURL(`/files/${fileId}`);
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to download file: ${response.status}`);
      }
      
      return response.blob();
    } catch (error) {
      console.error('[API] File download error:', error);
      throw error;
    }
  }

  async deleteFile(fileId) {
    return this.delete(`/files/${fileId}`);
  }

  // Configuration APIs
  async getConfigStatus() {
    return this.get('/config/status');
  }

  // LLM Profile Management
  async getLLMProfiles(activeOnly = true, limit = 50, offset = 0) {
    return this.get('/config/llm-profiles', {
      params: { active_only: activeOnly, limit, offset }
    });
  }

  async getLLMProfile(profileName) {
    return this.get(`/config/llm-profiles/${encodeURIComponent(profileName)}`);
  }

  async createLLMProfile(profileData) {
    return this.post('/config/llm-profiles', profileData);
  }

  async updateLLMProfile(profileName, updateData) {
    return this.put(`/config/llm-profiles/${encodeURIComponent(profileName)}`, updateData);
  }

  async deleteLLMProfile(profileName) {
    return this.delete(`/config/llm-profiles/${encodeURIComponent(profileName)}`);
  }

  async setDefaultLLMProfile(profileName) {
    return this.post(`/config/llm-profiles/${encodeURIComponent(profileName)}/set-default`);
  }

  // MCP Profile Management
  async getMCPProfiles(activeOnly = true, limit = 50, offset = 0) {
    return this.get('/config/mcp-profiles', {
      params: { active_only: activeOnly, limit, offset }
    });
  }

  async getMCPProfile(profileName) {
    return this.get(`/config/mcp-profiles/${encodeURIComponent(profileName)}`);
  }

  async createMCPProfile(profileData) {
    return this.post('/config/mcp-profiles', profileData);
  }

  async updateMCPProfile(profileName, updateData) {
    console.log('[API Client] updateMCPProfile called with profile:', profileName);
    const result = await this.put(`/config/mcp-profiles/${encodeURIComponent(profileName)}`, updateData);
    return result;
  }

  async deleteMCPProfile(profileName) {
    return this.delete(`/config/mcp-profiles/${encodeURIComponent(profileName)}`);
  }

  // LLM Providers and Models
  async getLLMProviders() {
    return this.get('/config/llm/providers');
  }

  async getLLMProviderModels(providerName) {
    return this.get(`/config/llm/providers/${encodeURIComponent(providerName)}/models`);
  }

  // Voice Profile Management
  async getVoiceProfiles(activeOnly = true, voiceModelType = null, limit = 50, offset = 0) {
    const params = { active_only: activeOnly, limit, offset };
    if (voiceModelType) {
      params.voice_model_type = voiceModelType;
    }
    return this.get('/voices/voice-profiles', { params });
  }

  async getVoiceProfile(profileName) {
    return this.get(`/voices/${encodeURIComponent(profileName)}`);
  }

  async createVoiceProfile(profileData) {
    return this.post('/voices/voice-profiles', profileData);
  }

  async updateVoiceProfile(profileName, updateData) {
    return this.put(`/voices/voice-profiles/${encodeURIComponent(profileName)}`, updateData);
  }

  async deleteVoiceProfile(profileName) {
    return this.delete(`/voices/voice-profiles/${encodeURIComponent(profileName)}`);
  }

  // Voice Models - matches the backend route @router.get("/models")
  async getVoiceModels(modelType = null) {
    let url = '/voices/models';
    if (modelType) {
      url += `?model_type=${encodeURIComponent(modelType)}`;
    }
    return this.get(url);
  }

  // Voice Recording API
  async transcribeAudio(audioBlob, voiceProfileName = null) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.webm');
    
    // Add voice profile name if provided
    const params = {};
    if (voiceProfileName) {
      params.voice_profile_name = voiceProfileName;
    }
    
    return this.post('/voices/asr', formData, {
      params,
      headers: {} // Let browser set Content-Type with boundary for FormData
    });
  }

  // Get available ASR profiles
  async getASRProfiles(activeOnly = true) {
    return this.get('/voices/voice-profiles', {
      params: {
        voice_model_type: 'asr',
        active_only: activeOnly
      }
    });
  }

  // Environment Variables
  async getEnvironmentVariables() {
    return this.get('/config/environments');
  }

  async updateEnvironmentVariables(variables) {
    return this.put('/config/environments', { environments: variables });
  }

  // Controller Configuration
  async getControllerConfig() {
    return this.get('/config/controller');
  }

  async updateControllerConfig(configData) {
    return this.put('/config/controller', configData);
  }

  // Browser APIs
  async getActiveBrowserTab() {
    return this.get('/browser/active-tab');
  }

  async getAllBrowserTabs() {
    return this.get('/browser/all-tabs');
  }

  // Agent APIs - Get available skills
  async getAllSkills() {
    return this.get('/agent/get_all_skills');
  }

  // Utility methods
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Update base URL
  setBaseURL(newBaseURL) {
    this.baseURL = newBaseURL.replace(/\/$/, '');
    console.log('[API] Base URL updated to:', this.baseURL);
  }

  // Create a session ID
  // Session ID generation using backend endpoint with fallback
  async generateSessionId(prefix = 'vibesurf_') {
    try {
      // Use backend endpoint for session ID generation
      const response = await fetch(`${this.baseURL}/generate-session-id?prefix=${encodeURIComponent(prefix)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(5000)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      return data.session_id;
    } catch (error) {
      console.warn('[API] Failed to generate session ID from backend, using fallback:', error);
      // Fallback to simple local generation
      const timestamp = Date.now();
      const random = Math.random().toString(36).substr(2, 9);
      return `${prefix}${timestamp}_${random}`;
    }
  }

  // Composio APIs
  async verifyComposioKey(apiKey) {
    return this.post('/composio/verify-key', { api_key: apiKey });
  }

  async getComposioToolkits(params = {}) {
    return this.get('/composio/toolkits', { params });
  }

  async toggleComposioToolkit(slug, enabled) {
    return this.post(`/composio/toolkit/${encodeURIComponent(slug)}/toggle`, { enabled });
  }

  async getComposioToolkitTools(slug) {
    return this.get(`/composio/toolkit/${encodeURIComponent(slug)}/tools`);
  }

  async updateComposioToolkitTools(slug, selectedTools) {
    console.log(`[APIClient] Updating toolkit tools for ${slug}:`, selectedTools);
    const response = await this.post(`/composio/toolkit/${encodeURIComponent(slug)}/tools`, { selected_tools: selectedTools });
    console.log(`[APIClient] Update toolkit tools response:`, response);
    return response;
  }

  async getComposioToolkitConnectionStatus(slug) {
    return this.get(`/composio/toolkit/${encodeURIComponent(slug)}/connection-status`);
  }

  async getComposioStatus() {
    return this.get('/composio/status');
  }

  // VibeSurf API Key Management
  async verifyVibeSurfKey(apiKey) {
    return this.post('/vibesurf/verify-key', { api_key: apiKey });
  }

  async getVibeSurfStatus() {
    return this.get('/vibesurf/status');
  }

  async deleteVibeSurfKey() {
    return this.delete('/vibesurf/key');
  }

  async validateVibeSurfKey() {
    return this.get('/vibesurf/validate');
  }

  // Workflow Management APIs (Langflow integration)
  async getWorkflows() {
    // Match the exact parameters from working curl command
    const params = {
      remove_example_flows: true,
      components_only: false,
      get_all: true
    };
    
    return this.get('/v1/flows/', { params });
  }

  async runWorkflow(flowId) {
    return this.post(`/v1/build/${encodeURIComponent(flowId)}/flow`, {});
  }

  async cancelWorkflow(jobId) {
    return this.post(`/v1/build/${encodeURIComponent(jobId)}/cancel`, {});
  }

  async getWorkflowEvents(jobId) {
    return this.get(`/v1/build/${encodeURIComponent(jobId)}/events`);
  }

  async getWorkflow(flowId) {
    return this.get(`/v1/flows/${encodeURIComponent(flowId)}`);
  }

  async deleteWorkflow(flowId) {
    return this.delete(`/v1/flows/${encodeURIComponent(flowId)}`);
  }

  async exportWorkflow(flowId) {
    return this.get(`/vibesurf/export-workflow/${encodeURIComponent(flowId)}`);
  }

  // Schedule Management APIs - using flow_id for simplicity
  async getSchedules() {
    return this.get('/schedule');
  }

  async createSchedule(scheduleData) {
    return this.post('/schedule', scheduleData);
  }

  async updateSchedule(flowId, scheduleData) {
    return this.put(`/schedule/${encodeURIComponent(flowId)}`, scheduleData);
  }

  async deleteSchedule(flowId) {
    return this.delete(`/schedule/${encodeURIComponent(flowId)}`);
  }

  async getSchedule(flowId) {
    return this.get(`/schedule/${encodeURIComponent(flowId)}`);
  }

  // Get projects list to obtain folder_id
  async getProjects() {
    return this.get('/v1/projects/');
  }

  // Generate UUID from backend
  async generateUUID() {
    return this.get('/vibesurf/generate-uuid');
  }

  // Create new workflow
  async createWorkflow(workflowData) {
    // Use the specific endpoint that langflow expects
    const url = `${this.baseURL}/api/v1/flows/`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(workflowData),
        signal: AbortSignal.timeout(this.timeout)
      });
      
      if (!response.ok) {
        const errorData = await response.text();
        throw new APIError(
          `Failed to create workflow: ${response.status}`,
          response.status,
          errorData
        );
      }
      
      const responseData = await response.json();
      return responseData;
    } catch (error) {
      throw error;
    }
  }

  // Import workflow from JSON string
  async importWorkflow(workflowJson) {
    return this.post('/vibesurf/import-workflow', { workflow_json: workflowJson });
  }

  // Get VibeSurf backend version
  async getVibeSurfVersion() {
    return this.get('/vibesurf/version');
  }
}

// Custom error class for API errors
class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfAPIClient = VibeSurfAPIClient;
  window.APIError = APIError;
}