#!/usr/bin/env python3

import requests, json, time, logging
import os, tweepy
from dotenv import load_dotenv
import telegram

load_dotenv()


def get_block(block_hash):
  poll_secs_interval = int(os.getenv('poll_secs_interval'))
  explorer_url = os.getenv('explorer_url')

  blocks_url= f"{explorer_url}/hash?value={block_hash}"
  block_dict={}

  try:
    block_dict = requests.get(blocks_url, timeout=10)
  except:
    backoff = (poll_secs_interval * 5)  # (poll_secs_interval * 2 ** tries)
    logging.info(f'Request failed for block with hash {block_hash}. Backing off {backoff} secs...')
    time.sleep(backoff)

  if not block_dict:
    print(f'Could not retrieve block {block_hash}')

  return block_dict.json()


def get_block_details(block_hash):
  block_dict=get_block(block_hash)

  return block_dict['details']


def update_blocks(last_epoch=0):
  explorer_url = os.getenv('explorer_url')

  if last_epoch == 0:
    update_url = f'{explorer_url}/blockchain?action=init&block=-1'
  else:
    update_url = f'{explorer_url}/blockchain?action=update&block={last_epoch}'


  try:
    new_blocks_dict = requests.get(update_url, timeout=10)

    if new_blocks_dict:
      return new_blocks_dict.json()
    else:
      return {}

  except:
    logging.error('Could not finish update_blocks, exception raised. Continue ...')
    #time.sleep(60)
    #continue
    return {}



def get_last_epoch():
  latest_blocks = update_blocks(0)

  if 'blockchain' in latest_blocks.keys():
    try:
      last_epoch = latest_blocks['blockchain'][-1][1]
    except IndexError:
      logging.error('Blocks retrieved, but could not find last epoch')
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
        logging.info(f'* {block[1]} - latest confirmed block is {block[0]}.')
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

  amount_to_str = f'{round(amount):,}'
  boldened_str = ""

  for char in amount_to_str:
    if char in '0123456789':
      boldened_str += math_sans_bold[int(char)].encode('utf-16', 'surrogatepass').decode('utf-16')
    elif char in ',':
      boldened_str += ','

  return boldened_str


def get_message(amount):
  # Partition the space between top&bottom value thresholds evenly,
  # returns a message according to the amount. Only the messages list should need amending.
  low_threshold = int(os.getenv('low_threshold'))
  high_threshold = int(os.getenv('high_threshold'))

  messages=[
  f"🔔🐳 *",
  f"🔔🐳🐳 * A humpback whale! Nice one.",
  f"🔔🐳🐳🐳 * Whoa! A finback whale breached!",
  f"🔔🐳🐳🐳🐳 * AMAZING! A massive blue whale!!"
  ]

  if len(messages) == 0:
    return []
  elif len(messages) == 1:
    return messages[0]
  else:
    span = int( (high_threshold - low_threshold) / ( len(messages) - 1 ) )

    if amount <= low_threshold:
      return messages[0]

    # locate amount in the amount space
    for p in range( len(messages) ):
      boundary = span * p + low_threshold
      if amount <= boundary:
        return messages[p-1]
      elif amount >= high_threshold:
        return messages[-1]


def print_block_info(block_dict, twitter_client, telegram_bot):

  # Values (in WIT) over this threshold trigger a tweet
  low_threshold = int(os.getenv('low_threshold'))
  high_threshold = int(os.getenv('high_threshold'))
  enable_tweets = os.getenv('enable_tweets').lower() in ['true', 'yes','y']
  enable_telegram = os.getenv('enable_telegram').lower() in ['true', 'yes','y']
  known_wallets_config = os.getenv('known_wallets_config')


  block_hash = block_dict['block_hash']
  epoch = block_dict['epoch']
  time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block_dict['time']))
  value_txns = get_value_txns(block_hash)

  print(f'{time_formatted} - {epoch} - {block_hash} ')

  if value_txns:
    for tx in value_txns:

      # Log to console and send alerts if over threshold (also send to twitter/telegram if enabled)
      scaled_value = int( tx['txn_value']*1E-9 )
      #logging.info(f"  >> Account {tx['real_output_address']} received * {scaled_value} * WITs (txn hash: {tx['txn_hash']})")
      logging.info(f" >> {scaled_value} WITs sent to {tx['real_output_address']} (tx: {tx['txn_hash']})")

      if scaled_value >= low_threshold:
        output_addresses = ", ".join(tx['real_output_address'])
        bold_scaled_value = twitter_utf_bold(scaled_value)
        msg = get_message(scaled_value)
        explorer_link = f"https://witnet.network/search/{tx['txn_hash']}"
        full_msg = msg + f" 💰 {bold_scaled_value} WITs were transferred! 💸 Take a look? 👀 ⇢ {explorer_link}"


        # transparency
        transparency_send_msg = ""
        transparency_receive_msg = ""

        if os.path.exists(known_wallets_config):
          with open(known_wallets_config,'r') as wallet_file:
             KNOWN_WALLETS = json.load(wallet_file)
             logging.info(f"Read known wallets file {known_wallets_config}")

          for input_address in tx['input_address']:
              if input_address in KNOWN_WALLETS.keys():
                  transparency_send_msg = f"🔔📸 * The {KNOWN_WALLETS[input_address]} wallet sent {bold_scaled_value} WITs."

          for output_address in tx['real_output_address']:
              if output_address in KNOWN_WALLETS.keys():
                  transparency_receive_msg = f"🔔📸 * The {KNOWN_WALLETS[output_address]} wallet received {bold_scaled_value} WITs."

        else:
          logging.info(f"transparency data not found, please create {known_wallets_config}.")


        if transparency_send_msg and transparency_receive_msg:
          full_msg = f"🔔📸 * The {KNOWN_WALLETS[input_address]} wallet sent {bold_scaled_value} WITs to the {KNOWN_WALLETS[output_address]} wallet."
        elif transparency_send_msg:
          full_msg = transparency_send_msg
        elif transparency_receive_msg:
          full_msg = transparency_receive_msg


        # Alerts to console & messengers
        logging.info(full_msg)

        if enable_tweets:
          twitter_post(twitter_client, full_msg)

        if enable_telegram:
          if transparency_send_msg or transparency_receive_msg:
            full_msg = full_msg + f" <a href='{explorer_link}'>Check the transaction</a>."
          else:
            full_msg = msg + f" 💰 {bold_scaled_value} WITs <a href='{explorer_link}'>were transferred</a>!"

          telegram_post(telegram_bot, full_msg)


