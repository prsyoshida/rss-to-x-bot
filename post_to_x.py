import os
import json
import re
import hashlib
import feedparser
import tweepy
from datetime import datetime

RSS_URL = "https://dr-liposuction.jp/feed/"
POSTED_FILE = "posted.json"

# 付けたい固定ハッシュタグ（必要なら増減OK）
TAGS = ["#脂肪吸引", "#豊胸", "#美容外科"]

def load_posted():
    """
    posted.json から投稿済みIDセットを読み込む
    形式は以下どちらでもOK：
      - ["id1","id2",...]
      - {"posted_ids":["id1","id2"], "updated_at":"..."}
    """
    if not os.path.exists(POSTED_FILE):
        return set()

    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return set()

    if isinstance(data, list):
        return set(data)
    if isinstance(data, dict):
        ids = data.get("posted_ids", [])
        return set(ids if isinstance(ids, list) else [])
    return set()

def save_posted(posted_ids):
    """投稿済みIDセットを posted.json に保存（dict形式で保存）"""
    payload = {
        "posted_ids": sorted(list(posted_ids)),
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def pick_next_entry(feed, posted_ids):
    """RSSの上から順に見て、未投稿の記事を1つ返す"""
    for e in feed.entries:
        link = getattr(e, "link", None) or e.get("link")
        eid = getattr(e, "id", None) or e.get("id") or link
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
    """題名＋誘導文＋リンク＋ハッシュタグ（280字対策あり）"""
    title = normalize_title(title)
    tags = " ".join(TAGS)

    # 文言は「同一判定」されにくいよう、末尾に短い固定語は入れず、必要最小限
    tweet = f"{title}\n\n続きはこちら👇\n{link}\n\n{tags}"

    # 280文字対策（保守的に275で切る）
    if len(tweet) > 275:
        max_title = max(10, 275 - (len(tweet) - len(title)) - 1)
        short_title = title[:max_title].rstrip("、。") + "…"
        tweet = f"{short_title}\n\n続きはこちら👇\n{link}\n\n{tags}"

    return tweet

def content_fingerprint(text: str) -> str:
    """
    追加の安全策：
    posted.json に「本文ハッシュ」も保存できるよう、指紋を作る
    （今回は ID 保存だけでもOKだが、将来の保険）
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main():
    feed = feedparser.parse(RSS_URL)
    posted_ids = load_posted()

    entry, entry_id = pick_next_entry(feed, posted_ids)
    if not entry:
        print("未投稿の記事がありません（投稿は行いませんでした）。")
        return

    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        raise RuntimeError("RSS項目に title または link がありません。")

    tweet_text = build_tweet(title, link)

    # 念のため：同じ entry_id を二重に投稿しない
    if entry_id in posted_ids:
        print("この記事はすでに投稿済みです（entry_id一致）。スキップします:", entry_id)
        return

    print("tweet_text =", tweet_text)

    # GitHub Secrets からキーを読む
    api_key = os.environ.get("API_KEY", "")
    api_secret = os.environ.get("API_SECRET", "")
    access_token = os.environ.get("ACCESS_TOKEN", "")
    access_token_secret = os.environ.get("ACCESS_TOKEN_SECRET", "")

    missing = [k for k, v in {
        "API_KEY": api_key,
        "API_SECRET": api_secret,
        "ACCESS_TOKEN": access_token,
        "ACCESS_TOKEN_SECRET": access_token_secret,
    }.items() if not v]

    if missing:
        raise RuntimeError(f"必要な環境変数（GitHub Secrets）が不足しています: {', '.join(missing)}")

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
    except tweepy.errors.Forbidden as e:
        # duplicate content などの典型例はここに入る
        print("Forbidden（403）で投稿できませんでした。理由:", e)
        # 403は「投稿はできていない」ので posted を更新しない
        raise
    except Exception as e:
        print("投稿に失敗しました。理由:", repr(e))
        raise

    # 投稿済みとして記録
    posted_ids.add(entry_id)
    save_posted(posted_ids)
    print("投稿済みIDを保存しました:", entry_id)

if __name__ == "__main__":
    main()
