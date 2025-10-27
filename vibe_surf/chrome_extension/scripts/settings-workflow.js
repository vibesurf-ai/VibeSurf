// Settings Workflow Manager - Handles tab and skill selector workflows
// Extracted from ui-manager.js to improve code organization

class VibeSurfSettingsWorkflow {
  constructor(uiManager, apiClient) {
    this.uiManager = uiManager;
    this.apiClient = apiClient;
    this.elements = {};
    
    // Initialize workflow states
    this.tabSelectorState = {
      isVisible: false,
      selectedTabs: [],
      allTabs: [],
      atPosition: -1 // Position where @ was typed
    };

    this.skillSelectorState = {
      isVisible: false,
      selectedSkills: [],
      allSkills: [],
      slashPosition: -1, // Position where / was typed
      currentFilter: '', // Current filter text after /
      filteredSkills: [] // Filtered skills based on current input
    };

    this.bindElements();
    this.initializeTabSelector();
    this.initializeSkillSelector();
  }

  bindElements() {
    // Bind workflow-related elements
    this.elements = {
      // Tab selector elements
      tabSelectorDropdown: document.getElementById('tab-selector-dropdown'),
      tabSelectorCancel: document.getElementById('tab-selector-cancel'),
      tabSelectorConfirm: document.getElementById('tab-selector-confirm'),
      selectAllTabs: document.getElementById('select-all-tabs'),
      tabOptionsList: document.getElementById('tab-options-list'),
      
      // Skill selector elements
      skillSelectorDropdown: document.getElementById('skill-selector-dropdown'),
      skillOptionsList: document.getElementById('skill-options-list'),
      
      // Task input (shared with ui-manager)
      taskInput: document.getElementById('task-input')
    };
  }

  // Tab Selector Methods
  initializeTabSelector() {
    console.log('[SettingsWorkflow] Initializing tab selector');
    
    // Initialize tab selector state
    this.tabSelectorState = {
      isVisible: false,
      selectedTabs: [],
      allTabs: [],
      atPosition: -1 // Position where @ was typed
    };

    console.log('[SettingsWorkflow] Tab selector initialized');
    
    // Bind tab selector events
    this.bindTabSelectorEvents();
  }

  bindTabSelectorEvents() {
    console.log('[SettingsWorkflow] Binding tab selector events');
    
    // Select all radio button
    this.elements.selectAllTabs?.addEventListener('change', this.handleSelectAllTabs.bind(this));
    
    // Hide on click outside
    document.addEventListener('click', (event) => {
      if (this.tabSelectorState.isVisible &&
          this.elements.tabSelectorDropdown &&
          !this.elements.tabSelectorDropdown.contains(event.target) &&
          !this.elements.taskInput?.contains(event.target)) {
        this.hideTabSelector();
      }
    });
    
    console.log('[SettingsWorkflow] Tab selector events bound');
  }

  handleTabSelectorInput(event) {
    // Safety check - ensure tab selector state is initialized
    if (!this.tabSelectorState) {
      console.warn('[SettingsWorkflow] Tab selector state not initialized');
      return;
    }
    
    const inputValue = event.target.value;
    const cursorPosition = event.target.selectionStart;
    
    console.log('[SettingsWorkflow] Tab selector input:', inputValue[cursorPosition - 1]);
    
    // Check if @ was just typed
    if (inputValue[cursorPosition - 1] === '@') {
      console.log('[SettingsWorkflow] @ detected, showing tab selector');
      this.tabSelectorState.atPosition = cursorPosition - 1;
      this.showTabSelector();
    } else if (this.tabSelectorState.isVisible) {
      // Check if @ was deleted - hide tab selector immediately
      if (this.tabSelectorState.atPosition >= 0 &&
          (this.tabSelectorState.atPosition >= inputValue.length ||
           inputValue[this.tabSelectorState.atPosition] !== '@')) {
        console.log('[SettingsWorkflow] @ deleted, hiding tab selector');
        this.hideTabSelector();
        return;
      }
      
      // Hide tab selector if user continues typing after @
      const textAfterAt = inputValue.substring(this.tabSelectorState.atPosition + 1, cursorPosition);
      if (textAfterAt.length > 0 && !textAfterAt.match(/^[\s]*$/)) {
        console.log('[SettingsWorkflow] Text after @, hiding tab selector');
        this.hideTabSelector();
      }
    }
  }

