import requests
import json
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

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(i) for i in os.environ.get("GUILD_LIST").split(" ")]

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENDPOINT = "https://api-m.paypal.com"
PAYPAL_TOKEN = 0

RESOURCE_ID = os.getenv("RESOURCE_ID")
RESOURCE_ROLE = os.getenv("RESOURCE_ROLE")

DEBUG = True

# init discord client
client = discord.Client(intents=discord.Intents.all())
bot = Bot("!")

# declare the discord slash commands through the client.
slash = SlashCommand(client, sync_commands=True)

# --- functions ---

# this formats a date for submitting to the PayPal API endpoint
def format_date(date):
    d = date.strftime('%Y-%m-%dT%H:%M:%SZ')
    return d

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

# this gets an oauth token from the paypal api
def get_token():
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

    return data['access_token']

# this gets a list of transactions from the paypal api ranging from start_date to end_date
def get_transactions(start_date, end_date):
    url = PAYPAL_ENDPOINT + "/v1/reporting/transactions"

    payload={}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PAYPAL_TOKEN}"
    }
    
    payload = {
        'start_date': f'{format_date(start_date)}',
        'end_date':   f'{format_date(end_date)}',
        'fields':   'all'
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

# this searches through all transactions to find a matching email
# if an email is found, it assigns a role and returns true
# if an email is not found, it returns false
async def find_resource_from_email(email, transactions):
    for transaction in transactions["transaction_details"]:
        try:
            purchase_custom_field = transaction['transaction_info']['custom_field']
            purchase_email = transaction['payer_info']['email_address']
            #print(purchase_custom_field)
            #print(purchase_email)
            if purchase_email.lower() == email.lower():
                s = purchase_custom_field.split('|')
                return s[len(s)-1] # return last index of list (the spigot resource id)
        except KeyError:
            pass
    return ''

# discord event that fires when the bot is ready and listening
@client.event
async def on_ready():
    print("Ready!")
    # get the oauth token needed for paypal requests
    global PAYPAL_TOKEN
    PAYPAL_TOKEN = get_token()

# defines a new 'slash command' in discord and what options to show to user for params
@slash.slash(name="paypal",
             description="Verify your paypal purchase.",
             options=[
               create_option(
                 name="email",
                 description="Verify your purchase via your paypal email.",
                 option_type=3,
                 required=True
               )],
             guild_ids=GUILD_IDS)
async def _verifypurchase(ctx, email: str): # Defines a new "context" (ctx) command called "paypal."
    
    # first check that the user doesn't already have the role
    role = discord.utils.find(lambda r: r.name == RESOURCE_ROLE, ctx.author.guild.roles)
    if role in ctx.author.roles:
        await ctx.send(f"You have already verified your purchase!")
        return
    
    # get current timestamp in UTC
    end_date = datetime.today()
    

    # loop through (current - 30) until a value is found or count == 36 (36 months/3 years is max for paypal api)
    count = 0
    success = False

    await ctx.defer()
    #search through purchases on 30 day intervals (paypal api has a max of 31 days)
    while(success == False or count < 36): #make this 36 in future
    
        start_date = end_date - timedelta(days=30)
        transactions = json.loads(get_transactions(start_date, end_date))
        
        resource_id = await find_resource_from_email(email, transactions)

        if resource_id:
            if RESOURCE_ID == resource_id:
                success = True;
                await addrole(ctx, RESOURCE_ROLE)

        end_date = start_date #make new end_date the old start_date
        count = count + 1
    
    if success:
        await ctx.send(f"Successfully verified PayPal purchase!")
    else:
        await ctx.send(f"Failed to verify PayPal purchase.")

# run the discord client with the discord token
client.run(DISCORD_TOKEN)