import feedparser
import json
import os
import tweepy
import requests
from bs4 import BeautifulSoup
import re


RSS_URL = "https://dr-liposuction.jp/feed/"
POSTED_FILE = "posted.json"
MAX_LEN = 300

def clean_html(text):
    if not text:
        return ""
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

summary = clean_html(entry.get("summary", ""))
description = clean_html(entry.get("description", ""))
content = clean_html(entry.get("content", [{}])[0].get("value", ""))

# 一番情報量が多いものを使う（HTMLタグ完全除去）
candidates = [summary, description, content]
text = max(candidates, key=len) or entry.title



# 参考文献番号のような引用 [1], [1,2], [1-7], ［1–7］ を削除
text = re.sub(r"[［\[]\s*\d+(?:\s*[-–,]\s*\d+)*\s*[］\]]", "", text)


MAX_LEN = 280  # まずは280で運用（長ければ下で自動調整）

def normalize_jp(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    s = s.replace("［", "[").replace("］", "]")
    return s.strip()

def to_sentences(s: str):
    s = normalize_jp(s)
    # 見出しっぽい語や目次ノイズを軽く除去
    s = re.sub(r"(目次|Toggle|重要)", "", s)
    # 句点で分割
    parts = [p.strip() for p in s.split("。") if p.strip()]
    return parts

# --- ここまでに作った text（本文候補）を使う前提 ---

sentences = to_sentences(text)

# タイトルを先頭に
title = normalize_jp(entry.title)

# 本文から「短く読みやすい」2〜3文だけ拾う（長すぎる文はカット）
picked = []
for p in sentences:
    if len(p) < 15:
        continue
    if len(p) > 70:
        p = p[:70].rstrip("、")  # 長い文は短縮
    picked.append(p)
    if len(picked) >= 3:
        break

# もし本文が取れなければsummaryを短縮して1文に
if not picked:
    picked = [normalize_jp(text)[:80]]

body = "。".join(picked) + "。"

# ✅リンクは必ず最後に
url = entry.link
tweet = f"{title}\n{body}\n\n全文はこちら\n{url}"

# 280を超えたら本文を短くする（リンクは残す）
while len(tweet) > 280 and len(picked) > 1:
    picked = picked[:-1]
    body = "。".join(picked) + "。"
    tweet = f"{title}\n{body}\n\n全文はこちら\n{url}"

if len(tweet) > 280:
    # それでも長い場合は本文をさらに削る
    max_body = 280 - len(f"{title}\n\n全文はこちら\n{url}") - 2
    body = body[:max(20, max_body)].rstrip("、。") + "…"
    tweet = f"{title}\n{body}\n\n全文はこちら\n{url}"


client = tweepy.Client(
    consumer_key=os.environ["API_KEY"],
    consumer_secret=os.environ["API_SECRET"],
    access_token=os.environ["ACCESS_TOKEN"],
    access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
)

client.create_tweet(text=tweet)

posted.append(entry.id)
save_posted(posted)