  async showTabSelector() {
    console.log('[SettingsWorkflow] Attempting to show tab selector');
    
    if (!this.elements.tabSelectorDropdown || !this.elements.taskInput) {
      console.error('[SettingsWorkflow] Tab selector elements not found', {
        dropdown: this.elements.tabSelectorDropdown,
        taskInput: this.elements.taskInput
      });
      return;
    }

    try {
      console.log('[SettingsWorkflow] Populating tab selector');
      // Fetch tab data from backend
      await this.populateTabSelector();
      
      console.log('[SettingsWorkflow] Positioning tab selector');
      // Position the dropdown relative to the input
      this.positionTabSelector();
      
      console.log('[SettingsWorkflow] Making tab selector visible');
      // Show the dropdown with explicit visibility
      this.elements.tabSelectorDropdown.classList.remove('hidden');
      this.elements.tabSelectorDropdown.style.display = 'block';
      this.elements.tabSelectorDropdown.style.visibility = 'visible';
      this.elements.tabSelectorDropdown.style.opacity = '1';
      this.tabSelectorState.isVisible = true;
      
      console.log('[SettingsWorkflow] Tab selector now visible');
      
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to show tab selector:', error);
      this.uiManager.showNotification('Failed to load browser tabs', 'error');
    }
  }

  hideTabSelector() {
    if (this.elements.tabSelectorDropdown) {
      this.elements.tabSelectorDropdown.classList.add('hidden');
      this.elements.tabSelectorDropdown.style.display = 'none'; // Ensure it's hidden
    }
    this.tabSelectorState.isVisible = false;
    this.tabSelectorState.selectedTabs = [];
    this.tabSelectorState.atPosition = -1;
    
    console.log('[SettingsWorkflow] Tab selector hidden');
  }

  positionTabSelector() {
    if (!this.elements.tabSelectorDropdown || !this.elements.taskInput) return;
    
    const inputRect = this.elements.taskInput.getBoundingClientRect();
    const dropdown = this.elements.tabSelectorDropdown;
    
    console.log('[SettingsWorkflow] Positioning tab selector dropdown');
    
    // Calculate 90% width of input
    const dropdownWidth = inputRect.width * 0.9;
    
    // Position dropdown ABOVE the input (not below)
    dropdown.style.position = 'fixed';
    dropdown.style.bottom = `${window.innerHeight - inputRect.top + 5}px`; // Above the input
    dropdown.style.left = `${inputRect.left + (inputRect.width - dropdownWidth) / 2}px`; // Centered
    dropdown.style.width = `${dropdownWidth}px`; // 80% of input width
    dropdown.style.zIndex = '9999';
    dropdown.style.maxHeight = '300px';
    dropdown.style.overflowY = 'auto';
    
    console.log('[SettingsWorkflow] Tab selector positioned');
  }

