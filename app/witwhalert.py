#!/usr/bin/env python3

import requests, json, time, logging, os, random
from dotenv import load_dotenv
import tweepy, telegram
import time
from datetime import datetime

load_dotenv()

def get_block(block_hash):
  poll_secs_interval = int(os.getenv('poll_secs_interval'))
  explorer_url = os.getenv('explorer_url')

  blocks_url= f"{explorer_url}/api/hash?value={block_hash}"
  block_dict={}

  try:
    block_dict = requests.get(blocks_url, timeout=10)
    return block_dict.json()
  except:
    backoff = (poll_secs_interval * 5)  # (poll_secs_interval * 2 ** tries)
    logging.error(f'Request failed for block with hash {block_hash}. Backing off {backoff} secs...')
    time.sleep(backoff)


def get_block_details(block_hash):
  block_dict=get_block(block_hash)

  return block_dict['details']


def update_blocks(last_epoch=0):
  explorer_url = os.getenv('explorer_url')

  if last_epoch == 0:
    update_url = f'{explorer_url}/api/blockchain?action=init&block=-1'
  else:
    update_url = f'{explorer_url}/api/blockchain?action=append&block={last_epoch}'


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

  try:
    if  block_dict['value_transfer_txns']:

      for vtx in block_dict['value_transfer_txns']:
        txn_hash = vtx['txn_hash']
        input_address = vtx['unique_input_addresses']
        real_output_address = vtx['real_output_addresses']
        txn_value = (vtx['value'])
        vtt_entry = {'txn_hash': txn_hash, 'input_address': input_address, 'real_output_address': real_output_address, "txn_value": txn_value }
        value_txns.append(vtt_entry)

    return value_txns

  except TypeError as e:
    logging.error('No value_transfer txns in block', block_hash)
    logging.debug("TypeError returned: ", e)


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

def all_messages():
  messages= [
  { "weight": "0.30", "limit": "6000", "txt": "🔔🌱 * Plankton. So tiny." },
  { "weight": "0.35", "limit": "12000", "txt": "🔔🦐 * Hah! Little prawn." },
  { "weight": "0.35", "limit": "25000", "txt": "🔔🐡 * Fugu, small and toxic." },
  { "weight": "0.40", "limit": "35000", "txt": "🔔🐟 * A delicious sardine." },
  { "weight": "0.45", "limit": "45000", "txt": "🔔🐠 * A pretty parrotfish." },
  { "weight": "0.50", "limit": "50000", "txt": "🔔🐟 * Tuna in the almadraba." },
  { "weight": "0.60", "limit": "125000", "txt": "🔔🐬 * A surfer dolphin!" },
  { "weight": "1.00", "limit": "400000", "txt": "🔔🐳 * A minke whale! Beautiful." },
  { "weight": "1.00", "limit": "500000", "txt": "🔔🐳🐳 * A humpback whale! Nice one." },
  { "weight": "1.00", "limit": "800000", "txt": "🔔🐳🐳🐳 * Whoa! A finback whale breached!" },
  { "weight": "1.00", "limit": "1500000", "txt": "🔔🐳🐳🐳🐳 * AMAZING! A massive blue whale!!" },
  { "weight": "1.00", "limit": "5000000", "txt": "🔔🐙🐙🐙🐙🐙 * Can't be... IT's a KRAKEN!!" },
  { "weight": "1.00", "limit": "10000000", "txt": "🔔🐍🐍🐍🐍🐍 * Run for your lives! IT's LEVIATHAN!!" },
  ]
  return messages


def lowest_threshold():
  messages = all_messages()
  limit_values = [ int(msg["limit"]) for msg in messages ]
  lower_limit = min(limit_values)
  return lower_limit


def get_message(amount):
  amount = int(amount)
  messages = all_messages()
  lower_limit = lowest_threshold()

  if amount < lower_limit:
    return []

  for msg in messages:
      if amount >= int(msg["limit"]):
          txt = msg["txt"]
          weight = float(msg["weight"])
          limit = msg["limit"]

  dice = random.uniform(0, 1)

  # messages are published or not depending on dice vs weight
  if weight >= dice:
      logging.info(f"Lucky dice -> amount: {amount}, limit: {limit}, weight: {weight}, dice: {dice}")
      return txt
  else:
      logging.info(f"Unlucky dice -> amount: {amount}, limit: {limit}, weight: {weight}, dice: {dice}")
      return []


