document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const loadingScreen = document.getElementById('loading-screen');
    const newsContainer = document.getElementById('news-container');
    const errorContainer = document.getElementById('error-container');
    const videoElement = document.getElementById('news-video');
    const videoSource = document.getElementById('video-source');
    const headlinesContainer = document.getElementById('headlines-container');
    const headlinesTitle = document.getElementById('headlines-title');
    
    // Buttons
    const englishBtn = document.getElementById('english-btn');
    const urduBtn = document.getElementById('urdu-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const retryBtn = document.getElementById('retry-btn');
    
    // State
    let currentLanguage = 'english';
    
    // Initialize
    fetchNews();
    
    // Event Listeners
    englishBtn.addEventListener('click', function() {
        if (currentLanguage !== 'english') {
            currentLanguage = 'english';
            updateLanguageButtons();
            fetchNews();
        }
    });
    
    urduBtn.addEventListener('click', function() {
        if (currentLanguage !== 'urdu') {
            currentLanguage = 'urdu';
            updateLanguageButtons();
            fetchNews();
        }
    });
    
    refreshBtn.addEventListener('click', function() {
        triggerNewsUpdate();
    });
    
    retryBtn.addEventListener('click', function() {
        fetchNews();
    });
    
    videoElement.addEventListener('error', function() {
        showError();
    });
    
    // Functions
    function updateLanguageButtons() {
        englishBtn.classList.toggle('active', currentLanguage === 'english');
        urduBtn.classList.toggle('active', currentLanguage === 'urdu');
        
        // Update RTL styling for Urdu
        document.querySelectorAll('.rtl-support').forEach(el => {
            el.classList.toggle('rtl', currentLanguage === 'urdu');
        });
        
        // Update headlines title
        headlinesTitle.textContent = currentLanguage === 'english' ? 'Latest Headlines' : 'تازہ ترین سرخیاں';
    }
    
    function showLoading() {
        loadingScreen.classList.remove('hidden');
        newsContainer.classList.add('hidden');
        errorContainer.classList.add('hidden');
    }
    
    function showNews() {
        loadingScreen.classList.add('hidden');
        newsContainer.classList.remove('hidden');
        errorContainer.classList.add('hidden');
    }
    
    function showError() {
        loadingScreen.classList.add('hidden');
        newsContainer.classList.add('hidden');
        errorContainer.classList.remove('hidden');
    }
    
    function fetchNews() {
        showLoading();
        
        fetch(`/api/news/${currentLanguage}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.video_url) {
                    // Update video source
                    videoSource.src = data.video_url;
                    videoElement.load();
                    
                    // Update headlines
                    updateHeadlines(data.news);
                    
                    showNews();
                } else {
                    // If there's no video available yet, trigger an update
                    triggerNewsUpdate();
                    showError();
                }
            })
            .catch(error => {
                console.error('Error fetching news:', error);
                showError();
            });
    }
    
    function updateHeadlines(news) {
        headlinesContainer.innerHTML = '';
        headlinesContainer.classList.toggle('rtl', currentLanguage === 'urdu');
        
        if (!news || news.length === 0) {
            const noNews = document.createElement('p');
            noNews.textContent = currentLanguage === 'english' ? 
                'No headlines available at the moment.' : 
                'اس وقت کوئی سرخیاں دستیاب نہیں ہیں۔';
            headlinesContainer.appendChild(noNews);
            return;
        }
        
        news.forEach(item => {
            const headlineItem = document.createElement('div');
            headlineItem.className = 'headline-item';
            
            const title = document.createElement('h3');
            title.textContent = item.title;
            
            const summary = document.createElement('p');
            summary.textContent = item.summary;
            
            const source = document.createElement('div');
            source.className = 'source';
            source.textContent = `Source: ${item.source}`;
            
            headlineItem.appendChild(title);
            headlineItem.appendChild(summary);
            headlineItem.appendChild(source);
            
            headlinesContainer.appendChild(headlineItem);
        });
    }
    
    function triggerNewsUpdate() {
        showLoading();
        
        const lang = currentLanguage === 'english' ? 'en' : 'ur';
        
        fetch('/api/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ language: lang })
        })
        .then(response => response.json())
        .then(data => {
            // Poll for updates every 10 seconds
            const pollInterval = setInterval(() => {
                fetch(`/api/news/${currentLanguage}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.video_url) {
                            clearInterval(pollInterval);
                            
                            // Update video source
                            videoSource.src = data.video_url;
                            videoElement.load();
                            
                            // Update headlines
                            updateHeadlines(data.news);
                            
                            showNews();
                        }
                    })
                    .catch(error => {
                        console.error('Error polling for updates:', error);
                    });
            }, 10000);
            
            // Stop polling after 5 minutes (30 attempts)
            setTimeout(() => {
                clearInterval(pollInterval);
                if (loadingScreen.classList.contains('hidden') === false) {
                    showError();
                }
            }, 5 * 60 * 1000);
        })
        .catch(error => {
            console.error('Error triggering update:', error);
            showError();
        });
    }
});
