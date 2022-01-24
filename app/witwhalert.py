#!/usr/bin/env python3

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
low_threshold = int(os.getenv('low_threshold'))
high_threshold = int(os.getenv('high_threshold'))

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
    block_dict = requests.get(blocks_url, timeout=10)
  except Timeout:
    logging.info('request timed out')
    logging.debug("get_block/block_dict : ", block_dict)


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

  for i in range(0,4):
    try:
      new_blocks_dict = requests.get(update_url, timeout=10)

      if new_blocks_dict:
        return new_blocks_dict.json()
      else:
        return {}

    except requests.exceptions.RequestException as e:
      time.sleep(60)
      print('request exception! continue ...')
      continue

    print('successful request, breaking')
    break


def get_last_epoch():
  latest_blocks = update_blocks(0)

  if 'blockchain' in latest_blocks.keys():
    try:
      last_epoch = latest_blocks['blockchain'][-1][1]
    except IndexError:
      logging.info('Blocks retrieved, but could not find last epoch')
      logging.debug("get_last_epoch/latest_blocks : ", latest_blocks)
      last_epoch = 0
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


def twitter_utf_bold(amount):
  math_sans_bold = {
  0: "\uD835\uDFEC", 1: "\uD835\uDFED", 2: "\uD835\uDFEE", 3: "\uD835\uDFEF", 4: "\uD835\uDFF0",
  5: "\uD835\uDFF1", 6: "\uD835\uDFF2", 7: "\uD835\uDFF3", 8: "\uD835\uDFF4", 9: "\uD835\uDFF5" }

  amount_to_str = str(amount)
  boldened_str = ""

  for char in amount_to_str:
    if char in '0123456789':
      boldened_str += math_sans_bold[int(char)].encode('utf-16', 'surrogatepass').decode('utf-16')

  return boldened_str


def get_message(amount):
  # Partition the space between top&bottom value thresholds evenly,
  # returns a message according to the amount. Only the messages list should need amending.
  messages=[
  f"🦎🐳🔔 *",
  f"🦎🐳🐳🔔 * A humpback whale! Nice one -> ",
  f"🦎🐳🐳🐳🔔 * Whoa! A finback whale breached! That is BIG ->",
  f"🦎🐳🐳🐳🐳🔔 * A-M-A-Z-I-N-G! A blue whale!! Look at the size of that ->"
  ]

  if len(messages) == 0:
    return []
  elif len(messages) == 1:
    return messages[0]
  else:
    span = int( (high_threshold - low_threshold) / ( len(messages) - 1 ) )

    # locate amount in the amount space
    for p in range( len(messages) ):
      boundary = span * p + low_threshold

      if amount <= boundary:
        return messages[p-1]
        break
      elif amount >= high_threshold:
        return messages[-1]
        break


def print_block_info(block_dict):
  block_hash = block_dict['block_hash']
  epoch = block_dict['epoch']
  time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block_dict['time']))
  value_txns = get_value_txns(block_hash)

  print(f'{time_formatted} - {epoch} - {block_hash} ')

  if value_txns:
    for tx in value_txns:
      # Log to console and send tweet if over threshold (and tweets are enabled)
      scaled_value = int( tx['txn_value']*1E-9 )
      print(f"    >> Account {tx['real_output_address']} received * {scaled_value} * WITs (txn hash: {tx['txn_hash']})")

      if scaled_value >= low_threshold:
        output_addresses = ", ".join(tx['real_output_address'])
        bold_scaled_value = twitter_utf_bold(scaled_value)
        msg = get_message(scaled_value)
        msg = msg + f" 💰 {bold_scaled_value} WITs changed hands! 💸 Want to see it ? 👀 -> https://witnet.network/search/{tx['txn_hash']}"

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
  logging.info(f'Alert set on transactions >= [{low_threshold}] WITs.')
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

      if 'blockchain' in latest_blocks.keys():
        print(f"> [{len(latest_blocks['blockchain'])}] blocks retrieved, processing ...")

        for block in latest_blocks['blockchain']:
          value_transfers = block[4]
          is_confirmed = block[10]

          # print only confirmed blocks
          if (is_confirmed == True):
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
