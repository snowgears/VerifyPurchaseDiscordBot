import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from threading import Timer
import re

import discord
import requests
from discord.ext import commands
import asyncio
from discord.utils import get
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option
from dotenv import load_dotenv

# first load the environment variables
load_dotenv()

# regular expression for validating an Email
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = [int(os.environ.get("GUILD_ID"))]
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID"))
VERIFY_CHANNEL_ID = int(os.environ.get("VERIFY_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.environ.get("ADMIN_ROLE_ID"))
ADMIN_ID_LIST = []
if bool(os.environ.get("ADMIN_ID_LIST") and os.environ.get("ADMIN_ID_LIST").strip()):
    ADMIN_ID_LIST = [int(i) for i in os.environ.get("ADMIN_ID_LIST").split(" ")]

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENDPOINT = "https://api-m.paypal.com"
PAYPAL_TOKEN = 0

RESOURCES = {}
for resource in os.environ.get("RESOURCE_LIST").split(" "):
    resource_name = resource.split(":")[0]
    resource_roles = (resource.split(":")[1]).split(",")
    RESOURCES[resource_name] = resource_roles

DEBUG = False
APPEAR_OFFLINE = True

CHECK_PREVIOUSLY_VERIFIED = False
emails_verified = []
resource_names_verified = []

# init discord client
client = discord.Client(intents=discord.Intents.all())
bot = commands.Bot(command_prefix='!')

# declare the discord slash commands through the client.
slash = SlashCommand(client, sync_commands=True)


# --- functions ---

# this formats a date for submitting to the PayPal API endpoint
async def format_date(date):
    d = date.strftime('%Y-%m-%dT%H:%M:%SZ')
    return d


def check_email(email):
    if re.fullmatch(regex, email):
        return True
    else:
        return False


# this is for debugging / viewing reponses from paypal api
# def display_response(response):
#     print('response:', response)
#     print('url:', response.url)
#     print('text:', response.text)

# # this is for debugging / viewing data from paypal api
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
        global resource_names_verified
        try:
            with open('verified_resource_names', 'rb') as fp:
                resource_names_verified = pickle.load(fp)
        except FileNotFoundError:
            pass


# write out any previously verified emails to file
async def write_out_emails():
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        with open('verified_emails', 'wb') as fp:
            pickle.dump(emails_verified, fp)
        global resource_names_verified
        with open('verified_resource_names', 'wb') as fr:
            pickle.dump(resource_names_verified, fr)


# check if an email has been previously verified
async def has_previously_verified(email, resource_name):
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        try:
            index = emails_verified.index(email)
            resources_verified = resource_names_verified[index]
            for i in resources_verified.split(":"):
                if resource_name == i:
                    return True
        except ValueError:
            pass
    return False


# add email and resource name list to verified
async def add_previously_verified(email, resource_name):
    if CHECK_PREVIOUSLY_VERIFIED:
        global emails_verified
        index = 0
        try:
            index = emails_verified.index(email)
        except ValueError:
            pass
        global resource_names_verified
        # get list of previously verified resource names
        verified_names = resource_names_verified[index]
        verified_names = verified_names + ":" + resource_name
        resource_names_verified[index] = verified_names


# this gets an oauth token from the paypal api
def update_token():
    url = PAYPAL_ENDPOINT + '/v1/oauth2/token'

    payload = {
        "grant_type": "client_credentials"
    }

    response = requests.post(url, auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET), data=payload)
    data = response.json()

    # keep the token alive
    token_expire = int(data['expires_in']) - 60
    t = Timer(token_expire, update_token)
    t.daemon = True
    t.start()

    logging.info(f"Got new access token.")
    print("Got new access token.")
    global PAYPAL_TOKEN
    PAYPAL_TOKEN = data['access_token']


# this gets a list of transactions from the paypal api ranging from start_date to end_date
async def get_transactions(start_date, end_date):
    url = PAYPAL_ENDPOINT + "/v1/reporting/transactions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PAYPAL_TOKEN}"
    }

    payload = {
        'start_date': f'{await format_date(start_date)}',
        'end_date': f'{await format_date(end_date)}',
        'transaction_status': 'S',
        'fields': 'cart_info, payer_info'
    }

    response = requests.get(url, headers=headers, params=payload)

    data = response.text
    return data


@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return
    role = discord.utils.get(message.guild.roles, id=ADMIN_ROLE_ID)
    if role in message.author.roles:
        return
    if message.channel.id == VERIFY_CHANNEL_ID:
        await message.delete()


# this is a discord bot command to add a role to a user
@bot.command(pass_context=True)
async def add_role(ctx, role_id):
    member = ctx.author
    role = get(member.guild.roles, id=int(role_id))
    await member.add_roles(role)


# send a direct message to a list of admions
@bot.command(pass_context=True)
async def dm_admins(ctx, email, username, roles_given, verified):
    # user: discord.User
    if verified:
        message = "{} successfully verified a purchase with email: ".format(
            ctx.author.mention) + f"{email} and username: {username}. Given roles: "
        for role_id in roles_given:
            message = message + f"<@&{role_id}> "
    else:
        message = "{} failed to verify a purchase with email: ".format(
            ctx.author.mention) + f"{email} and username: {username}"
    for user_id in ADMIN_ID_LIST:
        user = ctx.author.guild.get_member(user_id)
        await user.send(message)


