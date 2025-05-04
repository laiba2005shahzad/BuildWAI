from flask import Flask, render_template, jsonify, request
import os
import json
import time
import requests
import subprocess
import uuid
import logging
from newspaper import Article, build
from transformers import pipeline
from googletrans import Translator
import threading
import schedule
from pathlib import Path
import sys
import shutil


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("news_app")

app = Flask(__name__)

# Configuration
ARTICLES_PER_SOURCE = 6

SADTALKER_PATH = os.path.join(os.getcwd(), "SadTalker")  
SADTALKER_OUTPUT_PATH = os.path.join(os.getcwd(), "static", "videos")
TEMP_DIR = os.path.join(os.getcwd(), "temp")

AVATAR_IMAGES = {
    "en": os.path.join(os.getcwd(), "resources", "english_anchor.jpg"),
    "ur": os.path.join(os.getcwd(), "resources", "urdu_anchor.jpg")
}

for directory in [SADTALKER_OUTPUT_PATH, TEMP_DIR, os.path.join(os.getcwd(), "resources")]:
    os.makedirs(directory, exist_ok=True)


news_sources = {
    "english": [
        "https://www.bbc.com/",
        "https://edition.cnn.com/"
    ],
    "urdu": [
        "https://www.jang.com.pk",
        "https://www.geo.tv"
    ]
}


latest_news = {
    "english": [],
    "urdu": []
}

latest_videos = {
    "english": None,
    "urdu": None
}

def check_sadtalker_installation():
    """Check if SadTalker is properly installed"""
    if not os.path.exists(SADTALKER_PATH):
        logger.error(f"SadTalker directory not found at {SADTALKER_PATH}")
        logger.info("Please install SadTalker from https://github.com/OpenTalker/SadTalker")
        return False
        
    inference_script = os.path.join(SADTALKER_PATH, "inference.py")
    if not os.path.exists(inference_script):
        logger.error(f"SadTalker inference.py not found at {inference_script}")
        return False
        
    return True

def check_avatar_images():
    """Check if avatar images exist"""
    missing_images = []
    for lang, path in AVATAR_IMAGES.items():
        if not os.path.exists(path):
            missing_images.append((lang, path))
    
    if missing_images:
        for lang, path in missing_images:
            logger.error(f"Avatar image for {lang} not found at {path}")
        return False
    return True

try:
    translator = Translator()
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    labels = ["real", "fake"]
    logger.info("NLP components initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize NLP components: {e}")
    sys.exit(1)

def extract_articles(urls):
    """Extract articles from news sources"""
    articles = []
    for url in urls:
        try:
            logger.info(f"Scraping from {url}")
            paper = build(url, memoize_articles=False)
            logger.info(f"Found {len(paper.articles)} articles from {url}")
            
            for article in paper.articles[:ARTICLES_PER_SOURCE]:
                try:
                    article.download()
                    time.sleep(1)
                    if article.download_state != 2:
                        logger.warning(f"Failed to download: {article.url}")
                        continue
                    article.parse()
                    if article.text and len(article.text) > 100:
                        articles.append({
                            'title': article.title,
                            'content': article.text[:1000],
                            'source': url,
                            'url': article.url,
                            'published_date': article.publish_date.isoformat() if article.publish_date else 'N/A'
                        })
                        logger.debug(f"Added article: {article.title}")
                except Exception as e:
                    logger.error(f"Failed to parse article: {e}")
        except Exception as e:
            logger.error(f"Failed to build paper for {url}: {e}")
    
    logger.info(f"Extracted {len(articles)} articles in total")
    return articles

def summarize_articles(articles):
    """Summarize articles"""
    summaries = []
    for article in articles:
        try:
            content = article['content']
            max_len = min(180, int(len(content.split()) * 0.7))
            min_len = max(50, int(len(content.split()) * 0.3))

            summary = summarizer(content, max_length=max_len, min_length=min_len, do_sample=False)[0]['summary_text']
            article_with_summary = article.copy()
            article_with_summary['summary'] = summary
            summaries.append(article_with_summary)
            logger.info(f"Summarized: {article['title']}")
        except Exception as e:
            logger.error(f"Summary failed for {article['title']}: {e}")
    return summaries