def get_transparency_message(tx):
    known_wallets_config = os.getenv('known_wallets_config')

    transparency_send_msg = ""
    transparency_receive_msg = ""

    if os.path.exists(known_wallets_config):
        with open(known_wallets_config, 'r') as wallet_file:
            KNOWN_WALLETS = json.load(wallet_file)
            logging.info(f"Read known wallets file {known_wallets_config}")

        for input_address in tx['input_address']:
            if input_address in KNOWN_WALLETS:
                transparency_send_msg = f"🔔📸 * The known {KNOWN_WALLETS[input_address]} wallet sent some ⇢"

        for output_address in tx['real_output_address']:
            if output_address in KNOWN_WALLETS:
                transparency_receive_msg = f"🔔📸 * The known {KNOWN_WALLETS[output_address]} wallet received some ⇢"

    else:
        logging.info(f"Transparency data not found, please create {known_wallets_config}.")

    if transparency_send_msg and transparency_receive_msg:
        return f"🔔📸 * The known {KNOWN_WALLETS[input_address]} wallet sent {bold_scaled_value} WITs to the known {KNOWN_WALLETS[output_address]} wallet."
    elif transparency_send_msg:
        return transparency_send_msg
    elif transparency_receive_msg:
        return transparency_receive_msg
    else:
        return ""  # Return an empty string if no transparency message is found


def get_rate_limit_config():
    # Your logic to fetch or derive the rate limit values
    max_calls = int(os.getenv('msg_max'))
    period = int(os.getenv('msg_period'))

    return max_calls, period

def rate_limited():
    max_calls, period = get_rate_limit_config()
    last_time_called = time.monotonic()
    num_calls = 0

    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal last_time_called, num_calls
            now = time.monotonic()

            if now - last_time_called >= period:
                # Reset counter if period is finished
                last_time_called = now
                num_calls = 0

            if num_calls >= max_calls:
              # Throttle if limit is exceeded
              logging.warning(f"Function {func.__name__} exceeded {max_calls} calls per {period} second period")

            else:
              num_calls += 1
              return func(*args, **kwargs)

        return wrapper
    return decorator


def print_block_info(block_dict, twitter_client, telegram_bot):

    # Values (in WIT) over this threshold trigger a tweet
    lower_limit = lowest_threshold()
    enable_tweets = os.getenv('enable_tweets').lower() in ['true', 'yes','y']
    enable_telegram = os.getenv('enable_telegram').lower() in ['true', 'yes','y']
    explorer_url = os.getenv('explorer_url')

    block_hash = block_dict['block_hash']
    epoch = block_dict['epoch']
    time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block_dict['time']))
    value_txns = get_value_txns(block_hash)

    logging.info(f'{time_formatted} - {epoch} - {block_hash} ')

    if value_txns:
        for tx in value_txns:
            scaled_value = int(tx['txn_value'] * 1E-9)
            logging.info(f"  >> {scaled_value} WITs sent to {tx['real_output_address']} (tx: {tx['txn_hash']})")

            if scaled_value >= lower_limit:
                output_addresses = ", ".join(tx['real_output_address'])
                bold_scaled_value = twitter_utf_bold(scaled_value)

                # If tx belongs to a known wallet, get transparency message.
                transparency_msg = get_transparency_message(tx)

                if transparency_msg:
                    msg = transparency_msg
                else:
                    msg = get_message(scaled_value)

                # msg is blank if no messages are configured, amount is lower than low_threshold, or dice wins weight.
                if msg:
                  explorer_link = f"{explorer_url}/search/{tx['txn_hash']}"
                  full_msg = msg + f" 💰 {bold_scaled_value} WITs were transferred! 💸 Take a look? 👀 ⇢ {explorer_link}"

                  logging.info(full_msg)

                  if enable_tweets:
                      logging.debug(f"Sending message to Twitter...")
                      twitter_post(twitter_client, full_msg)

                  if enable_telegram:
                      logging.debug("Sending message to Telegram...")
                      full_msg = msg + f" 💰 {bold_scaled_value} WITs were transferred! 💸 <a href='{explorer_link}'>Check the transaction</a>."
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

