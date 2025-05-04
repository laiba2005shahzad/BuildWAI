# AI News Anchor Web Application

This project is an AI-powered news anchor web application that automatically scrapes news articles, generates summaries, translates content between English and Urdu, and presents the news using a digital avatar with synchronized lip movements.

## Features

- Automatic web scraping of news articles from various sources
- Natural language processing for summarizing articles
- Fake news detection using zero-shot classification
- Multilingual support (English and Urdu)
- Digital avatar news presenter using D-ID API
- Automatic hourly updates
- Responsive web design

## Technical Architecture

The application consists of:

1. **Backend** (Flask):
   - Web scraping module using newspaper3k
   - Article summarization with Hugging Face transformers
   - Content translation using Google Translate
   - Integration with D-ID API for avatar generation
   - Scheduled news updates

2. **Frontend** (HTML/CSS/JavaScript):
   - Responsive user interface
   - Language switching
   - Video playback
   - News headlines display

## Setup Instructions

### Prerequisites

- Python 3.8+
- Visual Studio Code
- D-ID API key (already included in code)

### Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Running the Application

1. Start the Flask application:
   ```
   python app.py
   ```
2. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

## Project Structure

```
ai-news-anchor/
│
├── app.py                # Flask application
├── requirements.txt      # Python dependencies
│
├── static/
│   ├── css/
│   │   └── style.css     # Application styling
│   │
│   └── js/
│       └── script.js     # Frontend functionality
│
└── templates/
    └── index.html        # HTML template
```

## How It Works

1. The application periodically scrapes news articles from configured sources
2. Articles are summarized and checked for authenticity
3. A news script is generated in the selected language
4. The D-ID API creates a video with a digital avatar reading the news
5.