  async populateTabSelector() {
    try {
      console.log('[SettingsWorkflow] Fetching tabs from backend');
      // Get all tabs and active tab from backend
      const [allTabsResponse, activeTabResponse] = await Promise.all([
        this.apiClient.getAllBrowserTabs(),
        this.apiClient.getActiveBrowserTab()
      ]);
      
      console.log('[SettingsWorkflow] Tabs response:', allTabsResponse);
      console.log('[SettingsWorkflow] Active tab response:', activeTabResponse);
      
      const allTabs = allTabsResponse.tabs || allTabsResponse || {};
      const activeTab = activeTabResponse.tab || activeTabResponse || {};
      const activeTabId = Object.keys(activeTab)[0];
      
      console.log('[SettingsWorkflow] Processing tabs data');
      console.log('[SettingsWorkflow] All tabs:', allTabs);
      
      this.tabSelectorState.allTabs = allTabs;
      
      // Clear existing options
      if (this.elements.tabOptionsList) {
        this.elements.tabOptionsList.innerHTML = '';
        console.log('[SettingsWorkflow] Cleared existing tab options');
      } else {
        console.error('[SettingsWorkflow] tabOptionsList element not found!');
        return;
      }
      
      // Add fallback test data if no tabs returned
      if (Object.keys(allTabs).length === 0) {
        console.warn('[SettingsWorkflow] No tabs returned from API, adding test data for debugging');
        const testTabs = {
          'test-1': { title: 'Test Tab 1', url: 'https://example.com' },
          'test-2': { title: 'Test Tab 2', url: 'https://google.com' },
          'test-3': { title: 'Very Long Tab Title That Should Be Truncated', url: 'https://github.com' }
        };
        
        Object.entries(testTabs).forEach(([tabId, tabInfo]) => {
          const isActive = tabId === 'test-1';
          
          const option = this.createTabOption(tabId, tabInfo, isActive);
          this.elements.tabOptionsList.appendChild(option);
        });
        
        this.tabSelectorState.allTabs = testTabs;
      } else {
        // Add real tab options
        Object.entries(allTabs).forEach(([tabId, tabInfo]) => {
          const isActive = tabId === activeTabId;
          
          const option = this.createTabOption(tabId, tabInfo, isActive);
          this.elements.tabOptionsList.appendChild(option);
        });
      }
      
      // Reset select all checkbox
      if (this.elements.selectAllTabs) {
        this.elements.selectAllTabs.checked = false;
      }
      
      console.log('[SettingsWorkflow] Tab selector populated');
    } catch (error) {
      console.error('[SettingsWorkflow] Failed to populate tab selector:', error);
      throw error;
    }
  }

  createTabOption(tabId, tabInfo, isActive) {
    const option = document.createElement('div');
    option.className = `tab-option ${isActive ? 'active-tab' : ''}`;
    option.dataset.tabId = tabId;
    
    // Format title (first 20 characters)
    const displayTitle = tabInfo.title ?
      (tabInfo.title.length > 20 ? tabInfo.title.substring(0, 20) + '...' : tabInfo.title) :
      'Unknown Title';
    
    option.innerHTML = `
      <input type="radio" class="tab-radio" id="tab-${tabId}" name="tab-selection" value="${tabId}">
      <label for="tab-${tabId}" class="tab-label">
        <span class="tab-id">${tabId}:</span>
        <span class="tab-title">${this.escapeHtml(displayTitle)}</span>
        ${isActive ? '<span class="active-indicator">(Active)</span>' : ''}
      </label>
    `;
    
    // Add change event to radio button for auto-confirm
    const radio = option.querySelector('.tab-radio');
    radio?.addEventListener('change', this.handleTabSelection.bind(this));
    
    return option;
  }

  handleTabSelection(event) {
    const tabId = event.target.value;
    
    if (event.target.checked) {
      // For radio buttons, replace the selected tabs array with just this tab
      this.tabSelectorState.selectedTabs = [tabId];
      
      console.log('[SettingsWorkflow] Tab selected:', tabId);
      
      // Auto-confirm selection immediately
      this.confirmTabSelection();
    }
  }

  handleSelectAllTabs(event) {
    if (event.target.checked) {
      // "Select All" means list all tabs in the input
      const allTabIds = Object.keys(this.tabSelectorState.allTabs);
      this.tabSelectorState.selectedTabs = allTabIds;
      
      console.log('[SettingsWorkflow] All tabs selected:', allTabIds);
      
      // Auto-confirm selection immediately
      this.confirmTabSelection();
    }
  }

  updateSelectAllState() {
    if (!this.elements.selectAllTabs || !this.elements.tabOptionsList) return;
    
    const checkboxes = this.elements.tabOptionsList.querySelectorAll('.tab-checkbox');
    const checkedBoxes = this.elements.tabOptionsList.querySelectorAll('.tab-checkbox:checked');
    
    if (checkboxes.length === 0) {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = false;
    } else if (checkedBoxes.length === checkboxes.length) {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = true;
    } else if (checkedBoxes.length > 0) {
      this.elements.selectAllTabs.indeterminate = true;
      this.elements.selectAllTabs.checked = false;
    } else {
      this.elements.selectAllTabs.indeterminate = false;
      this.elements.selectAllTabs.checked = false;
    }
  }

