import asyncio
import logging
import discord
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option
import os
from dotenv import load_dotenv
from paypal_api import PayPalApi
from verify_bot import VerifyBot, AlreadyVerifiedPurchases, AlreadyVerifiedEmail, VerificationFailed

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = [int(os.environ.get("GUILD_ID"))]
REPORT_CHANNEL_ID = int(os.environ.get("REPORT_CHANNEL_ID"))
VERIFY_CHANNEL_ID = int(os.environ.get("VERIFY_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.environ.get("ADMIN_ROLE_ID"))
ADMIN_ID_LIST = []
if bool(os.environ.get("ADMIN_ID_LIST") and os.environ.get("ADMIN_ID_LIST").strip()):
    ADMIN_ID_LIST = [int(i) for i in os.environ.get("ADMIN_ID_LIST").split(" ")]
APPEAR_OFFLINE = os.getenv("APPEAR_OFFLINE").lower() == "true"
client = discord.Client(intents=discord.Intents.all())
bot = commands.Bot(command_prefix='!')
slash = SlashCommand(client, sync_commands=True)
paypal_api = PayPalApi()
verify_bot = VerifyBot(paypal_api)


@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return
    role = discord.utils.get(message.guild.roles, id=ADMIN_ROLE_ID)
    if role not in message.author.roles and message.channel.id == VERIFY_CHANNEL_ID:
        await message.delete()


# discord bot command to add a role to a user
@bot.command(pass_context=True)
async def add_role(ctx, role_id):
    member = ctx.author
    role = get(member.guild.roles, id=int(role_id))
    await member.add_roles(role)


# send a direct message to a list of admins
@bot.command(pass_context=True)
async def dm_admins(ctx, email, username, roles_given, verified):
    if verified:
        message = "{} successfully verified a purchase with email: ".format(
            ctx.author.mention) + f"{email} and username: {username}. Given roles: "
        roles = [(get(ctx.guild.roles, id=int(role_id))).name for role_id in roles_given]
        message = message + str(roles)
    else:
        message = "{} failed to verify a purchase with email: ".format(
            ctx.author.mention) + f"{email} and username: {username}"
    for user_id in ADMIN_ID_LIST:
        user = ctx.author.guild.get_member(user_id)
        await user.send(message)


# send a report message into a channel
@bot.command(pass_context=True)
async def channel_message(author, email, username, roles, verified):
    channel = client.get_channel(REPORT_CHANNEL_ID)
    roles_message = ""
    if verified:
        embed = discord.Embed(title="Purchase verify of premium plugins",
                              description="Purchase verification completed for {}!".format(author.name),
                              color=0x2ecc71)
        for role_id in roles:
            roles_message = roles_message + f"<@&{role_id}> "
    else:
        embed = discord.Embed(title="Purchase verify of premium plugins",
                              description="Purchase verification failed for {}!".format(author.name),
                              color=0xe74c3c)
    embed.add_field(name="Email", value=email, inline=True)
    embed.add_field(name="Username", value=username, inline=True)
    if verified:
        embed.add_field(name="Roles", value=roles_message, inline=False)
    await channel.send(embed=embed)


# discord event that fires when the bot is ready and listening
@client.event
async def on_ready():
    logging.basicConfig(handlers=[logging.FileHandler('data/verifybot.log', 'a+', 'utf-8')], level=logging.INFO,
                        format='%(asctime)s: %(message)s')

    if APPEAR_OFFLINE:
        await client.change_presence(status=discord.Status.offline)

    print("The bot is ready!")


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
async def _verifypurchase(ctx, email: str, username: str):
    if not (ctx.channel.id == VERIFY_CHANNEL_ID):
        return

    try:
        roles_to_give = await verify_bot.verify(ctx, email, username)
        if roles_to_give:
            for role in roles_to_give:
                await add_role(ctx, role)
                logging.info(f"{ctx.author.name} given role: " + role)

            await ctx.send(f"Successfully verified plugin purchase!", hidden=True)
            await channel_message(ctx.author, email, username, roles_to_give, True)
            await dm_admins(ctx, email, username, roles_to_give, True)
            logging.info(f"{ctx.author.name} successfully verified their purchase")
            asyncio.create_task(verify_bot.write_out_emails())
    except AlreadyVerifiedPurchases:
        await ctx.send(f"You have already verified your purchase(s)!", hidden=True)
        logging.info(f"{ctx.author.name} already had all verified roles.")
        return
    except AlreadyVerifiedEmail:
        await ctx.send(f"Purchase already verified with this email!", hidden=True)
        logging.info(f"{ctx.author.name} already verified email.")
    except VerificationFailed:
        await ctx.send("Failed to verify plugin purchase, open a ticket.", hidden=True)
        await channel_message(ctx.author, email, username, [], False)
        await dm_admins(ctx, email, username, [], False)
        logging.info(f"{ctx.author.name} failed to verify their purchase")


# run the discord client with the discord token
client.run(DISCORD_TOKEN)