def setup_twitter_api():
  consumer_key = os.getenv('consumer_key')
  consumer_secret = os.getenv('consumer_secret')

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

  return tweepy.Client( consumer_key = consumer_key,
                          consumer_secret = consumer_secret ,
                          access_token = auth.access_token,
                          access_token_secret = auth.access_token_secret)


def twitter_post(twitter_client, message):
  try:
    response = twitter_client.create_tweet(text=message)
  except:
    logging.info("Could not post to Twitter.")


def setup_telegram_api():
  telegram_token = os.getenv('telegram_token')

  try:
    telegram_bot = telegram.Bot(token=telegram_token)
    return telegram_bot
  except:
    logging.info("Telegram auth failed. Is the bot's token correct?")


def telegram_get_chat_id(telegram_bot, telegram_chat_name):

  telegram_chat_id = os.getenv('telegram_chat_id')
  telegram_chat_name = os.getenv('telegram_chat_name')

  if not telegram_chat_id:
    try:
      updates = telegram_bot.get_updates()
      for u in updates:
        try:
          if u.message.chat.title == telegram_chat_name:
            telegram_chat_id = u.message.chat.id
            break
        except:
          # no chat attribute
          continue

    except:
      logging.error("Could not get Telegram updates.")

  if not telegram_chat_id:
    logging.error("Could not find chat_id for chat ", telegram_chat_name)

  return telegram_chat_id


def telegram_post(telegram_bot, message):
  telegram_chat_id = os.getenv('telegram_chat_id')

  if not telegram_chat_id:
    telegram_chat_name = os.getenv('telegram_chat_name')
    telegram_chat_id = telegram_get_chat_id(telegram_bot, telegram_chat_name)

  try:
    telegram_bot.send_message(text=message, chat_id=telegram_chat_id, disable_web_page_preview=True, parse_mode='html')
  except:
    logging.info("Could not post to Telegram.")


def start_up(twitter_client, telegram_bot):

  enable_tweets = os.getenv('enable_tweets').lower() in ['true', 'yes','y']
  enable_telegram = os.getenv('enable_telegram').lower() in ['true', 'yes','y']
  low_threshold = int(os.getenv('low_threshold'))
  high_threshold = int(os.getenv('high_threshold'))

  if enable_tweets:
    twitter_client = setup_twitter_api()
  if enable_telegram:
    telegram_bot = setup_telegram_api()

  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(message)s",
      handlers=[
          logging.FileHandler('witwhalert.log'),
          logging.StreamHandler()
      ]
  )

  logging.info("witwhalert v0.0.1")
  logging.info(f'Alert on transactions >= [{low_threshold}-{high_threshold}] WITs.')
  logging.info(f'Enable tweets is [{enable_tweets}].' )
  logging.info(f'Enable telegram is [{enable_telegram}].' )


  return twitter_client, telegram_bot


def main():

  poll_secs_interval = int(os.getenv('poll_secs_interval'))
  poll_try_limit = int(os.getenv('poll_try_limit'))

  twitter_client = telegram_bot = None
  twitter_client, telegram_bot = start_up(twitter_client, telegram_bot)

  oldest_epoch = get_last_confirmed_epoch() - 1
  #oldest_epoch = 914712

  while True:

    latest_blocks = {}

    if (get_last_epoch() > oldest_epoch):

      latest_blocks = update_blocks( oldest_epoch )
      logging.debug(f'"Retrieving blocks: {latest_blocks}')

      if 'blockchain' in latest_blocks.keys():
        logging.info(f"> [{len(latest_blocks['blockchain'])}] blocks retrieved, processing ...")

        for block in latest_blocks['blockchain']:
          value_transfers = block[4]
          is_confirmed = block[10]

          # print only confirmed blocks
          if (is_confirmed == True):
            oldest_epoch = block[1]
            if (value_transfers > 0):
              print_block_info(get_block_details(block[0]), twitter_client, telegram_bot)
              time.sleep(5)
            else:
              # confirmed block, but w/o vtx
              time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block[2]))
              print(f'{time_formatted} - {block[1]} - {block[0]} - no value transactions.')

    time.sleep(poll_secs_interval)


if __name__ == "__main__":
  main()