  confirmTabSelection() {
    if (this.tabSelectorState.selectedTabs.length === 0) {
      this.uiManager.showNotification('Please select at least one tab', 'warning');
      return;
    }
    
    // Replace @ with selected tabs information
    this.insertSelectedTabsIntoInput();
    
    // Hide the selector
    this.hideTabSelector();
    
    console.log(`[SettingsWorkflow] ${this.tabSelectorState.selectedTabs.length} tab(s) selected and confirmed`);
  }

  insertSelectedTabsIntoInput() {
    if (!this.elements.taskInput) return;
    
    const input = this.elements.taskInput;
    const currentValue = input.value;
    const atPosition = this.tabSelectorState.atPosition;
    
    // Use special Unicode characters as boundaries for easy deletion
    const TAB_START_MARKER = '\u200B'; // Zero-width space
    const TAB_END_MARKER = '\u200C'; // Zero-width non-joiner
    
    // Create tab information string in new format: @ tab_id: title[:20]
    const selectedTabsInfo = this.tabSelectorState.selectedTabs.map(tabId => {
      const tabInfo = this.tabSelectorState.allTabs[tabId];
      const displayTitle = tabInfo?.title ?
        (tabInfo.title.length > 20 ? tabInfo.title.substring(0, 20) + '...' : tabInfo.title) :
        'Unknown';
      return `${TAB_START_MARKER}@ ${tabId}: ${displayTitle}${TAB_END_MARKER}`;
    }).join(' ');
    
    // Replace @ with tab selection (preserve the @ symbol)
    const beforeAt = currentValue.substring(0, atPosition);
    const afterAt = currentValue.substring(atPosition + 1);
    const newValue = `${beforeAt}${selectedTabsInfo} ${afterAt}`;
    
    input.value = newValue;
    
    // Trigger input change event for validation
    this.uiManager.handleTaskInputChange({ target: input });
    
    // Set cursor position after the inserted text
    const newCursorPosition = beforeAt.length + selectedTabsInfo.length + 1; // Add space
    input.setSelectionRange(newCursorPosition, newCursorPosition);
    input.focus();
  }

  getSelectedTabsForTask() {
    // Return selected tabs information for task submission
    if (this.tabSelectorState.selectedTabs.length === 0) {
      return null;
    }
    
    const selectedTabsData = {};
    this.tabSelectorState.selectedTabs.forEach(tabId => {
      const tabInfo = this.tabSelectorState.allTabs[tabId];
      if (tabInfo) {
        selectedTabsData[tabId] = {
          url: tabInfo.url,
          title: tabInfo.title
        };
      }
    });
    
    return selectedTabsData;
  }

  // Tab Token Deletion Handler
  handleTabTokenDeletion(event) {
    const input = event.target;
    const cursorPos = input.selectionStart;
    const text = input.value;
    
    // Unicode markers for tab tokens
    const startMarker = '\u200B'; // Zero-width space
    const endMarker = '\u200C';   // Zero-width non-joiner
    
    let tokenStart = -1;
    let tokenEnd = -1;
    
    if (event.key === 'Backspace') {
      // Only delete if cursor is directly adjacent to end of token
      // Check if the character immediately before cursor is an endMarker
      if (cursorPos > 0 && text[cursorPos - 1] === endMarker) {
        tokenEnd = cursorPos; // Include the marker
        // Find the corresponding start marker backwards
        for (let j = cursorPos - 2; j >= 0; j--) {
          if (text[j] === startMarker) {
            tokenStart = j;
            break;
          }
        }
      }
    } else if (event.key === 'Delete') {
      // Only delete if cursor is directly adjacent to start of token
      // Check if the character immediately at cursor is a startMarker
      if (cursorPos < text.length && text[cursorPos] === startMarker) {
        tokenStart = cursorPos;
        // Find the corresponding end marker forwards
        for (let j = cursorPos + 1; j < text.length; j++) {
          if (text[j] === endMarker) {
            tokenEnd = j + 1; // Include the marker
            break;
          }
        }
      }
    }
    
    // If we found a complete token, delete it
    if (tokenStart !== -1 && tokenEnd !== -1) {
      const beforeToken = text.substring(0, tokenStart);
      const afterToken = text.substring(tokenEnd);
      input.value = beforeToken + afterToken;
      input.setSelectionRange(tokenStart, tokenStart);
      
      // Trigger input change event for validation
      this.uiManager.handleTaskInputChange({ target: input });
      
      return true; // Prevent default behavior
    }
    
    return false; // Allow default behavior
  }

