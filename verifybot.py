import time

import requests
import json
import pickle
import logging
from threading import Timer
from interactions import Client, Intents, listen, Status
from interactions import slash_command, SlashContext
from interactions import OptionType, slash_option

import os
from dotenv import load_dotenv

from datetime import datetime, timedelta

from json import JSONDecodeError

# first load the environment variables
load_dotenv()

LOG_FILE = f"verifybot_{datetime.now().strftime('%d-%m-%Y')}.log"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(i) for i in os.environ.get("GUILD_LIST").split(" ")]

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENDPOINT = "https://api-m.paypal.com"
PAYPAL_TOKEN = 0
LATEST_TOKEN_PATH = "latest-token.json"

RESOURCE_LIST = [str(i) for i in os.environ.get("RESOURCE_LIST").split(" ")]
RESOURCE_ID_LIST = [i.split(":")[0] for i in RESOURCE_LIST]
RESOURCE_ROLE_LIST = [i.split(":")[1] for i in RESOURCE_LIST]

ADMIN_ID_LIST = [int(i) for i in os.environ.get("ADMIN_ID_LIST").split(" ")]

DEBUG = False
APPEAR_OFFLINE = False

CHECK_PREVIOUSLY_VERIFIED = False
emails_verified = []
resource_ids_verified = []

# init discord client
bot = Client(intents=Intents.DEFAULT)


# --- functions ---

# this formats a date for submitting to the PayPal API endpoint
async def format_date(date):
    d = date.strftime('%Y-%m-%dT%H:%M:%SZ')
    return d


# this is for debugging / viewing responses from PayPal api
# def display_response(response):
#     print('response:', response)
#     print('url:', response.url)
#     print('text:', response.text)

# # this is for debugging / viewing data from PayPal api
# def display_data(data):
#     for key, value in data.items():
#         if key == 'scope':
#             for item in value.split(' '):
#                 print(key, '=', item)
#         else:
#             print(key, '=', value)

# read in any previously verified emails from file
async def read_in_emails():
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        try:
            with open('verified_emails', 'rb') as fp:
                emails_verified = pickle.load(fp)
        except FileNotFoundError:
            pass
        global resource_ids_verified
        try:
            with open('verified_resource_ids', 'rb') as fp:
                resource_ids_verified = pickle.load(fp)
        except FileNotFoundError:
            pass


# write out any previously verified emails to file
async def write_out_emails():
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        with open('verified_emails', 'wb') as fp:
            pickle.dump(emails_verified, fp)
        global resource_ids_verified
        with open('verified_resource_ids', 'wb') as fr:
            pickle.dump(resource_ids_verified, fr)


# check if an email has been previously verified
async def has_previously_verified(email, resource_id):
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        try:
            index = emails_verified.index(email)
            resources_verified = resource_ids_verified[index]
            for i in resources_verified.split(":"):
                if resource_id == i:
                    return True
        except ValueError:
            pass
    return False


# add email and resource id list to verified
async def add_previously_verified(email, resource_id):
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        index = 0
        try:
            index = emails_verified.index(email)
        except ValueError:
            pass
        global resource_ids_verified
        # get list of previously verified resource ids
        verified_ids = resource_ids_verified[index]
        verified_ids = verified_ids + ":" + resource_id
        resource_ids_verified[index] = verified_ids


# this gets an oauth token from the PayPal api
async def get_token():
    if os.path.exists(LATEST_TOKEN_PATH):
        try:
            with open(LATEST_TOKEN_PATH, "r") as infile:
                indata = json.loads(infile.read())
                infile.close()
        except JSONDecodeError:
            print(f'Invalid json in {LATEST_TOKEN_PATH}')
        else:
            if indata['expiration_time'] > time.time():
                token_expire = int(indata['expiration_time']) - time.time() - 100
                t = Timer(token_expire, get_token)
                t.daemon = True
                t.start()
                return indata['access_token']

    url = PAYPAL_ENDPOINT + '/v1/oauth2/token'

    payload = {
        "grant_type": "client_credentials"
    }

    response = requests.post(url, auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET), data=payload)
    data = response.json()

    # keep the token alive
    token_expire = int(data['expires_in']) - 100
    t = Timer(token_expire, get_token)
    t.daemon = True
    t.start()

    logging.info(f"Got new access token.")
    data['expiration_time'] = round(time.time() + token_expire)

    with open(LATEST_TOKEN_PATH, "w") as outfile:
        json.dump(data, outfile, indent=4)

    return data['access_token']


# this gets a list of transactions from the PayPal api ranging from start_date to end_date
async def get_transactions(start_date, end_date):
    url = PAYPAL_ENDPOINT + "/v1/reporting/transactions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PAYPAL_TOKEN}"
    }

    payload = {
        'start_date': f'{await format_date(start_date)}',
        'end_date': f'{await format_date(end_date)}',
        'fields': 'all'
    }

    response = requests.get(url, headers=headers, params=payload)

    data = response.text
    return data