# send a message into a channel
@bot.command(pass_context=True)
async def channel_message(author, email, username, roles, verified):
    channel = client.get_channel(REPORT_CHANNEL_ID)
    roles_message = ""
    if verified:
        embed = discord.Embed(title="Purchase verify of premium plugins",
                              description="Purchase verification completed for {}!".format(author.mention),
                              color=0x2ecc71)
        for role_id in roles:
            roles_message = roles_message + f"<@&{role_id}> "
    else:
        embed = discord.Embed(title="Purchase verify of premium plugins",
                              description="Purchase verification failed for {}!".format(author.mention),
                              color=0xe74c3c)
    embed.add_field(name="Email", value=email, inline=True)
    embed.add_field(name="Username", value=username, inline=True)
    if verified:
        embed.add_field(name="Roles", value=roles_message, inline=False)
    await channel.send(embed=embed)


# this searches through all transactions to find matching emails
# if an email is found, it returns the resource name from the transaction
# if an email is not found, it returns an empty list
async def find_resource_names_from_email(email, transactions):
    matching_names = []
    try:
        for transaction in transactions["transaction_details"]:
            try:
                purchase_item_name = transaction['cart_info']['item_details'][0]['item_name']
                purchase_email = transaction['payer_info']['email_address']
                # if purchase_email == 'test@example.com':
                #     print(purchase_custom_field)
                #     print(purchase_email)
                if purchase_email.lower() == email.lower():
                    pl_name = (purchase_item_name.split('|')[0]).replace("Purchase Resource:", "")
                    pl_name = pl_name.strip()
                    # only add matching resource name to list if it hasnt been verified yet
                    if not await has_previously_verified(email, pl_name):
                        matching_names.append(pl_name)  # add the matching spigot resource name)
            except KeyError:
                pass
    except KeyError:
        pass
    return matching_names


# discord event that fires when the bot is ready and listening
@client.event
async def on_ready():
    # set the logging config
    logging.basicConfig(handlers=[logging.FileHandler('verifybot.log', 'a+', 'utf-8')], level=logging.INFO,
                        format='%(asctime)s: %(message)s')

    if APPEAR_OFFLINE:
        await client.change_presence(status=discord.Status.offline)

    # get the oauth token needed for paypal requests
    update_token()

    # read in any previously verified emails
    await read_in_emails()

    print("Ready!")


# defines a new 'slash command' in discord and what options to show to user for params
@slash.slash(name="verify",
             description="Verify your plugins purchase.",
             options=[
                 create_option(
                     name="email",
                     description="Your paypal email.",
                     option_type=3,
                     required=True
                 ),
                 create_option(
                     name="username",
                     description="Your SpigotMc or McMarket username.",
                     option_type=3,
                     required=True
                 )
             ],
             guild_ids=GUILD_ID)
async def _verifypurchase(ctx, email: str, username: str):  # Defines a new "context" (ctx) command called "paypal."

    if not (ctx.channel.id == VERIFY_CHANNEL_ID):
        return

    logging.info(f"{ctx.author.name} ran command '/paypal {email}'")

    if not check_email(email):
        await ctx.send(f"You must provide a valid email!", hidden=True)
        return

    available_roles = []

    for name_element in RESOURCES.keys():
        for role_element in RESOURCES.get(name_element):
            role = discord.utils.find(lambda r: r.id == int(role_element), ctx.author.guild.roles)
            if role not in ctx.author.roles:
                available_roles.append(role_element)

    if len(available_roles) == 0:
        await ctx.send(f"You have already verified your purchase(s)!", hidden=True)
        logging.info(f"{ctx.author.name} already had all verified roles.")
        return

    # get current timestamp in UTC
    end_date = datetime.utcnow()

    await ctx.defer(hidden=True)

    roles_given = []
    # loop through purchases until a value is found or count == 36 (36 months is max for how far paypal api can go back)
    count = 0
    success = False
    while len(available_roles) != 0 and count < 36:

        # search through purchases on 30-day intervals (PayPal api has a max of 31 days)
        start_date = end_date - timedelta(days=31)
        transactions = json.loads(await get_transactions(start_date, end_date))

        resource_names = await find_resource_names_from_email(email, transactions)

        # for all found resource names in the PayPal transactions
        for pl_name in resource_names:
            try:
                roles = RESOURCES.get(pl_name)
                roles_to_give = [value for value in roles if value in available_roles]
                for role in roles_to_give:
                    # add the configured discord role to the user who ran the command
                    asyncio.create_task(add_role(ctx, role))
                    # add the email to previously verified emails (with the resource name)
                    await add_previously_verified(email, pl_name)
                    available_roles.remove(role)
                    roles_given.append(role)
                    success = True
                    logging.info(f"{ctx.author.name} given role: " + role)
            except ValueError:
                pass

        # make new end_date the old start_date for next while iteration
        end_date = start_date
        count = count + 1

    if success:
        await ctx.send(f"Successfully verified plugin purchase!", hidden=True)
        await dm_admins(ctx, email, username, roles_given, True)
        await channel_message(ctx.author, email, username, roles_given, True)
        logging.info(f"{ctx.author.name} successfully verified their purchase")
        # write verified emails and resource names out to files
        await write_out_emails()
    else:
        await ctx.send("Failed to verify plugin purchase, open a ticket.", hidden=True)
        await dm_admins(ctx, email, username, roles_given, False)
        await channel_message(ctx.author, email, username, roles_given, False)
        logging.info(f"{ctx.author.name} failed to verify their purchase")


# run the discord client with the discord token
client.run(DISCORD_TOKEN)