  // Skill Selector Methods
  initializeSkillSelector() {
    // Initialize skill selector state
    this.skillSelectorState = {
      isVisible: false,
      selectedSkills: [],
      allSkills: [],
      slashPosition: -1, // Position where / was typed
      currentFilter: '', // Current filter text after /
      filteredSkills: [] // Filtered skills based on current input
    };

    // Bind skill selector events
    this.bindSkillSelectorEvents();
  }

  bindSkillSelectorEvents() {
    // Hide on click outside
    document.addEventListener('click', (event) => {
      if (this.skillSelectorState.isVisible &&
          this.elements.skillSelectorDropdown &&
          !this.elements.skillSelectorDropdown.contains(event.target) &&
          !this.elements.taskInput?.contains(event.target)) {
        this.hideSkillSelector();
      }
    });
  }

  handleSkillSelectorInput(event) {
    // Safety check - ensure skill selector state is initialized
    if (!this.skillSelectorState) {
      console.warn('[SettingsWorkflow] Skill selector state not initialized');
      return;
    }

    const inputValue = event.target.value;
    const cursorPosition = event.target.selectionStart;

    // Check if / was just typed
    if (inputValue[cursorPosition - 1] === '/') {
      this.skillSelectorState.slashPosition = cursorPosition - 1;
      this.skillSelectorState.currentFilter = '';
      this.showSkillSelector();
    } else if (this.skillSelectorState.isVisible) {
      // Check if / was deleted - hide skill selector immediately
      if (this.skillSelectorState.slashPosition >= 0 &&
          (this.skillSelectorState.slashPosition >= inputValue.length ||
           inputValue[this.skillSelectorState.slashPosition] !== '/')) {
        this.hideSkillSelector();
        return;
      }

      // Update filter based on text after /
      const textAfterSlash = inputValue.substring(this.skillSelectorState.slashPosition + 1, cursorPosition);
      
      // Only consider text up to the next space or special character
      const filterText = textAfterSlash.split(/[\s@]/)[0];
      
      if (this.skillSelectorState.currentFilter !== filterText) {
        this.skillSelectorState.currentFilter = filterText;
        this.filterSkills();
      }

      // Hide skill selector if user typed a space or moved past the skill context
      if (textAfterSlash.includes(' ') || textAfterSlash.includes('@')) {
        this.hideSkillSelector();
      }
    }
  }

  async showSkillSelector() {
    if (!this.elements.skillSelectorDropdown || !this.elements.taskInput) {
      console.error('[SettingsWorkflow] Skill selector elements not found', {
        dropdown: this.elements.skillSelectorDropdown,
        taskInput: this.elements.taskInput
      });
      return;
    }

    try {
      // Fetch skill data from backend if not already cached
      if (this.skillSelectorState.allSkills.length === 0) {
        await this.populateSkillSelector();
      }

      // Filter skills based on current input
      this.filterSkills();

      // Position the dropdown relative to the input
      this.positionSkillSelector();

      // Show the dropdown with explicit visibility
      this.elements.skillSelectorDropdown.classList.remove('hidden');
      this.elements.skillSelectorDropdown.style.display = 'block';
      this.elements.skillSelectorDropdown.style.visibility = 'visible';
      this.elements.skillSelectorDropdown.style.opacity = '1';
      this.skillSelectorState.isVisible = true;

    } catch (error) {
      console.error('[SettingsWorkflow] Failed to show skill selector:', error);
      this.uiManager.showNotification('Failed to load skills', 'error');
    }
  }

