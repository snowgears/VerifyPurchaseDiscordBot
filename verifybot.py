import requests
import json
import pickle
import logging
from threading import Timer
import re

import discord
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option
from discord.utils import get
from discord.ext import commands
from discord.ext.commands import Bot

import os
from dotenv import load_dotenv

from datetime import datetime, timedelta

# first load the environment variables
load_dotenv()

# regular expression for validating an Email
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(i) for i in os.environ.get("GUILD_LIST").split(" ")]

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENDPOINT = "https://api-m.paypal.com"
PAYPAL_TOKEN = 0

RESOURCES = {}

for resource in os.environ.get("RESOURCE_LIST").split(" "):
    resource_name = resource.split(":")[0]
    resource_roles = (resource.split(":")[1]).split(",")
    RESOURCES[resource_name] = resource_roles

ADMIN_ID_LIST=[int(i) for i in os.environ.get("ADMIN_ID_LIST").split(" ")]

DEBUG = False
APPEAR_OFFLINE = True

CHECK_PREVIOUSLY_VERIFIED = False
emails_verified = []
resource_names_verified = []

# init discord client
client = discord.Client(intents=discord.Intents.all())
bot = Bot("!")

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
            with open ('verified_emails', 'rb') as fp:
                emails_verified = pickle.load(fp)
        except FileNotFoundError:
            pass
        global resource_names_verified
        try:
            with open ('verified_resource_names', 'rb') as fp:
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
async def get_token():
    url = PAYPAL_ENDPOINT + '/v1/oauth2/token'
    
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
        
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
    return data['access_token']

# this gets a list of transactions from the paypal api ranging from start_date to end_date
async def get_transactions(start_date, end_date):
    url = PAYPAL_ENDPOINT + "/v1/reporting/transactions"

    payload={}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PAYPAL_TOKEN}"
    }
    
    payload = {
        'start_date': f'{await format_date(start_date)}',
        'end_date':   f'{await format_date(end_date)}',
        'transaction_status': 'S',
        'fields':   'cart_info, payer_info'
    }    
    
    response = requests.get(url, headers=headers, params=payload)

    data = response.text
    return data

# this is a discord bot command to add a role to a user
@bot.command(pass_context=True)
async def addrole(ctx, role):
    member = ctx.author
    role = get(member.guild.roles, name=role)
    await member.add_roles(role)

# send a direct message to a list of admions
@bot.command(pass_context=True)
async def dm_admins(ctx, message):
    #user: discord.User
    for user_id in ADMIN_ID_LIST:
        user = ctx.author.guild.get_member(user_id)
        await user.send(message)

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
                        matching_names.append(pl_name) # add the matching spigot resource name)
            except KeyError:
                pass
    except KeyError:
            pass
    return matching_names

# discord event that fires when the bot is ready and listening
@client.event
async def on_ready():
    #set the logging config
    logging.basicConfig(handlers=[logging.FileHandler('verifybot.log', 'a+', 'utf-8')], level=logging.INFO, format='%(asctime)s: %(message)s')

    if APPEAR_OFFLINE:
        await client.change_presence(status=discord.Status.offline)

    # get the oauth token needed for paypal requests
    global PAYPAL_TOKEN
    PAYPAL_TOKEN = await get_token()

    # read in any previously verified emails
    await read_in_emails()

    print("Ready!")


# defines a new 'slash command' in discord and what options to show to user for params
@slash.slash(name="verify",
             description="Verify your plugin purchase.",
             options=[
               create_option(
                 name="email",
                 description="Verify your purchase via your paypal email.",
                 option_type=3,
                 required=True
               )],
             guild_ids=GUILD_IDS)
async def _verifypurchase(ctx, email: str): # Defines a new "context" (ctx) command called "paypal."
    
    logging.info(f"{ctx.author.name} ran command '/paypal {email}'")

    if not check_email(email):
        await ctx.send(f"You must provide a valid email!", hidden=True)
        return

    available_roles = []

    for name_element in RESOURCES.keys():
        for role_element in RESOURCES.get(name_element):
            role = discord.utils.find(lambda r: r.name == role_element, ctx.author.guild.roles)
            if role not in ctx.author.roles:
                available_roles.append(role_element)

    if len(available_roles) == 0:
        await ctx.send(f"You have already verified your purchase(s)!", hidden=True)
        logging.info(f"{ctx.author.name} already had all verified roles.")
        return

    # get current timestamp in UTC
    end_date = datetime.today()

    await ctx.defer(hidden=True)
    
    roles_given = []
    # loop through purchases until a value is found or count == 36 (36 months is max for how far paypal api can go back)
    count = 0
    success = False
    while(len(available_roles) !=0 and count < 36):
    
        #search through purchases on 30 day intervals (paypal api has a max of 31 days)
        start_date = end_date - timedelta(days=30)
        transactions = json.loads(await get_transactions(start_date, end_date))

        resource_names = await find_resource_names_from_email(email, transactions)

        # for all found resourcenames in the paypal transactions
        for pl_name in resource_names:
            try:
                roles = RESOURCES.get(pl_name)
                for role in roles:
                    available_roles.remove(role)
                    roles_given.append(role)
                    success = True;
                    # add the email to previously verified emails (with the resource name)
                    await add_previously_verified(email, pl_name)
                    # add the configured discord role to the user who ran the command
                    await addrole(ctx, role)
                    logging.info(f"{ctx.author.name} given role: "+role)
            except ValueError:
                pass

        # make new end_date the old start_date for next while iteration
        end_date = start_date
        count = count + 1
    
    if success:
        await ctx.send(f"Successfully verified PayPal purchase!", hidden=True)
        await dm_admins(ctx, "{} successfully verified a purchase with email: ".format(ctx.author.mention)+f"{email}. Given roles: {roles_given}")
        logging.info(f"{ctx.author.name} successfully verified their purchase")
        # write verified emails and resource names out to files
        await write_out_emails()
    else:
        await ctx.send("Failed to verify PayPal purchase.", hidden=True)
        await dm_admins(ctx, "{} failed to verify a purchase with email: ".format(ctx.author.mention)+f"{email}")
        logging.info(f"{ctx.author.name} failed to verify their purchase")

# run the discord client with the discord token
client.run(DISCORD_TOKEN)