# this is a discord bot command to add a role to a
async def add_role(ctx, role_id):
    member = ctx.member
    role = member.guild.get_role(role_id)
    await member.add_role(role)
    return role


# send a direct message to a list of admins
async def dm_admins(ctx, message):
    # user: discord.User
    for user_id in ADMIN_ID_LIST:
        user = ctx.author.guild.get_member(user_id)
        await user.send(message)


# this searches through all transactions to find matching emails
# if an email is found, it returns the resource id from the transaction
# if an email is not found, it returns an empty list
async def find_resource_ids_from_email(email, transactions):
    matching_ids = []
    try:
        for transaction in transactions["transaction_details"]:
            try:
                purchase_custom_field = transaction['transaction_info']['custom_field']
                purchase_email = transaction['payer_info']['email_address']
                # if purchase_email == 'test@example.com':
                #     print(purchase_custom_field)
                #     print(purchase_email)
                if purchase_email.lower() == email.lower():
                    s = purchase_custom_field.split('|')
                    s = s[len(s) - 1]
                    # only add matching resource id to list if it hasn't been verified yet
                    if not await has_previously_verified(email, s):
                        matching_ids.append(s)  # add the matching spigot resource id
            except KeyError:
                pass
    except KeyError:
        pass
    return matching_ids


# discord event that fires when the bot is ready and listening
@listen()
async def on_ready():
    # create logs folder if it doesn't exist
    if not os.path.exists("logs/"):
        os.mkdir("logs/")

    # set the logging config
    logging.basicConfig(
        handlers=[logging.FileHandler(f"logs/{LOG_FILE}", 'a+', 'utf-8')],
        level=logging.INFO,
        format='%(asctime)s: %(message)s'
    )

    if APPEAR_OFFLINE:
        await bot.change_presence(status=Status.OFFLINE)

    # get the oauth token needed for PayPal requests
    global PAYPAL_TOKEN
    PAYPAL_TOKEN = await get_token()

    # read in any previously verified emails
    await read_in_emails()

    print("Ready!")


# defines a new 'slash command' in discord and what options to show to user for params
@slash_command(
    name="verify",
    description="Verify your purchases"
)
@slash_option(
    name="email",
    description="The email address connected to your PayPal account",
    required=True,
    opt_type=OptionType.STRING
)
async def _verify_purchase(ctx: SlashContext, email: str):  # Defines a new "context" (ctx) command called "verify"

    logging.info(f"{ctx.author.global_name} ran command '/verify {email}'")

    available_roles = RESOURCE_ROLE_LIST.copy()

    # first check that the user doesn't already have the roles
    for role_element in RESOURCE_ROLE_LIST:
        if ctx.member.has_role(role_element):
            available_roles.remove(role_element)

    if len(available_roles) == 0:
        await ctx.send(f"You have already verified your purchases!", ephemeral=True)
        logging.info(f"{ctx.author.global_name} already had all verified roles.")
        return

    # get current timestamp in UTC
    end_date = datetime.today()

    await ctx.defer(ephemeral=True)

    roles_given = []
    # loop through purchases until a value is found or count == 36 (36 months is max for how far PayPal api can go back)
    count = 0
    success = False
    while len(available_roles) != 0 and count < 36:

        # search through purchases on 30-day intervals (PayPal api has a max of 31 days)
        start_date = end_date - timedelta(days=30)
        transactions = json.loads(await get_transactions(start_date, end_date))

        resource_ids = await find_resource_ids_from_email(email, transactions)

        # for all found resource ids in the PayPal transactions
        for resource_id in resource_ids:
            try:
                # get index of id in main resource id list
                index = RESOURCE_ID_LIST.index(resource_id)
                # get the corresponding resource role associated with that resource id
                role = RESOURCE_ROLE_LIST[index]
                available_roles.remove(role)
                success = True
                # add the email to previously verified emails (with the resource id)
                await add_previously_verified(email, resource_id)
                # add the configured discord role to the user who ran the command
                added_role = await add_role(ctx, role)
                roles_given.append(added_role.name)
                logging.info(f"{ctx.author.global_name} given role: " + role)
            except ValueError:
                pass

        # make new end_date the old start_date for next while iteration
        end_date = start_date
        count = count + 1

    if success:
        await ctx.send(f"Successfully verified PayPal purchase!", ephemeral=True)
        await dm_admins(ctx, "{} successfully verified a purchase with email: ".format(
            ctx.author.mention) + f"`{email}`. Given roles: {' '.join(roles_given)}")
        logging.info(f"{ctx.author.global_name} successfully verified their purchase")
        # write verified emails and resource ids out to files
        await write_out_emails()
    else:
        await ctx.send("Failed to verify PayPal purchase.", ephemeral=True)
        await dm_admins(ctx, "{} failed to verify a purchase with email: ".format(ctx.author.mention) + f"`{email}`")
        logging.info(f"{ctx.author.global_name} failed to verify their purchase")


# run the discord client with the discord token
bot.start(DISCORD_TOKEN)
