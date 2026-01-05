import os
import tweepy

auth = tweepy.OAuth1UserHandler(
    os.getenv("API_KEY"),
    os.getenv("API_SECRET"),
    os.getenv("ACCESS_TOKEN"),
    os.getenv("ACCESS_TOKEN_SECRET"),
)

api = tweepy.API(auth)

me = api.verify_credentials()
print("AUTH CHECK:", me.screen_name if me else "FAILED")

exit(0)
