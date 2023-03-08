import json
import logging
import os
import re
from datetime import datetime, timedelta
from threading import Timer

import discord
from dotenv import load_dotenv
from dateutil import parser
import paypal_api
from pathlib import Path

regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'


def isValid(email):
    return re.fullmatch(regex, email)


class AlreadyVerifiedPurchases(Exception):
    pass


class AlreadyVerifiedEmail(Exception):
    pass


class VerificationFailed(Exception):
    pass


class VerifyBot:
    def __init__(self, paypal_api: paypal_api.PayPalApi):
        self.database = {}
        self.RESOURCES = {}
        self.verified_emails = {}
        load_dotenv()
        for resource in os.environ.get("RESOURCE_LIST").split(";"):
            resource_name = resource.split(":")[0].lower()
            resource_roles = (resource.split(":")[1]).split(",")
            self.RESOURCES[resource_name] = resource_roles
        self.CHECK_PREVIOUSLY_VERIFIED = os.getenv("CHECK_PREVIOUSLY_VERIFIED").lower() == "true"
        self.paypal_api = paypal_api
        self.read_in_emails()
        print("Loading purchases...")
        self.update_purchases_task()

    def update_purchases_task(self):
        self.update_purchases()
        t = Timer(3600, self.update_purchases_task)
        t.daemon = True
        t.start()

    def read_in_emails(self):
        if self.CHECK_PREVIOUSLY_VERIFIED:
            try:
                with open('data/verified_emails.json') as file:
                    self.verified_emails = json.load(file)
            except FileNotFoundError:
                pass

    async def write_out_emails(self):
        if self.CHECK_PREVIOUSLY_VERIFIED:
            with open('data/verified_emails.json', 'w') as outfile:
                json.dump(self.verified_emails, outfile, indent=2)

    def has_previously_verified(self, email: str, resource_name: str):
        return self.CHECK_PREVIOUSLY_VERIFIED and email in self.verified_emails and resource_name.lower() in \
               self.verified_emails[email]["purchases"]

    def get_previously_verified_purchases(self, email: str):
        resources = []
        if self.CHECK_PREVIOUSLY_VERIFIED:
            if email in self.verified_emails:
                for name in self.verified_emails[email]["purchases"]:
                    if self.has_previously_verified(email, name):
                        resources.append(name)

        if resources:
            resources.sort()
            return self.verified_emails[email]["discord_id"], resources

        return None, resources

    def add_previously_verified(self, email: str, discord_id: int, resource_name: str):
        if self.CHECK_PREVIOUSLY_VERIFIED:
            if email in self.verified_emails and resource_name not in self.verified_emails[email]["purchases"]:
                self.verified_emails[email]["purchases"].append(resource_name.lower())
            else:
                self.verified_emails[email] = {
                    'discord_id': discord_id,
                    'purchases': [resource_name.lower()]
                }

    def find_plugin_name(self, text: str):
        for resource_name in self.RESOURCES.keys():
            if resource_name.lower() in text.lower():
                return resource_name.lower()
        return

    def find_purchases_by_email(self, email: str):
        purchases = self.database.get("customers").get(email)
        if purchases:
            purchases.sort()
            return purchases

    def find_purchases(self, transactions):
        try:
            for transaction in transactions["transaction_details"]:
                try:
                    purchase_item_name = transaction['cart_info']['item_details'][0]['item_name']
                    purchase_email = transaction['payer_info']['email_address'].lower()
                    plugin_name = self.find_plugin_name(purchase_item_name)
                    if plugin_name:
                        user_purchases = []
                        if self.database.get("customers").get(purchase_email):
                            user_purchases = self.database["customers"].get(purchase_email)
                        if plugin_name not in user_purchases:
                            user_purchases.append(plugin_name)
                            self.database["customers"][purchase_email] = user_purchases
                        else:
                            self.database["customers"][purchase_email] = [plugin_name]
                except KeyError:
                    pass
                except IndexError:
                    pass
        except KeyError:
            pass

    def update_purchases(self):
        if not self.database:
            try:
                with open('data/database.json') as file:
                    self.database = json.load(file)
            except FileNotFoundError:
                pass
        
        if not self.database.get("last_update") or not all(
                x == y for x, y in zip(self.database["saved_plugins"], self.RESOURCES.keys())):

            end_date = datetime.utcnow()
            self.database["last_update"] = end_date
            self.database["customers"] = {}
            count = 0
            while count < 36:
                start_date = end_date - timedelta(days=31)
                transactions = self.paypal_api.get_transactions(start_date, end_date)
                self.find_purchases(transactions)
                end_date = start_date
                count = count + 1
        else:
            end_date = datetime.utcnow()
            last_update = parser.parse(self.database["last_update"])
            self.database["last_update"] = end_date
            count = 0
            while count < 36 and end_date >= last_update:
                start_date = end_date - timedelta(days=31)
                transactions = self.paypal_api.get_transactions(start_date, end_date)
                self.find_purchases(transactions)
                end_date = start_date
                count = count + 1

        Path("data").mkdir(parents=True, exist_ok=True)
        with open('data/database.json', 'w') as outfile:
            self.database["last_update"] = self.database["last_update"].isoformat()
            self.database["saved_plugins"] = list(self.RESOURCES.keys())
            json.dump(self.database, outfile, indent=2)

    async def verify(self, ctx, email: str, username: str):

        if not isValid(email):
            await ctx.send(f"You must provide a valid email!", hidden=True)
            return

        email = email.lower()

        logging.info(f"{ctx.author.name} ran command '/verify {email} {username}'")
        available_roles = []

        for roles in self.RESOURCES.values():
            for role_id in roles:
                role = discord.utils.find(lambda r: r.id == int(role_id), ctx.author.guild.roles)
                if role not in ctx.author.roles:
                    available_roles.append(role_id)

        if len(available_roles) == 0:
            raise AlreadyVerifiedPurchases()

        await ctx.defer(hidden=True)
        self.update_purchases()
        user_id, verified_purchases = self.get_previously_verified_purchases(email)
        purchases = self.find_purchases_by_email(email)

        if not purchases:
            raise VerificationFailed()

        if user_id and user_id != ctx.author.id:
            purchases = [item for item in purchases if item not in verified_purchases]

        if not purchases:
            raise AlreadyVerifiedEmail()

        roles_to_give = []
        for purchase in purchases:
            roles = self.RESOURCES.get(purchase)
            if roles:
                roles_to_give = roles_to_give + [value for value in roles if value in available_roles]
                if roles_to_give:
                    self.add_previously_verified(email, ctx.author.id, purchase)

        if (self.CHECK_PREVIOUSLY_VERIFIED and verified_purchases == purchases and len(roles_to_give) == 0) or (
                not self.CHECK_PREVIOUSLY_VERIFIED and len(roles_to_give) == 0):
            raise AlreadyVerifiedPurchases()

        return roles_to_give
