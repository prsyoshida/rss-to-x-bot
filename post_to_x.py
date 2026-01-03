import os
import tweepy

def main():
    tweet_text = """脂肪吸引の合併症：知っておくべきポイントを専門医が解説
続きはこちら👇
https://dr-liposuction.jp/135/
#脂肪吸引 #豊胸 #美容外科
"""

    # ===== X API Client（OAuth1.0a / User context）=====
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )

    print("----- POST PREVIEW -----")
    print(tweet_text)
    print("------------------------")

    # ===== ここが重要：create_tweet を try / except で囲む =====
    try:
        client.create_tweet(text=tweet_text)
        print("✅ 投稿成功")
    except tweepy.Forbidden as e:
        print("❌ X API error: 403 Forbidden")
        if getattr(e, "response", None) is not None:
            print("Status:", e.response.status_code)
            print("Headers:", dict(e.response.headers))
            print("Body:", e.response.text)
        raise
    except Exception as e:
        print("❌ 予期しないエラー:", e)
        raise


if __name__ == "__main__":
    main()