  hideSkillSelector() {
    if (this.elements.skillSelectorDropdown) {
      this.elements.skillSelectorDropdown.classList.add('hidden');
      this.elements.skillSelectorDropdown.style.display = 'none';
    }
    this.skillSelectorState.isVisible = false;
    this.skillSelectorState.slashPosition = -1;
    this.skillSelectorState.currentFilter = '';
    this.skillSelectorState.filteredSkills = [];
  }

  positionSkillSelector() {
    if (!this.elements.skillSelectorDropdown || !this.elements.taskInput) return;

    const inputRect = this.elements.taskInput.getBoundingClientRect();
    const dropdown = this.elements.skillSelectorDropdown;

    // Calculate 90% width of input
    const dropdownWidth = inputRect.width * 0.9;

    // Position dropdown ABOVE the input (not below)
    dropdown.style.position = 'fixed';
    dropdown.style.bottom = `${window.innerHeight - inputRect.top + 5}px`; // Above the input
    dropdown.style.left = `${inputRect.left + (inputRect.width - dropdownWidth) / 2}px`; // Centered
    dropdown.style.width = `${dropdownWidth}px`; // 90% of input width
    dropdown.style.zIndex = '9999';
    dropdown.style.maxHeight = '300px';
    dropdown.style.overflowY = 'auto';
  }

  async populateSkillSelector() {
    try {
      console.log('[SettingsWorkflow] Fetching skills from backend...');
      // Get all skills from backend
      const skills = await this.apiClient.getAllSkills();

      console.log('[SettingsWorkflow] Skills received from backend:', skills);

      if (!skills || !Array.isArray(skills) || skills.length === 0) {
        console.warn('[SettingsWorkflow] No skills returned from backend');
        this.skillSelectorState.allSkills = [];
        return;
      }

      this.skillSelectorState.allSkills = skills.map(skillName => ({
        name: skillName,
        displayName: skillName // Keep original skill name without transformation
      }));
      console.log('[SettingsWorkflow] Processed skills:', this.skillSelectorState.allSkills);

    } catch (error) {
      console.error('[SettingsWorkflow] Failed to populate skill selector:', error);
      console.error('[SettingsWorkflow] Error details:', {
        message: error.message,
        stack: error.stack,
        response: error.response,
        data: error.data
      });

      // Show error to user
      this.uiManager.showNotification(`Failed to load skills: ${error.message}`, 'error');

      // Set empty array instead of fallback test data
      this.skillSelectorState.allSkills = [];
    }
  }

  filterSkills() {
    const filter = this.skillSelectorState.currentFilter.toLowerCase();
    
    if (!filter) {
      this.skillSelectorState.filteredSkills = this.skillSelectorState.allSkills;
    } else {
      this.skillSelectorState.filteredSkills = this.skillSelectorState.allSkills.filter(skill =>
        skill.name.toLowerCase().startsWith(filter) ||
        skill.displayName.toLowerCase().startsWith(filter)
      );
    }

    this.renderSkillOptions();
  }

  renderSkillOptions() {
    if (!this.elements.skillOptionsList) return;

    // Clear existing options
    this.elements.skillOptionsList.innerHTML = '';

    if (this.skillSelectorState.filteredSkills.length === 0) {
      const noResults = document.createElement('div');
      noResults.className = 'skill-option';
      noResults.innerHTML = '<span class="skill-name">No skills found</span>';
      noResults.style.opacity = '0.6';
      noResults.style.cursor = 'not-allowed';
      this.elements.skillOptionsList.appendChild(noResults);
      return;
    }

    // Add skill options
    this.skillSelectorState.filteredSkills.forEach((skill, index) => {
      const option = this.createSkillOption(skill, index);
      this.elements.skillOptionsList.appendChild(option);
    });
  }

  createSkillOption(skill, index) {
    const option = document.createElement('div');
    option.className = 'skill-option';
    option.dataset.skillName = skill.name;
    option.dataset.skillIndex = index;

    option.innerHTML = `
      <span class="skill-name">${this.escapeHtml(skill.displayName)}</span>
    `;

    // Add click event for skill selection
    option.addEventListener('click', () => {
      this.selectSkill(skill);
    });

    return option;
  }

