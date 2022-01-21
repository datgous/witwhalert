# witwhalert

Trivial python bot that tracks high value transactions in the [Witnet](https://witnet.io) blockchain.

When the value of a transaction exceeds a configurable threshold, an alert is sent. Follow [@witwhalert](https://twitter.com/witwhalert) in Twitter for an example.

Uses typical libraries such as requests, dotenv and [tweepy](https://www.tweepy.org/).

## Getting started

- Set up your python environment (use the ```venv``` module, or whatever floats your boat):

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- For integration with Twitter you will need a [developer account](https://developer.twitter.com/). This bot uses the [PIN-based OAuth](https://developer.twitter.com/en/docs/authentication/oauth-1-0a/pin-based-oauth) flow (OAuth1.0a, APIv2). Please read the documentation to determine if this meets your needs.

- Set your Twitter developer credentials and other config in the ```.env``` file :
```
cp .env.example .env
vi .env    # <- add your Twitter credentials here
```
- Fire it up (probably better with screen/tmux/etc.)
```
python3 app/witwhalert.py
```

## Acknowledgments

This project blatantly free rides the fantastic work of the [Witnet explorer](https://witnet.network), by [@drcpu](https://github.com/drcpu-github). Kudos! 🤟

## License

MIT.