def filter_authentic_news(summaries):
    """Filter authentic news using classification"""
    real_news = []
    for item in summaries:
        try:
            result = classifier(item['summary'], labels)
            if result['labels'][0] == "real":
                real_news.append(item)
                logger.info(f"Real news: {item['title']}")
            else:
                logger.info(f"Potential fake news: {item['title']}")
        except Exception as e:
            logger.error(f"Classification failed: {e}")
    return real_news

def translate_content(text, target_lang):
    """Translate text to target language"""
    if target_lang == 'ur' and not text:
        return text
    
    try:
        translated = translator.translate(text, dest=target_lang)
        return translated.text
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text

def create_news_script(news_items, lang='en'):
    """Create a news script from news items"""
    if lang == 'en':
        script = "Welcome to today's news broadcast.\n\n"
        for item in news_items[:5]:  # Limit to 5 news items
            script += f"Breaking news: {item['title']}\n"
            script += f"{item['summary']}\n\n"
        script += "Thank you for watching. Stay tuned for more updates."
    else:  # Urdu
        script = "آج کی خبروں میں خوش آمدید۔\n\n"
        for item in news_items[:5]:
            title_ur = translate_content(item['title'], 'ur')
            summary_ur = translate_content(item['summary'], 'ur')
            script += f"اہم خبر: {title_ur}\n"
            script += f"{summary_ur}\n\n"
        script += "دیکھنے کا شکریہ۔ مزید اپڈیٹس کے لیے ہمارے ساتھ رہیں۔"
    
    return script.strip()

def generate_audio_from_text(text, output_path, lang='en'):
    """Generate audio file from text using TTS"""
    try:
        try:
            from edge_tts import Communicate
            import asyncio
            
            # Choose voice based on language
            voice = "en-US-Neural2-F" if lang == 'en' else "ur-PK-UzmaNeural"
            
            async def generate():
                communicate = Communicate(text, voice)
                await communicate.save(output_path)
            
            logger.info(f"Generating audio with edge-tts to {output_path}")
            asyncio.run(generate())
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Audio generated successfully: {output_path}")
                return output_path
            else:
                logger.error(f"Audio file not created or empty: {output_path}")
                return None
                
        except ImportError:
            logger.warning("edge-tts not installed, trying gTTS fallback")
            # Fallback to gTTS if edge-tts is not available
            from gtts import gTTS
            
            tts = gTTS(text=text, lang='en' if lang == 'en' else 'ur')
            tts.save(output_path)
            logger.info(f"Audio generated with gTTS: {output_path}")
            return output_path
            
    except Exception as e:
        logger.error(f"All TTS methods failed: {e}")
        return None

