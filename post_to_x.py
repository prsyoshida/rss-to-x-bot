import feedparser
import json
import os
import tweepy
from bs4 import BeautifulSoup


RSS_URL = "https://dr-liposuction.jp/feed/"
POSTED_FILE = "posted.json"
MAX_LEN = 300

def clean_html(text):
    return BeautifulSoup(text, "html.parser").get_text(" ").replace("\n", " ").strip()


def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(data, f)

feed = feedparser.parse(RSS_URL)
posted = load_posted()

entry = next(e for e in feed.entries if e.id not in posted)

summary = entry.get("summary", "").replace("\n", " ").strip()
content = entry.get("content", [{}])[0].get("value", "").replace("\n", " ").strip()

# summary が短すぎる場合は本文を使う
if len(summary) < 120:
    text = content or entry.title
else:
    text = summary


text = raw_text.replace("\n", " ").strip()

tweet = f"{text}\n\n続きはこちら\n{entry.link}"


if len(tweet) > MAX_LEN:
    tweet = tweet[:MAX_LEN].rsplit("。", 1)[0] + "。"


client = tweepy.Client(
    consumer_key=os.environ["API_KEY"],
    consumer_secret=os.environ["API_SECRET"],
    access_token=os.environ["ACCESS_TOKEN"],
    access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
)

client.create_tweet(text=tweet)

posted.append(entry.id)
save_posted(posted)
