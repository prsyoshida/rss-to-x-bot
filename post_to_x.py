import os
import tweepy

def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env: {name}")
    return v

# ===== X API v2 クライアント =====
client = tweepy.Client(
    bearer_token=must_env("BEARER_TOKEN"),
    consumer_key=must_env("API_KEY"),
    consumer_secret=must_env("API_SECRET"),
    access_token=must_env("ACCESS_TOKEN"),
    access_token_secret=must_env("ACCESS_TOKEN_SECRET"),
)

# ===== 投稿内容（テスト）=====
tweet_text = (
    "【v2テスト投稿】\n"
    "GitHub Actions からの自動投稿テストです。\n"
    "#脂肪吸引 #豊胸 #美容外科"
)

# ===== 投稿 =====
res = client.create_tweet(text=tweet_text)

print("POST SUCCESS:", res.data)