def create_avatar_video(script, lang='en'):
    """Create avatar video using SadTalker"""
    if not check_sadtalker_installation():
        logger.error("SadTalker not properly installed. Video creation aborted.")
        return None
        
    if not check_avatar_images():
        logger.error("Avatar images not found. Video creation aborted.")
        return None
    
    try:
        # Create a unique ID for this video
        video_id = str(uuid.uuid4())
        
        # Define paths
        audio_path = os.path.join(TEMP_DIR, f"audio_{video_id}.mp3")
        output_dir = os.path.join(SADTALKER_OUTPUT_PATH, video_id)
        os.makedirs(output_dir, exist_ok=True)
        
        source_image = AVATAR_IMAGES[lang]
        if not os.path.exists(source_image):
            logger.error(f"Source image not found: {source_image}")
            return None
        
        # Generate audio from script
        logger.info(f"Generating audio for {lang} script")
        audio_file = generate_audio_from_text(script, audio_path, lang)
        if not audio_file or not os.path.exists(audio_file):
            logger.error("Audio generation failed")
            return None
            
        logger.info(f"Audio file created: {audio_file}")
        
        # here we go
        original_dir = os.getcwd()
        try:
            os.chdir(SADTALKER_PATH)
            logger.info(f"Changed directory to {SADTALKER_PATH}")
            
            # Build the command with proper quoting and path handling
            command = [
                sys.executable,  # Use the current Python interpreter
                "inference.py",
                "--driven_audio", audio_file,
                "--source_image", source_image,
                "--result_dir", output_dir,
                "--enhancer", "gfpgan",
                "--still",
                "--preprocess", "full",
                "--expression_scale", "1.0"
            ]
            
            command_str = " ".join(command)
            logger.info(f"Running SadTalker command: {command_str}")
            
            # Run the command with full output capture
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            # Log the output
            logger.info(f"SadTalker stdout: {stdout}")
            if stderr:
                logger.error(f"SadTalker stderr: {stderr}")
            
            if process.returncode != 0:
                logger.error(f"SadTalker failed with return code {process.returncode}")
                return None
                
            # Find the output video file
            video_files = list(Path(output_dir).glob("*.mp4"))
            if not video_files:
                logger.error(f"No output video found in {output_dir}")
                # List all files in the directory for debugging
                logger.debug(f"Files in output directory: {os.listdir(output_dir)}")
                return None
                
            # Get the relative URL path for the video
            video_url = f"/static/videos/{video_id}/{video_files[0].name}"
            logger.info(f"Video created successfully: {video_url}")
            return video_url
            
        finally:
            os.chdir(original_dir)
            logger.info(f"Changed directory back to {original_dir}")
            
    except Exception as e:
        logger.exception(f"Error creating video: {e}")
        return None

def fetch_news_pipeline(lang='en'):
    """Run the complete news fetching and processing pipeline"""
    logger.info(f"Running news pipeline for {lang}...")
    
    # Determine the news sources based on language
    urls = news_sources['english'] if lang == 'en' else news_sources['urdu']
    
    # Extract and process news
    raw_articles = extract_articles(urls)
    if not raw_articles:
        logger.warning("No articles found.")
        return None
    
    summaries = summarize_articles(raw_articles)
    if not summaries:
        logger.warning("No summaries generated.")
        return None
    
    authentic = filter_authentic_news(summaries)
    if not authentic:
        logger.warning("No real news passed the filter.")
        return None
    
    # Create news script
    script = create_news_script(authentic, lang)
    logger.info(f"Script ready for {lang}")
    
    # Create avatar video
    video_url = create_avatar_video(script, lang)
    
    # Update latest news storage
    lang_key = 'english' if lang == 'en' else 'urdu'
    latest_news[lang_key] = authentic
    latest_videos[lang_key] = video_url
    
    return video_url

def scheduled_news_update():
    """Function to run scheduled news updates"""
    logger.info("Running scheduled news update...")
    fetch_news_pipeline('en')
    fetch_news_pipeline('ur')

# Schedule the news updates
def start_scheduler():
    schedule.every(1).hour.do(scheduled_news_update)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Fallback video method using ffmpeg if SadTalker fails
def create_fallback_video(script, lang='en'):
    """Create a simple video with text overlay using ffmpeg"""
    try:
        video_id = str(uuid.uuid4())
        output_dir = os.path.join(SADTALKER_OUTPUT_PATH, video_id)
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "news_video.mp4")
        
        # Generate audio
        audio_path = os.path.join(TEMP_DIR, f"audio_{video_id}.mp3")
        audio_file = generate_audio_from_text(script, audio_path, lang)
        
        if not audio_file:
            logger.error("Failed to create audio for fallback video")
            return None
            
        # Create text file for ffmpeg
        text_file = os.path.join(TEMP_DIR, f"text_{video_id}.txt")
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(script[:500])  # Limit text length for display
            
        # Create video with ffmpeg
        background_color = "blue"
        text_color = "white"
        
        command = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=c={background_color}:s=1280x720:d=60",
            "-i", audio_file,
            "-vf", f"drawtext=fontfile=/path/to/font.ttf:textfile='{text_file}':x=(w-text_w)/2:y=(h-text_h)/2:fontsize=24:fontcolor={text_color}:box=1:boxcolor=black@0.5:boxborderw=5:line_spacing=10",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]
        
        subprocess.run(command, check=True)
        
        if os.path.exists(output_path):
            video_url = f"/static/videos/{video_id}/news_video.mp4"
            logger.info(f"Fallback video created at {video_url}")
            return video_url
        
        return None
    except Exception as e:
        logger.exception(f"Fallback video creation failed: {e}")
        return None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news/<lang>')
