# Install required packages (uncomment and run if needed)
# !pip install newspaper3k transformers gtts googletrans==4.0.0-rc1

from newspaper import Article, build
from transformers import pipeline
from gtts import gTTS
from googletrans import Translator
from IPython.display import Audio, display
import time

# News source URLs
urls = [
    "https://www.jang.com.pk",
    "https://www.geo.tv",
    "https://www.bbc.com/",
    "https://edition.cnn.com/"
]

ARTICLES_PER_SOURCE = 6
translator = Translator()

# Huggingface pipelines
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

labels = ["real", "fake"]

def extract_articles(urls):
    articles = []
    for url in urls:
        try:
            paper = build(url, memoize_articles=False)
            print(f"\n🔍 Scraping from {url} ({len(paper.articles)} articles found)")
            for article in paper.articles[:ARTICLES_PER_SOURCE]:
                try:
                    article.download()
                    time.sleep(1)
                    if article.download_state != 2:
                        print(f"⚠️ Failed to download: {article.url}")
                        continue
                    article.parse()
                    if article.text and len(article.text) > 100:
                        articles.append({
                            'title': article.title,
                            'content': article.text[:1000],
                            'published_date': article.publish_date if article.publish_date else 'N/A'
                        })
                except Exception as e:
                    print(f"❌ Failed to parse article: {e}")
        except Exception as e:
            print(f"❌ Failed to build paper for {url}: {e}")
    return articles

def summarize_articles(articles):
    summaries = []
    for article in articles:
        try:
            content = article['content']
            max_len = min(180, int(len(content.split()) * 0.7))
            min_len = max(50, int(len(content.split()) * 0.3))

            summary = summarizer(content, max_length=max_len, min_length=min_len, do_sample=False)[0]['summary_text']
            summaries.append({
                'title': article['title'],
                'summary': summary
            })
            print(f"✅ Summarized: {article['title']}")
        except Exception as e:
            print(f"❌ Summary failed: {e}")
    return summaries

def filter_authentic_news(summaries):
    real_news = []
    for item in summaries:
        try:
            result = classifier(item['summary'], labels)
            if result['labels'][0] == "real":
                real_news.append(item)
                print(f"🟢 Real news: {item['title']}")
            else:
                print(f"🔴 Fake news: {item['title']}")
        except Exception as e:
            print(f"❌ Classification failed: {e}")
    return real_news

def translate_to_urdu(text):
    try:
        translated = translator.translate(text, dest='ur')
        return translated.text
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        return text

def create_script(news_items):
    full_script = ""
    for item in news_items:
        title_ur = translate_to_urdu(item['title'])
        summary_ur = translate_to_urdu(item['summary'])
        full_script += f"اہم خبر: {title_ur}\n{summary_ur}\n\n"
    return full_script.strip()

def text_to_speech(script_text, lang='ur'):
    try:
        print("🎙️ Generating voiceover...")
        tts = gTTS(text=script_text, lang=lang)
        tts.save("news_audio.mp3")
        display(Audio("news_audio.mp3", autoplay=True))
    except Exception as e:
        print(f"❌ TTS failed: {e}")

def run_pipeline():
    print("\n🚀 Running news pipeline...")
    raw_articles = extract_articles(urls)
    if not raw_articles:
        print("⚠️ No articles found.")
        return

    summaries = summarize_articles(raw_articles)
    if not summaries:
        print("⚠️ No summaries generated.")
        return

    authentic = filter_authentic_news(summaries)
    if not authentic:
        print("⚠️ No real news passed the filter.")
        return

    script = create_script(authentic)
    print("\n📝 Urdu Script Ready:\n", script)
    text_to_speech(script, lang='ur')

# Run the pipeline once
run_pipeline()
