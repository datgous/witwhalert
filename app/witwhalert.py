import requests, json, time
import os, tweepy
from dotenv import load_dotenv

# Explorer API url
explorer_url = 'https://witnet.network/api'

# Explorer polling interval (secs). Be nice!
poll_secs_interval = 60

# Values (in WIT) over this threshold trigger a tweet
value_threshold = 60000

# Publish alerts as tweets
enable_tweets = True

# Twitter stuff
load_dotenv()
consumer_key = os.getenv('consumer_key')
consumer_secret = os.getenv('consumer_secret')
client = ""


def get_block(block_hash):
  blocks_url= f"{explorer_url}/hash?value={block_hash}"
  block_dict={}

  try:
    block_dict = requests.get(blocks_url)
  except requests.exceptions.RequestException as e:
    raise SystemExit(e)

  if not block_dict:
    print(f'Could not retrieve block {block_hash}')

  return block_dict.json()


def get_block_details(block_hash):
  block_dict=get_block(block_hash)

  return block_dict['details']


def update_blocks(last_epoch=0):
  if last_epoch == 0:
    update_url = f'{explorer_url}/blockchain?action=init&block=-1'
  else:
    update_url = f'{explorer_url}/blockchain?action=update&block={last_epoch}'

  try:
    new_blocks_dict = requests.get(update_url)
  except requests.exceptions.RequestException as e:
    raise SystemExit(e)

  if new_blocks_dict:
    return new_blocks_dict.json()
  else:
    return {}


def get_last_epoch():
  latest_blocks = update_blocks(0)

  if latest_blocks['blockchain']:
    last_epoch = latest_blocks['blockchain'][-1][1]
  else:
    print('Could not retrieve last epoch')
    last_epoch = 0

  return last_epoch


def get_value_txns(block_hash):
  block_dict = get_block(block_hash)
  value_txns = []

  if  block_dict['value_transfer_txns']:

    for vtx in block_dict['value_transfer_txns']:
      txn_hash = vtx['txn_hash']
      input_address = vtx['unique_input_addresses']
      real_output_address = vtx['real_output_addresses']
      txn_value = (vtx['value'])
      vtt_entry = {'txn_hash': txn_hash, 'input_address': input_address, 'real_output_address': real_output_address, "txn_value": txn_value }
      value_txns.append(vtt_entry)

  return value_txns


def print_block_info(block_dict):
  block_hash = block_dict['block_hash']
  epoch = block_dict['epoch']
  time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block_dict['time']))
  value_txns = get_value_txns(block_hash)

  print(f'{time_formatted} - {epoch} - {block_hash} ')

  if value_txns:
    for tx in value_txns:
      # Log to console and send twit if over threshold
      scaled_value = tx['txn_value']*1E-9
      print(f"    >> Account {tx['real_output_address']} received * {scaled_value:.2f} * WITs (txn hash: {tx['txn_hash']})")

      if scaled_value >= value_threshold:
        msg=f"    🦎🐳🔔 * 💰 {scaled_value:.2f} WITs changed hands! 💸 Assets went to {tx['real_output_address']}. 👀 See the transaction log -> https://witnet.network/search/{tx['txn_hash']}"
        print(msg)
        if enable_tweets:
          twitter_post(msg)


def setup_twitter_api():
  # api credentials
  auth = tweepy.OAuthHandler(consumer_key, consumer_secret, 'oob')

  # get access token, print authorisation URL
  auth_url = auth.get_authorization_url()
  print('Authorization URL: ' + auth_url)

  # open auth_url in a browser, (manually) copy the PIN code
  pin_code = input('PIN: ').strip()
  auth.get_access_token(pin_code)
  print('ACCESS_TOKEN = "%s"' % auth.access_token)
  print('ACCESS_TOKEN_SECRET = "%s"' % auth.access_token_secret)

  global client
  client = tweepy.Client( consumer_key = consumer_key,
                          consumer_secret = consumer_secret ,
                          access_token = auth.access_token,
                          access_token_secret = auth.access_token_secret)

def twitter_post(message):
  response = client.create_tweet(text=message)


def main():
  print("witwhalert v0.0.1")
  print(f'Alert set on transactions >= [{value_threshold}] WITs.')
  print(f'Enable tweets is [{enable_tweets}].' )
  print()

  if enable_tweets:
    setup_twitter_api()

  oldest_epoch = get_last_epoch() - 1
  #oldest_epoch = 878638

  while True:

    latest_blocks = {}

    if (get_last_epoch() > oldest_epoch):

      latest_blocks = update_blocks( oldest_epoch )

      if latest_blocks['blockchain']:

        for b in latest_blocks['blockchain']:
          print_block_info(get_block_details(b[0]))
          time.sleep(5)

        oldest_epoch = latest_blocks['blockchain'][-1][1]

    time.sleep(poll_secs_interval)


if __name__ == "__main__":
  main()
