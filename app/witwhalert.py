import requests, json, time, logging
import os, tweepy
from dotenv import load_dotenv

load_dotenv()

# Explorer API url
explorer_url = os.getenv('explorer_url')

# Explorer polling interval (secs). Be nice!
poll_secs_interval = int(os.getenv('poll_secs_interval'))
poll_try_limit = int(os.getenv('poll_try_limit'))

# Values (in WIT) over this threshold trigger a tweet
value_threshold = int(os.getenv('value_threshold'))

# Publish alerts as tweets
# Careful with booleans! dotenv retrieves config purely as strings.
enable_tweets = os.getenv('enable_tweets').lower() in ['true', 'yes','y']

# Twitter stuff
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

  tries = 0
  while tries < poll_try_limit:
    try:
      new_blocks_dict = requests.get(update_url)

      if new_blocks_dict:
        return new_blocks_dict.json()
      else:
        return {}

    except requests.exceptions.RequestException as e:
      tries += 1



def get_last_epoch():
  latest_blocks = update_blocks(0)

  if latest_blocks['blockchain']:
    last_epoch = latest_blocks['blockchain'][-1][1]
  else:
    print('Could not retrieve last epoch')
    last_epoch = 0

  return last_epoch


def get_last_confirmed_epoch():
  last_epoch = get_last_epoch()
  look_back  = 10
  confirmed_epoch = 0

  while confirmed_epoch == 0:

    target_epoch = last_epoch - look_back
    block_sample = update_blocks(target_epoch)

    for block in block_sample['blockchain']:
      logging.debug(f'Checking {block[0]} for confirmed status...')
      block_confirmed = block[10]
      if block_confirmed:
        confirmed_epoch = block[1]
        logging.info(f'{block[1]} - latest confirmed block is {block[0]}.')
        break
    look_back += look_back

  return confirmed_epoch


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
      print(f"    >> Account {tx['real_output_address']} received * {scaled_value:.0f} * WITs (txn hash: {tx['txn_hash']})")

      if scaled_value >= value_threshold:
        msg=f"    🦎🐳🔔 * 💰 {scaled_value:.0f} WITs changed hands! 💸 Assets went to {tx['real_output_address']}. 👀 Want to see it? -> https://witnet.network/search/{tx['txn_hash']}"
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


def start_up():
  #logging.basicConfig(filename='witwhalert.log', level=logging.INFO)
  logging.basicConfig(level=logging.INFO)
  logging.info("witwhalert v0.0.1")
  logging.info(f'Alert set on transactions >= [{value_threshold}] WITs.')
  logging.info(f'Enable tweets is [{enable_tweets}].' )
  print()


def main():
  start_up()

  if enable_tweets:
    setup_twitter_api()

  oldest_epoch = get_last_confirmed_epoch() - 1
  #oldest_epoch = 888302

  while True:

    latest_blocks = {}

    if (get_last_epoch() > oldest_epoch):

      latest_blocks = update_blocks( oldest_epoch )
      logging.debug(f'"Retrieving blocks: {latest_blocks}')

      if latest_blocks['blockchain']:
        print(f"> [{len(latest_blocks['blockchain'])}] blocks retrieved, processing ...")

        for block in latest_blocks['blockchain']:
          value_transfers = block[4]
          status_confirmed = block[10]

          # print only confirmed blocks
          if (status_confirmed == True):
            oldest_epoch = block[1]
            if (value_transfers > 0):
              print_block_info(get_block_details(block[0]))
              time.sleep(5)
            else:
              # confirmed block, but w/o vtx
              time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block[2]))
              print(f'{time_formatted} - {block[1]} - {block[0]} - no value transactions.')

    time.sleep(poll_secs_interval)


if __name__ == "__main__":
  main()
