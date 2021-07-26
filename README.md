# VerifyPurchaseDiscordBot
Discord bot that searches your PayPal transactions (by user entered email) and assigns a role if the purchase was verified.

![](https://i.imgur.com/qE83p4R.png)

![](https://i.imgur.com/BCNGeJW.png)

![](https://i.imgur.com/IC70YYD.png)

There is also an option to check for previously verified emails!

![](https://i.imgur.com/6Y6iGJO.png)

**Steps for getting started:**
- install the libraries in requirements.txt
   - ```python -m pip install -r requirements.txt```
- rename ".env example" to ".env"


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
ADMIN_ID_LIST="xxxxxxxxxxxxxxxxxx"
```
- Put any admin ids (discord user ids) in here you that you want the bot to private message (seperated by spaces within the string)
- ![](https://i.imgur.com/X61GB6a.png)
- If you don't know a discord user id, find it like this: https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-
```
PAYPAL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAYPAL_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
- Create a PayPal API application in a 'Live' environment (https://developer.paypal.com/docs/api-basics/manage-apps/)
- Make sure to grant the application access to 'Transaction Search'

```
RESOURCE_LIST="0000:verified-plugin0 1111:verified-plugin1"
```
- Put your Spigot resource id here (found in your Spigot resource URL) followed by the Discord role you want to assign to a user once they have verified a purchase for that id. (This role must already exist on your server)
- Put as many of these as you have separated by spaces within the string like in the example above
---
\
Now just run the bot wherever you are going to host it (and make sure it has a sufficient role to assign roles to users):
``` 
py -3 verifybot.py
```

Enjoy!

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=WYC2DQJMWUX6J) \
**If this bot is helpful to you, please consider donating.**
