// News Carousel Manager
// Handles news fetching, display, and carousel navigation

class NewsCarouselManager {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.currentIndex = 0;
        this.currentType = 'hottest'; // 'hottest' or 'realtime'
        this.newsData = [];
        this.sourcesMetadata = {};
        this.isVisible = true; // Visible by default
        
        this.initializeElements();
        this.attachEventListeners();
    }
    
    initializeElements() {
        this.container = document.getElementById('news-carousel-container');
        this.slidesContainer = document.getElementById('news-carousel-slides');
        this.prevBtn = document.getElementById('carousel-prev');
        this.nextBtn = document.getElementById('carousel-next');
        this.indicatorsContainer = document.getElementById('carousel-indicators');
        this.typeTabs = document.querySelectorAll('.news-type-tab');
    }
    
    attachEventListeners() {
        // Navigation buttons
        this.prevBtn?.addEventListener('click', () => this.navigate(-1));
        this.nextBtn?.addEventListener('click', () => this.navigate(1));
        
        // Type tabs
        this.typeTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const type = e.target.dataset.type;
                if (type !== this.currentType) {
                    this.switchType(type);
                }
            });
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;
            if (e.key === 'ArrowLeft') this.navigate(-1);
            if (e.key === 'ArrowRight') this.navigate(1);
        });
    }
    
    async loadNews() {
        try {
            console.log('[NewsCarousel] Starting to load news, type:', this.currentType);
            this.showLoading();
            
            console.log('[NewsCarousel] Calling API getNews...');
            const response = await this.apiClient.getNews(null, this.currentType, 15);
            console.log('[NewsCarousel] API response received:', {
                hasResponse: !!response,
                hasNews: !!(response && response.news),
                newsKeys: response && response.news ? Object.keys(response.news) : [],
                hasMetadata: !!(response && response.sources_metadata),
                metadataKeys: response && response.sources_metadata ? Object.keys(response.sources_metadata) : []
            });
            
            if (response && response.news) {
                console.log('[NewsCarousel] Processing news data...');
                this.newsData = Object.entries(response.news).map(([sourceId, items]) => ({
                    sourceId,
                    items,
                    metadata: response.sources_metadata[sourceId] || {}
                }));
                
                console.log('[NewsCarousel] Mapped newsData:', {
                    totalSources: this.newsData.length,
                    sources: this.newsData.map(d => ({ sourceId: d.sourceId, itemCount: d.items.length }))
                });
                
                // Filter out sources with no news
                this.newsData = this.newsData.filter(item => item.items && item.items.length > 0);
                
                console.log('[NewsCarousel] Filtered newsData:', {
                    sourcesWithNews: this.newsData.length
                });
                
                this.sourcesMetadata = response.sources_metadata;
                
                console.log('[NewsCarousel] Calling renderCarousel...');
                this.renderCarousel();
                console.log('[NewsCarousel] renderCarousel completed');
            } else {
                console.warn('[NewsCarousel] No news data in response, showing empty state');
                this.showEmpty();
            }
        } catch (error) {
            console.error('[NewsCarousel] Error loading news:', error);
            console.error('[NewsCarousel] Error stack:', error.stack);
            this.showError();
        }
    }
    
    renderCarousel() {
        console.log('[NewsCarousel] renderCarousel called, newsData:', {
            hasNewsData: !!this.newsData,
            length: this.newsData ? this.newsData.length : 0
        });
        
        if (!this.newsData || this.newsData.length === 0) {
            console.warn('[NewsCarousel] No news data to render, showing empty state');
            this.showEmpty();
            return;
        }
        
        console.log('[NewsCarousel] Rendering carousel with', this.newsData.length, 'sources');
        
        // Reset index
        this.currentIndex = 0;
        
        // Clear slides
        console.log('[NewsCarousel] Clearing slides container');
        this.slidesContainer.innerHTML = '';
        
        // Create slides
        console.log('[NewsCarousel] Creating slides...');
        this.newsData.forEach((sourceData, index) => {
            console.log(`[NewsCarousel] Creating card ${index} for source:`, sourceData.sourceId);
            const slide = this.createNewsCard(sourceData, index);
            this.slidesContainer.appendChild(slide);
        });
        console.log('[NewsCarousel] All slides created, DOM children count:', this.slidesContainer.children.length);
        
        // Update indicators
        console.log('[NewsCarousel] Rendering indicators...');
        this.renderIndicators();
        
        // Update navigation
        console.log('[NewsCarousel] Updating navigation...');
        this.updateNavigation();
        
        console.log('[NewsCarousel] renderCarousel complete');
    }
    
    createNewsCard(sourceData, index) {
        const { sourceId, items, metadata } = sourceData;
        
        const card = document.createElement('div');
        card.className = `news-card ${this.currentType}-type`;
        
        const color = metadata.color || 'gray';
        const sourceName = metadata.name || sourceId;
        const sourceTitle = metadata.title || '';
        const sourceHome = metadata.home || '#';
        
        // Create source logo (first character of source name)
        const logoText = sourceName.charAt(0).toUpperCase();
        
        const cardHTML = `
            <div class="news-card-inner color-${color}">
                <div class="news-card-header">
                    <div class="news-source-logo">${logoText}</div>
                    <div class="news-source-info">
                        <div class="news-source-name">${sourceName}</div>
                        <div class="news-source-subtitle">${sourceTitle || '最新资讯'}</div>
                    </div>
                    <button class="news-refresh-btn" data-source-id="${sourceId}" title="刷新">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 4v6h6M23 20v-6h-6"/>
                            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
                        </svg>
                    </button>
                </div>
                <ul class="news-list">
                    ${items.slice(0, 13).map((item, i) => this.createNewsItem(item, i, sourceHome)).join('')}
                </ul>
            </div>
        `;
        
        card.innerHTML = cardHTML;
        
        // Add refresh button listener
        const refreshBtn = card.querySelector('.news-refresh-btn');
        refreshBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.refreshSource(sourceId);
        });
        
        return card;
    }
    
    createNewsItem(item, index, sourceHome) {
        const number = index + 1;
        const title = item.title || '无标题';
        const url = item.url || item.mobileUrl || sourceHome;
        const pubDate = item.pubDate;
        const extra = item.extra;
        
        // Format time
        const timeDisplay = this.formatTime(pubDate);
        
        // Create metadata display
        let metaHTML = '';
        if (this.currentType === 'realtime' && timeDisplay) {
            metaHTML = `
                <div class="news-item-meta">
                    <span class="news-item-time">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M12 6v6l4 2"/>
                        </svg>
                        ${timeDisplay}
                    </span>
                </div>
            `;
        } else if (this.currentType === 'hottest' && extra) {
            // Show heat/engagement info if available
            const heatInfo = typeof extra === 'object' ? extra.heat || extra.hot || '' : extra;
            if (heatInfo) {
                metaHTML = `
                    <div class="news-item-meta">
                        <span class="news-item-heat">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                            </svg>
                            ${heatInfo}
                        </span>
                    </div>
                `;
            }
        }
        
        const numberClass = number <= 3 ? 'top-3' : '';
        
        return `
            <li class="news-item">
                <div class="news-item-number ${numberClass}">${number}</div>
                <div class="news-item-content">
                    <a href="${url}" target="_blank" rel="noopener noreferrer" class="news-item-title">${this.escapeHtml(title)}</a>
                    ${metaHTML}
                </div>
            </li>
        `;
    }
    
    formatTime(pubDate) {
        if (!pubDate) return '';
        
        try {
            const now = new Date();
            const newsTime = new Date(pubDate);
            
            if (isNaN(newsTime.getTime())) return '';
            
            const diffMs = now - newsTime;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 1) {
                return '刚刚';
            } else if (diffMins < 60) {
                return `${diffMins}分钟前`;
            } else if (diffHours < 24) {
                return `${diffHours}小时前`;
            } else if (diffDays < 7) {
                return `${diffDays}天前`;
            } else {
                // Format as date
                const month = newsTime.getMonth() + 1;
                const day = newsTime.getDate();
                return `${month}月${day}日`;
            }
        } catch (error) {
            console.error('[NewsCarousel] Error formatting time:', error);
            return '';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    renderIndicators() {
        if (!this.indicatorsContainer) return;
        
        this.indicatorsContainer.innerHTML = '';
        
        this.newsData.forEach((_, index) => {
            const indicator = document.createElement('div');
            indicator.className = 'carousel-indicator';
            if (index === this.currentIndex) {
                indicator.classList.add('active');
            }
            indicator.addEventListener('click', () => this.goToSlide(index));
            this.indicatorsContainer.appendChild(indicator);
        });
    }
    
    navigate(direction) {
        const newIndex = this.currentIndex + direction;
        
        if (newIndex >= 0 && newIndex < this.newsData.length) {
            this.goToSlide(newIndex);
        }
    }
    
    goToSlide(index) {
        if (index < 0 || index >= this.newsData.length) return;
        
        this.currentIndex = index;
        
        // Update slide position
        const offset = -index * 100;
        this.slidesContainer.style.transform = `translateX(${offset}%)`;
        
        // Update indicators
        const indicators = this.indicatorsContainer?.querySelectorAll('.carousel-indicator');
        indicators?.forEach((indicator, i) => {
            indicator.classList.toggle('active', i === index);
        });
        
        // Update navigation buttons
        this.updateNavigation();
    }
    
    updateNavigation() {
        if (this.prevBtn) {
            this.prevBtn.disabled = this.currentIndex === 0;
        }
        
        if (this.nextBtn) {
            this.nextBtn.disabled = this.currentIndex === this.newsData.length - 1;
        }
    }
    
    async switchType(type) {
        this.currentType = type;
        
        // Update tab active state
        this.typeTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.type === type);
        });
        
        // Reload news
        await this.loadNews();
    }
    
    async refreshSource(sourceId) {
        try {
            console.log(`[NewsCarousel] Refreshing source: ${sourceId}`);
            const response = await this.apiClient.getNews(sourceId, this.currentType, 15);
            
            if (response && response.news && response.news[sourceId]) {
                // Update the specific source data
                const sourceIndex = this.newsData.findIndex(item => item.sourceId === sourceId);
                if (sourceIndex !== -1) {
                    this.newsData[sourceIndex].items = response.news[sourceId];
                    
                    // Re-render only the current card if it's the one being refreshed
                    if (sourceIndex === this.currentIndex) {
                        const card = this.createNewsCard(this.newsData[sourceIndex], sourceIndex);
                        const currentCard = this.slidesContainer.children[sourceIndex];
                        if (currentCard) {
                            this.slidesContainer.replaceChild(card, currentCard);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('[NewsCarousel] Error refreshing source:', error);
        }
    }
    
    showLoading() {
        this.slidesContainer.innerHTML = `
            <div class="news-loading">
                <div class="news-loading-spinner"></div>
                <div class="news-loading-text">加载新闻中...</div>
            </div>
        `;
        
        if (this.indicatorsContainer) {
            this.indicatorsContainer.innerHTML = '';
        }
        
        if (this.prevBtn) this.prevBtn.disabled = true;
        if (this.nextBtn) this.nextBtn.disabled = true;
    }
    
    showEmpty() {
        this.slidesContainer.innerHTML = `
            <div class="news-empty">
                <div class="news-empty-icon">📰</div>
                <div class="news-empty-text">暂无新闻数据</div>
            </div>
        `;
        
        if (this.indicatorsContainer) {
            this.indicatorsContainer.innerHTML = '';
        }
        
        if (this.prevBtn) this.prevBtn.disabled = true;
        if (this.nextBtn) this.nextBtn.disabled = true;
    }
    
    showError() {
        this.slidesContainer.innerHTML = `
            <div class="news-empty">
                <div class="news-empty-icon">⚠️</div>
                <div class="news-empty-text">加载失败，请稍后重试</div>
            </div>
        `;
        
        if (this.indicatorsContainer) {
            this.indicatorsContainer.innerHTML = '';
        }
    }
    
    show() {
        if (this.container) {
            this.container.style.display = 'block';
            this.isVisible = true;
        }
    }
    
    hide() {
        if (this.container) {
            this.container.style.display = 'none';
            this.isVisible = false;
        }
    }
    
    async initialize() {
        console.log('[NewsCarousel] initialize() called');
        console.log('[NewsCarousel] Elements check:', {
            hasContainer: !!this.container,
            hasSlidesContainer: !!this.slidesContainer,
            hasPrevBtn: !!this.prevBtn,
            hasNextBtn: !!this.nextBtn,
            hasIndicatorsContainer: !!this.indicatorsContainer,
            hasTypeTabs: !!this.typeTabs,
            typeTabsCount: this.typeTabs ? this.typeTabs.length : 0
        });
        
        try {
            console.log('[NewsCarousel] Calling loadNews...');
            await this.loadNews();
            console.log('[NewsCarousel] loadNews completed');
        } catch (error) {
            console.error('[NewsCarousel] Error in initialize:', error);
            console.error('[NewsCarousel] Error stack:', error.stack);
        }
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.NewsCarouselManager = NewsCarouselManager;
}