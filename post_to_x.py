import os
import json
import re
import feedparser
import tweepy

RSS_URL = "https://dr-liposuction.jp/feed/"
POSTED_FILE = "posted.json"

# 付けたい固定ハッシュタグ（必要なら増減OK）
# ※ Xはハッシュタグの効果が昔より弱いですが、検索導線としては有用です
TAGS = ["#脂肪吸引", "#豊胸", "#美容外科"]

def load_posted():
    """posted.json から投稿済みIDリストを読み込む"""
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_posted(data):
    """投稿済みIDリストを posted.json に保存する"""
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def pick_next_entry(feed, posted_ids):
    """RSSの上から順に見て、未投稿の記事を1つ返す"""
    for e in feed.entries:
        eid = getattr(e, "id", None) or getattr(e, "link", None)
        if not eid:
            continue
        if eid not in posted_ids:
            return e, eid
    return None, None

def normalize_title(title: str) -> str:
    """タイトルの改行や余計な空白を整える"""
    t = (title or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t

def build_tweet(title: str, link: str) -> str:
    """最小のツイート本文を作る（題名＋続きはこちら＋リンク＋ハッシュタグ）"""
    title = normalize_title(title)
    tags = " ".join(TAGS)

    # 「題名」「誘導文」「リンク」「タグ」の順（読みやすい）
    tweet = f"{title}\n\n続きはこちら！\n{link}\n\n{tags}"

    # 念のため280を超えたらタイトルを短縮して収める
    # （URLは23文字換算などがあり得るので保守的に短くする）
    if len(tweet) > 275:
        max_title = max(10, 275 - (len(tweet) - len(title)) - 1)
        short_title = title[:max_title].rstrip("、。") + "…"
        tweet = f"{short_title}\n\n続きはこちら！\n{link}\n\n{tags}"

    return tweet

def main():
    feed = feedparser.parse(RSS_URL)
    posted = load_posted()

    entry, entry_id = pick_next_entry(feed, posted)
    if not entry:
        print("未投稿の記事がありません（投稿は行いませんでした）。")
        return

    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()

    if not title or not link:
        raise RuntimeError("RSS項目に title または link がありません。")

    tweet_text = build_tweet(title, link)
    print("tweet_text =", tweet_text)

    # GitHub Secrets からキーを読む
    api_key = os.environ["API_KEY"]
    api_secret = os.environ["API_SECRET"]
    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    # v2で投稿（あなたの現状のアクセス範囲に合わせる）
    client_v2 = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    # 投稿（失敗時は posted.json を更新しない）
    try:
        client_v2.create_tweet(text=tweet_text)
        print("投稿しました（v2）。")
    except Exception as e:
        print("投稿に失敗しました。理由:", repr(e))
        raise

    # 投稿済みとして記録
    posted.append(entry_id)
    save_posted(posted)
    print("投稿済みIDを保存しました:", entry_id)

if __name__ == "__main__":
    main()
