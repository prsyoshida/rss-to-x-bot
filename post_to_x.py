import os
import json
import feedparser
import requests
import tweepy
from bs4 import BeautifulSoup

# ============================
# 設定
# ============================
RSS_URL = "https://dr-liposuction.jp/feed/"  # あなたのRSS（必要なら変更）
POSTED_FILE = "posted.json"                  # 「投稿済み記事ID」を保存するファイル（同じ記事を二重投稿しないため）

# ============================
# posted.json（投稿済み管理）の読み書き
# ============================
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

# ============================
# WebページからOGP情報を取得（扉絵/説明文）
# ============================
def fetch_html(url: str) -> str:
    """URLのHTMLを取得（失敗したら空文字）"""
    try:
        r = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def get_og_image_url(article_url: str) -> str:
    """記事ページから og:image（扉絵URL）を取得"""
    html = fetch_html(article_url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

def get_og_description(article_url: str) -> str:
    """記事ページから og:description（説明文）を取得"""
    html = fetch_html(article_url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:description")
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

def download_image(url: str, save_path: str) -> bool:
    """画像URLをダウンロードして保存（成功したらTrue）"""
    try:
        r = requests.get(
            url,
            timeout=25,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()

        # Content-Typeが画像じゃなければ弾く
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "image" not in ctype:
            return False

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
        return True
    except Exception:
        return False

# ============================
# RSSから「未投稿の最新記事」を選ぶ
# ============================
def pick_next_entry(feed, posted_ids):
    """
    RSSの上から順に見て、posted.jsonに入っていない記事を1つ返す
    """
    for e in feed.entries:
        # RSSによっては e.id が無いので link も候補にする
        eid = getattr(e, "id", None) or getattr(e, "link", None)
        if not eid:
            continue
        if eid not in posted_ids:
            return e, eid
    return None, None

# ============================
# 文字を短く整える（説明文）
# ============================
def shorten_ja(text: str, limit: int = 60) -> str:
    """日本語説明文を指定文字数に収める（長ければ末尾を…にする）"""
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= limit:
        return t
    return t[:limit].rstrip("、。") + "…"

# ============================
# メイン処理
# ============================
def main():
    # 1) RSSを取得
    feed = feedparser.parse(RSS_URL)

    # 2) 投稿済みIDを読み込む
    posted = load_posted()

    # 3) 未投稿の最新記事を取得
    entry, entry_id = pick_next_entry(feed, posted)
    if not entry:
        # 未投稿が無ければ何もしない（正常終了）
        print("未投稿の記事がありません（投稿は行いませんでした）。")
        return

    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()

    if not title or not link:
        raise RuntimeError("RSS項目に title または link がありません。")

    # 4) 日本語の説明文（OGP description → RSS summary の順で使う）
    description = get_og_description(link)
    if not description:
        description = (entry.get("summary") or "").strip()
    description = shorten_ja(description, limit=60)

    # 5) ツイート本文（題名＋説明文＋続きはこちら＋リンク）
    #    ※「全文はこちら」など好みに応じて変更OK
    tweet_text = f"{title}\n{description}\n\n続きはこちら！\n{link}"

    # 6) 環境変数（GitHub Secrets）からキーを読む
    #    GitHub Secrets:
    #    API_KEY / API_SECRET / ACCESS_TOKEN / ACCESS_TOKEN_SECRET
    api_key = os.environ["API_KEY"]
    api_secret = os.environ["API_SECRET"]
    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    # 7) v2（投稿用）クライアント
    client_v2 = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    # 8) v1.1（画像アップロード用）API
    #    ※Xは画像アップロードがv1.1のほうが扱いやすいので併用します
    auth = tweepy.OAuth1UserHandler(
        api_key,
        api_secret,
        access_token,
        access_token_secret,
    )
    api_v1 = tweepy.API(auth)

    # 9) 扉絵（og:image）を取得して添付（取れなければ画像なしで投稿）
   media_id = None
　　og_img = get_og_image_url(link)
　　print("og:image =", og_img)

　　tmp_path = "/tmp/og_image.jpg"

　　if og_img:
　　    ok = download_image(og_img, tmp_path)
　　    print("download_image =", ok)

　　    if ok:
　　        try:
　　            media = api_v1.media_upload(filename=tmp_path)
　　            media_id = media.media_id_string
　　            print("media_id =", media_id)
　　        except Exception as e:
　　            print("media_upload failed:", repr(e))
　　else:
　　    print("og:image が取得できませんでした（空です）")


    # 10) 投稿（画像があれば添付）
    try:
        if media_id:
            client_v2.create_tweet(text=tweet_text, media_ids=[media_id])
        else:
            client_v2.create_tweet(text=tweet_text)
        print("投稿処理が正常に完了しました")
 
    except tweepy.errors.Forbidden as e:
        print("403 Forbidden が発生しました")
        try:
            print("status:", e.response.status_code)
            print("body:", e.response.text)
        except Exception:
            pass
        raise



    # 11) 投稿済みとして記録
    posted.append(entry_id)
    save_posted(posted)
    print(f"投稿済みIDを保存しました: {entry_id}")

if __name__ == "__main__":
    main()
