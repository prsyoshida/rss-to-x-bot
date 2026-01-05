import os
import tweepy

def build_tweet() -> str:
    return (
        "脂肪吸引の合併症：知っておくべきポイントを専門医が解説\n"
        "続きはこちら👇\n"
        "https://dr-liposuction.jp/135/\n"
        "#脂肪吸引 #豊胸 #美容外科"
    )

def main():
    tweet_text = build_tweet()

    print("----- POST PREVIEW -----")
    print(tweet_text)
    print("------------------------")

    # OAuth 1.0a (User context) for API v1.1
    auth = tweepy.OAuth1UserHandler(
        os.environ["API_KEY"],
        os.environ["API_SECRET"],
        os.environ["ACCESS_TOKEN"],
        os.environ["ACCESS_TOKEN_SECRET"],
    )

    api = tweepy.API(auth, wait_on_rate_limit=True)

    try:
        api.update_status(status=tweet_text)  # v1.1 posting
        print("✅ 投稿成功（v1.1 update_status）")
    except tweepy.TweepyException as e:
        # TweepyException includes response sometimes
        print("❌ 投稿失敗:", repr(e))
        # 可能ならレスポンス本文を出す
        resp = getattr(e, "response", None)
        if resp is not None:
            print("Status:", resp.status_code)
            print("Headers:", dict(resp.headers))
            print("Body:", resp.text[:2000])  # 長いのでカット
        raise

if __name__ == "__main__":
    main()