  selectSkill(skill) {
    if (!this.elements.taskInput) return;

    const input = this.elements.taskInput;
    const currentValue = input.value;
    const slashPosition = this.skillSelectorState.slashPosition;

    // Use special Unicode characters as boundaries for easy deletion
    const SKILL_START_MARKER = '\u200D'; // Zero-width joiner
    const SKILL_END_MARKER = '\u200E';   // Left-to-right mark

    // Create skill information string
    const skillInfo = `${SKILL_START_MARKER}/${skill.name}${SKILL_END_MARKER}`;

    // Replace / with skill selection
    const beforeSlash = currentValue.substring(0, slashPosition);
    const afterSlash = currentValue.substring(slashPosition + 1 + this.skillSelectorState.currentFilter.length);
    const newValue = `${beforeSlash}${skillInfo} ${afterSlash}`;

    input.value = newValue;

    // Trigger input change event for validation
    this.uiManager.handleTaskInputChange({ target: input });

    // Set cursor position after the inserted text
    const newCursorPosition = beforeSlash.length + skillInfo.length + 1;
    input.setSelectionRange(newCursorPosition, newCursorPosition);
    input.focus();

    // Hide the selector
    this.hideSkillSelector();
  }

  getSelectedSkillsForTask() {
    if (!this.elements.taskInput) return null;

    const inputValue = this.elements.taskInput.value;
    const SKILL_START_MARKER = '\u200D'; // Zero-width joiner
    const SKILL_END_MARKER = '\u200E';   // Left-to-right mark

    const skills = [];
    let startIndex = 0;

    while ((startIndex = inputValue.indexOf(SKILL_START_MARKER, startIndex)) !== -1) {
      const endIndex = inputValue.indexOf(SKILL_END_MARKER, startIndex);
      if (endIndex !== -1) {
        const skillText = inputValue.substring(startIndex + 1, endIndex);
        if (skillText.startsWith('/')) {
          skills.push(skillText.substring(1)); // Remove the / prefix
        }
        startIndex = endIndex + 1;
      } else {
        break;
      }
    }

    return skills.length > 0 ? skills : null;
  }

  // Skill Token Deletion Handler
  handleSkillTokenDeletion(event) {
    const input = event.target;
    const cursorPos = input.selectionStart;
    const text = input.value;
    
    // Unicode markers for skill tokens
    const startMarker = '\u200D'; // Zero-width joiner
    const endMarker = '\u200E';   // Left-to-right mark
    
    let tokenStart = -1;
    let tokenEnd = -1;
    
    if (event.key === 'Backspace') {
      // Only delete if cursor is directly adjacent to end of token
      if (cursorPos > 0 && text[cursorPos - 1] === endMarker) {
        tokenEnd = cursorPos; // Include the marker
        // Find the corresponding start marker backwards
        for (let j = cursorPos - 2; j >= 0; j--) {
          if (text[j] === startMarker) {
            tokenStart = j;
            break;
          }
        }
      }
    } else if (event.key === 'Delete') {
      // Only delete if cursor is directly adjacent to start of token
      if (cursorPos < text.length && text[cursorPos] === startMarker) {
        tokenStart = cursorPos;
        // Find the corresponding end marker forwards
        for (let j = cursorPos + 1; j < text.length; j++) {
          if (text[j] === endMarker) {
            tokenEnd = j + 1; // Include the marker
            break;
          }
        }
      }
    }
    
    // If we found a complete token, delete it
    if (tokenStart !== -1 && tokenEnd !== -1) {
      const beforeToken = text.substring(0, tokenStart);
      const afterToken = text.substring(tokenEnd);
      input.value = beforeToken + afterToken;
      input.setSelectionRange(tokenStart, tokenStart);
      
      // Trigger input change event for validation
      this.uiManager.handleTaskInputChange({ target: input });
      
      return true; // Prevent default behavior
    }
    
    return false; // Allow default behavior
  }

  // Utility methods
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Export for use in other modules
  static exportToWindow() {
    if (typeof window !== 'undefined') {
      window.VibeSurfSettingsWorkflow = VibeSurfSettingsWorkflow;
    }
  }
}

// Call the export method
VibeSurfSettingsWorkflow.exportToWindow();