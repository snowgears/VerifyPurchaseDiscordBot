# VerifyPurchaseDiscordBot
Discord bot that searches your PayPal transactions (via user email) and assigns a role if the purchase has been verified.

This bot supports [SpigotMC](https://www.spigotmc.org/) and [MCMarket](https://www.mc-market.org/)

**ScreenShot**

Some pics of the Discord bot

![](https://i.imgur.com/yoDuzS7.png)

![](https://imgur.com/J0wHgl1.png)

![](https://imgur.com/fj58XJO.png)
![](https://imgur.com/Uv0UhVm.png)
![](https://imgur.com/DFJPUfC.png)
![](https://imgur.com/ihRk6tE.png)


**Steps for getting started:**
- install the libraries in requirements.txt
   - ```python -m pip install -r requirements.txt```


**Guide to filling out the .env file:**
---

```
DISCORD_TOKEN=Ojzk1MTM2Mc0NjYTATQy2Mkz.gfqYfq99A.JScoVbGD1Lo0HDbonDuvYjJPtPy
```
 - Create a new discord application and put the token value here, [click here](https://discord.com/developers/applications)
- Make sure to set the Oauth2 scope to: [bot, applications.commands]

```
GUILD_ID="897460772427382670"
```
- Put here the guild id (discord server id) you want to use the bot on
- If you don't know your discord server id, [click here](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-) 

```
ADMIN_ID_LIST="143651103467110401 290472907317051392"
```
- Put here any admin role ids (discord role ids) that you want the bot to private message (seperated by spaces within the string)
- If you don't know a discord user id, [click here](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-) 
```
ADMIN_ROLE_ID="945380919903150090"
```
- Put here the admin role id (discord role id) that you want to allow to write in the verification channel, otherwise the bot will delete the messages
- If you don't know the discord role id [click here](https://ozonprice.com/blog/discord-get-role-id/) 
```
REPORT_CHANNEL_ID="945380919903150090"
```
- Put here the channel id (discord channel id) where the bot will send a message with the success of the verification every time someone will use the verification command
- If you don't know the discord channel id [click here](https://turbofuture.com/internet/Discord-Channel-ID) 
```
VERIFY_CHANNEL_ID="945380919903150090"
```
- Put here the channel id (discord channel id) where users can only use the verification command
- Make sure that users can write within that channel
- If you don't know the discord channel id [click here](https://turbofuture.com/internet/Discord-Channel-ID) 
```
PAYPAL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAYPAL_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
- Create a PayPal API application in a 'Live' environment [click here](https://developer.paypal.com/docs/api-basics/manage-apps/)
- Make sure to grant the application access to 'Transaction Search'

```
RESOURCE_LIST="PluginName1:846789230670774275,846789230670774276;PluginName2:RoleId1,RoleId2"
```
- Put your Spigot or McMarket resource name here followed by the Discord roles (comma-separated) you want to assign to a user once they have verified a purchase for that plugin name. (These roles must already exist on your server)
- Put as many of these as you have separated by semicolon within the string like in the example above

---
Now just run the bot wherever you are going to host it (and make sure it has a sufficient role to assign roles to users):
``` 
py -3 verifybot.py
```
