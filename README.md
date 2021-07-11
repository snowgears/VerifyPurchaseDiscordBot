# VerifyPurchaseDiscordBot
Discord bot that searches your PayPal transactions (by user entered email) and assigns a role if the purchase was verified.

install the libraries in library.sh
rename ".env example" to ".env"


**Guide to filling out the .env file:**
---

```
DISCORD_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
 - Create a new discord application and put the token value here. (https://discord.com/developers/applications)
- Make sure to set the Oauth2 scope to: [bot, applications.commands]

```
GUILD_LIST="xxxxxxxxxxxxxxxxxx"
```
- Put any guild ids (discord server ids) in here you want to use the bot on (seperated by spaces within the string)
- If you don't know your discord server id, find it like this: https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-

```
PAYPAL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAYPAL_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
- Create a PayPal API application in a 'Live' environment (https://developer.paypal.com/docs/api-basics/manage-apps/)
- Make sure to grant the application access to 'Transaction Search'

```
RESOURCE_ID=0000
RESOURCE_ROLE=verified-purchase
```
- Put your Spigot resource id here (found in your Spigot resource URL)
- Put the name of the Discord role you want to assign to a user once they have verified a purchase. (This role must already exist)
---
\
Now just run the bot wherever you are going to host it (and make sure it has a sufficient role to assign roles to users):
``` 
py -3 verifybot.py
```

Enjoy!

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=WYC2DQJMWUX6J) \
**If this bot is helpful to you, please consider donating.**