def get_news(lang):
    """API endpoint to get latest news"""
    if lang not in ['english', 'urdu']:
        return jsonify({"error": "Invalid language"}), 400
    
    return jsonify({
        "news": latest_news[lang],
        "video_url": latest_videos[lang]
    })

@app.route('/api/update', methods=['POST'])
def update_news():
    """Manually trigger news update"""
    lang = request.json.get('language', 'en')
    if lang not in ['en', 'ur']:
        return jsonify({"error": "Invalid language"}), 400
    
    # Run in a separate thread to not block the request
    threading.Thread(target=fetch_news_pipeline, args=(lang,)).start()
    return jsonify({"message": f"News update for {lang} started"})

@app.route('/api/status')
def status():
    """Get system status"""
    sadtalker_installed = check_sadtalker_installation()
    images_ok = check_avatar_images()
    
    return jsonify({
        "status": "ok",
        "sadtalker_installed": sadtalker_installed,
        "avatar_images_ok": images_ok,
        "english_news_count": len(latest_news["english"]),
        "urdu_news_count": len(latest_news["urdu"]),
        "english_video": latest_videos["english"] is not None,
        "urdu_video": latest_videos["urdu"] is not None
    })

# HTML template for testing
@app.route('/test')
def test_page():
    """Test page to check if videos are working"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>News Avatar Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .video-container { margin-bottom: 30px; }
            video { max-width: 100%; }
            button { padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>News Avatar Test</h1>
        
        <div class="video-container">
            <h2>English News</h2>
            <div id="english-video">No video available</div>
            <button onclick="updateNews('en')">Generate English News</button>
        </div>
        
        <div class="video-container">
            <h2>Urdu News</h2>
            <div id="urdu-video">No video available</div>
            <button onclick="updateNews('ur')">Generate Urdu News</button>
        </div>
        
        <div>
            <h2>System Status</h2>
            <pre id="status">Loading...</pre>
            <button onclick="checkStatus()">Refresh Status</button>
        </div>
        
        <script>
            function loadVideos() {
                fetch('/api/news/english')
                    .then(response => response.json())
                    .then(data => {
                        if (data.video_url) {
                            document.getElementById('english-video').innerHTML = 
                                `<video controls><source src="${data.video_url}" type="video/mp4"></video>`;
                        }
                    });
                    
                fetch('/api/news/urdu')
                    .then(response => response.json())
                    .then(data => {
                        if (data.video_url) {
                            document.getElementById('urdu-video').innerHTML = 
                                `<video controls><source src="${data.video_url}" type="video/mp4"></video>`;
                        }
                    });
            }
            
            function updateNews(lang) {
                fetch('/api/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({language: lang}),
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    setTimeout(loadVideos, 3000);  // Try to load videos after 3 seconds
                });
            }
            
            function checkStatus() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status').textContent = JSON.stringify(data, null, 2);
                    });
            }
            
            // Initial load
            loadVideos();
            checkStatus();
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    # Check if SadTalker is installed
    if not check_sadtalker_installation():
        logger.warning("SadTalker not properly installed. Video creation will not work.")
        
    # Check if avatar images exist
    if not check_avatar_images():
        logger.warning("Avatar images not found. Using default images may fail.")
    
    # Initial news fetch in background
    logger.info("Starting initial news fetch")
    threading.Thread(target=fetch_news_pipeline, args=('en',)).start()
    threading.Thread(target=fetch_news_pipeline, args=('ur',)).start()
    
    # Start scheduler in a separate thread
    logger.info("Starting scheduler")
    threading.Thread(target=start_scheduler, daemon=True).start()
    
    # Run the Flask app
    logger.info("Starting Flask app")
    app.run(debug=True, use_reloader=False)