@rate_limited()
def twitter_post(twitter_client, message):
  try:
    response = twitter_client.create_tweet(text=message)
  except:
    logging.warning("Could not post to Twitter.")


def setup_telegram_api():
  telegram_token = os.getenv('telegram_token')

  try:
    telegram_bot = telegram.Bot(token=telegram_token)
    return telegram_bot
  except:
    logging.warning("Telegram auth failed. Is the bot's token correct?")


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


@rate_limited()
def telegram_post(telegram_bot, message):
  telegram_chat_id = os.getenv('telegram_chat_id')

  if not telegram_chat_id:
    telegram_chat_name = os.getenv('telegram_chat_name')
    telegram_chat_id = telegram_get_chat_id(telegram_bot, telegram_chat_name)

  try:
    telegram_bot.send_message(text=message, chat_id=telegram_chat_id, disable_web_page_preview=True, parse_mode='html')
  except RateLimitException as e:
    logging.warning(f"Rate limit exceeded: {e}")
    pass
  except:
    logging.info("Could not post to Telegram.")
    pass

def start_up(twitter_client, telegram_bot):

  log_level = logging.getLevelName(os.getenv('log_level'))
  enable_tweets = os.getenv('enable_tweets').lower() in ['true', 'yes','y']
  enable_telegram = os.getenv('enable_telegram').lower() in ['true', 'yes','y']
  low_threshold = lowest_threshold()


  if enable_tweets:
    twitter_client = setup_twitter_api()
  if enable_telegram:
    telegram_bot = setup_telegram_api()

  logging.basicConfig(
      level=log_level,
      format="%(asctime)s [%(levelname)s] %(message)s",
      handlers=[
          logging.FileHandler('witwhalert.log'),
          logging.StreamHandler()
      ]
  )

  logging.info("witwhalert v0.0.2")
  logging.info(f'Alert on transactions >= [{low_threshold}] WITs.')
  logging.info(f'Enable tweets is [{enable_tweets}].' )
  logging.info(f'Enable telegram is [{enable_telegram}].' )


  return twitter_client, telegram_bot


def main():

  poll_secs_interval = int(os.getenv('poll_secs_interval'))
  poll_try_limit = int(os.getenv('poll_try_limit'))

  twitter_client = telegram_bot = None
  twitter_client, telegram_bot = start_up(twitter_client, telegram_bot)


  last_confirmed_epoch = get_last_confirmed_epoch()
  #last_confirmed_epoch = 2179365

  while True:

    latest_blocks = {}

    if (get_last_epoch() > last_confirmed_epoch):

      latest_blocks = update_blocks( last_confirmed_epoch )
      logging.debug(f'Retrieving blocks: {latest_blocks}')

      if 'blockchain' in latest_blocks:
        logging.info(f"> [{len(latest_blocks['blockchain'])}] blocks retrieved, processing ...")

        block_list = latest_blocks['blockchain']
        block_list.sort(key= lambda r:r[1])  # reverse block list for more intuitive output.

        for block in block_list:
          value_transfers = block[4]
          is_confirmed = block[10]

          # print only confirmed blocks
          if (is_confirmed == True):

            last_confirmed_epoch = block[1] + 1

            if (value_transfers > 0):
              print_block_info(get_block_details(block[0]), twitter_client, telegram_bot)
              time.sleep(5)
            else:
              # confirmed block, but w/o vtx
              datetime_obj = datetime.fromtimestamp(block[2])
              time_formatted = datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
              print(f'{time_formatted} - {block[1]} - {block[0]} - no value transactions.')

    time.sleep(poll_secs_interval)


if __name__ == "__main__":
  main()
