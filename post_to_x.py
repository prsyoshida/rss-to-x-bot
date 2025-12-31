import os
import json
import re
import feedparser
import requests
import tweepy
from bs4 import BeautifulSoup

# ============================
# 設定
# ============================
RSS_URL = "https://dr-liposuction.jp/feed/"  # あなたのRSS（必要なら変更）
POSTED_FILE = "posted.json"                  # 投稿済みを記録するファイル（同じ記事を二重投稿しないため）
DESC_LIMIT = 60                              # 説明文（日本語）を何文字までにするか

# ============================
# 投稿済み（posted.json）の読み書き
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
# 文字整形（説明文用）
# ============================
def shorten_ja(text: str, limit: int = 60) -> str:
    """日本語説明文を指定文字数に収める（長ければ末尾を…にする）"""
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    if len(t) <= limit:
        return t
    return t[:limit].rstrip("、。") + "…"

def clean_html_to_text(html: str) -> str:
    """HTMLをテキストにして余計な空白を整える"""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ").strip()

# ============================
# RSSから「扉絵（画像URL）」を拾う（最重要）
# ============================
def get_image_url_from_rss_entry(entry) -> str:
    """
    WordPress RSSに含まれる画像情報を優先して拾う
    - media:content
    - media:thumbnail
    - enclosure（links）
    """
    # 1) media_content
    mc = getattr(entry, "media_content", None)
    if mc and isinstance(mc, list) and mc:
        url = mc[0].get("url")
        if url:
            return url

    # 2) media_thumbnail
    mt = getattr(entry, "media_thumbnail", None)
    if mt and isinstance(mt, list) and mt:
        url = mt[0].get("url")
        if url:
            return url

    # 3) links の enclosure
    links = getattr(entry, "links", None)
    if links and isinstance(links, list):
        for l in links:
            if l.get("rel") == "enclosure":
                href = l.get("href")
                typ = (l.get("type") or "").lower()
                if href and (typ.startswith("image/") or href.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
                    return href

    return ""

# ============================
# 記事ページからOGP（保険：取れれば使う）
# ※ WAF/Cloudflare等で取得できない場合があるので必須にはしない
# ============================
def fetch_html(url: str) -> str:
    """URLのHTMLを取得（失敗したら空文字）"""
    try:
        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def get_og_image_url(article_url: str) -> str:
    """記事ページから og:image（扉絵URL）を取得（取れなければ空文字）"""
    html = fetch_html(article_url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # og:image
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"].strip()

    # og:image:secure_url
    tag = soup.find("meta", property="og:image:secure_url")
    if tag and tag.get("content"):
        return tag["content"].strip()

    return ""

def get_og_description(article_url: str) -> str:
    """記事ページから og:description（説明文）を取得（取れなければ空文字）"""
    html = fetch_html(article_url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:description")
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

# ============================
# 画像ダウンロード（Xに添付するため）
# ============================
def download_image(url: str, save_path: str) -> bool:
    """画像URLをダウンロードして保存（成功したらTrue）"""
    try:
        r = requests.get(
            url,
            timeout=25,
            stream=True,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0",
                # 画像直リンクを弾くサイト対策（Refererを付ける）
                "Referer": "https://dr-liposuction.jp/",
            },
        )
        r.raise_for_status()

        ctype = (r.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("image/"):
            return False

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print("download_image 失敗:", repr(e))
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

    # 4) 日本語の説明文（優先順位：OGP description → RSS summary）
    # ※ 取れない場合もあるのでRSS summaryを必ず持っておく
    description = get_og_description(link)
    if not description:
        # RSSのsummaryはHTMLの場合があるのでテキスト化
        description = clean_html_to_text(entry.get("summary", ""))
    description = shorten_ja(description, limit=DESC_LIMIT)

    # 5) ツイート本文（題名＋説明文＋続きはこちら！＋リンク）
    tweet_text = f"{title}\n{description}\n\n続きはこちら！\n{link}"

    # 6) 認証（v1.1で投稿＆画像アップロード）
    # GitHub Secrets:
    # API_KEY / API_SECRET / ACCESS_TOKEN / ACCESS_TOKEN_SECRET
    api_key = os.environ["API_KEY"]
    api_secret = os.environ["API_SECRET"]
    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = tweepy.OAuth1UserHandler(
        api_key,
        api_secret,
        access_token,
        access_token_secret,
    )
    api_v1 = tweepy.API(auth)

    # 7) 扉絵（画像URL）を取得
    # まずRSSから拾う（最優先）。取れない場合だけOGPを保険で見る。
    img_url = get_image_url_from_rss_entry(entry) or get_og_image_url(link)
    print("image_url =", img_url)

    media_id = None
    tmp_path = "/tmp/og_image.jpg"

    if img_url:
        ok = download_image(img_url, tmp_path)
        print("download_image =", ok)

        if ok:
            try:
                media = api_v1.media_upload(filename=tmp_path)
                media_id = media.media_id_string
                print("media_id =", media_id)
            except Exception as e:
                print("画像アップロードに失敗しました。画像なしで投稿します。理由:", repr(e))
    else:
        print("画像URLが取得できませんでした（空です）")

    # 8) 投稿（v1.1で実施：/2/tweets がCloudflare等で弾かれる回避策）
    try:
        if media_id:
            api_v1.update_status(status=tweet_text, media_ids=[media_id])
            print("画像付きで投稿しました（v1.1）。")
        else:
            api_v1.update_status(status=tweet_text)
            print("画像なしで投稿しました（v1.1）。")
    except Exception as e:
        # 失敗時はここで止めて、posted.jsonに記録しない
        print("投稿に失敗しました。理由:", repr(e))
        raise

    # 9) 投稿済みとして記録
    posted.append(entry_id)
    save_posted(posted)
    print("投稿済みIDを保存しました:", entry_id)

if __name__ == "__main__":
    main()
