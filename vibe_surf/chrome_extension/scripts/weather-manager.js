// Weather Manager - Handles weather data fetching and display

class WeatherManager {
  constructor(apiClient) {
    this.apiClient = apiClient;
    this.container = document.getElementById('weather-widget');
    this.weatherData = null;
    
    // We'll initialize when the container is available
    if (this.container) {
      this.initialize();
    } else {
      console.warn('[WeatherManager] Container #weather-widget not found during construction');
    }
  }

  async initialize() {
    console.log('[WeatherManager] Initializing...');
    await this.fetchWeather();
  }

  // Allow re-initialization if container is added dynamically
  checkContainer() {
    const newContainer = document.getElementById('weather-widget');
    if (newContainer) {
      console.log('[WeatherManager] Found weather widget container');
      this.container = newContainer;
      // Only fetch if we don't have data or if the container was empty
      if (!this.weatherData || this.container.children.length === 0) {
        this.fetchWeather();
      } else {
        // Re-render existing data
        this.renderWeather(this.weatherData);
      }
    } else {
      console.warn('[WeatherManager] Container #weather-widget not found');
    }
  }

  async fetchWeather() {
    if (!this.container) {
      console.warn('[WeatherManager] Cannot fetch weather: container not found');
      return;
    }
    
    try {
      console.log('[WeatherManager] Fetching weather data...');
      this.renderLoading();
      const data = await this.apiClient.getWeather();
      console.log('[WeatherManager] Weather data received:', data);
      this.weatherData = data;
      this.renderWeather(data);
    } catch (error) {
      console.error('[WeatherManager] Failed to fetch weather:', error);
      this.renderError(error.message);
    }
  }

  getWeatherIcon(condition) {
    // Map weather conditions to icons (updated for open-meteo.com conditions)
    const conditionLower = condition.toLowerCase();
    
    if (conditionLower.includes('clear sky')) {
      return '☀️';
    } else if (conditionLower.includes('mainly clear')) {
      return '🌤️';
    } else if (conditionLower.includes('partly cloudy')) {
      return '⛅';
    } else if (conditionLower.includes('overcast') || conditionLower.includes('cloud')) {
      return '☁️';
    } else if (conditionLower.includes('drizzle')) {
      return '🌦️';
    } else if (conditionLower.includes('rain')) {
      return '🌧️';
    } else if (conditionLower.includes('snow')) {
      return '❄️';
    } else if (conditionLower.includes('thunderstorm') || conditionLower.includes('thunder')) {
      return '⛈️';
    } else if (conditionLower.includes('fog')) {
      return '🌫️';
    } else {
      return '🌡️'; // Default
    }
  }

  renderLoading() {
    if (!this.container) return;
    
    this.container.innerHTML = `
      <div class="weather-loading">
        <div class="weather-loading-spinner"></div>
        <div class="weather-loading-text">Loading weather...</div>
      </div>
    `;
  }

  renderError(message) {
    if (!this.container) return;
    
    this.container.innerHTML = `
      <div class="weather-error">
        <div class="weather-error-icon">⚠️</div>
        <div class="weather-error-text">Unable to load weather</div>
        <button class="weather-retry-btn">Retry</button>
      </div>
    `;
    
    const retryBtn = this.container.querySelector('.weather-retry-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => this.fetchWeather());
    }
  }

  renderWeather(data) {
    if (!this.container) return;
    
    const { location, temp_c, condition, wind_speed } = data;
    const icon = this.getWeatherIcon(condition);
    
    this.container.innerHTML = `
      <div class="weather-card">
        <div class="weather-header">
          <div class="weather-location">
            <span class="location-icon">📍</span>
            <span class="location-text">${location}</span>
          </div>
          <div class="weather-refresh" title="Refresh weather">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M23 4v6h-6M1 20v-6h6"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
          </div>
        </div>
        
        <div class="weather-main">
          <div class="weather-icon-large">${icon}</div>
          <div class="weather-temp">
            <span class="temp-value">${temp_c}</span>
            <span class="temp-unit">°C</span>
          </div>
          <div class="weather-condition-text">${condition}</div>
          <div class="weather-details">
            <div class="weather-detail-item">
              <span class="detail-label">💨</span>
              <span class="detail-value">${wind_speed} km/h</span>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Add refresh handler
    const refreshBtn = this.container.querySelector('.weather-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.fetchWeather());
    }
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.VibeSurfWeatherManager = WeatherManager;
}