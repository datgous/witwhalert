# witwhalert

Trivial python bot to track high value transactions in the [Witnet](https://witnet.io) blockchain.

Transactions over a configurable threshold trigger a Twitter post (requires a [Twitter devel](https://developer.twitter.com/) account).

Uses typical libraries such as requests, dotenv and [tweepy](https://www.tweepy.org/).

## Getting started

- Set up your python environment (venv module, or whatever floats your boat):

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- Set your [Twitter developer](https://developer.twitter.com/) credentials in the ```.env``` file :
```
cp .env.example .env
vi .env    # <- add your Twitter credentials

```
- Fire it up (probably better with screen/tmux/etc.)
```
python3 app/witwhalert.py
```

## Acknowledgments

This project blatantly free rides the fantastic work of the [Witnet block explorer](https://witnet.network), by @drcpu. Kudos! 🤟

## License

MIT.

