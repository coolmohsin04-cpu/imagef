from keep_alive import keep_awake
import os
from dotenv import load_dotenv

load_dotenv()

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents)

# ====================================================
# SYSTEM 1: $confirm (2-Trader Direct Confirmation)
# ====================================================
class TradeView(discord.ui.View):
    def __init__(self, trader1: discord.User, trader2: discord.User, item_details: str):
        super().__init__(timeout=600)
        self.trader1 = trader1
        self.trader2 = trader2
        self.item_details = item_details
        self.confirmations = set()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.trader1.id, self.trader2.id):
            await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)
            return

        if interaction.user.id in self.confirmations:
            await interaction.response.send_message("⚠️ You have already confirmed!", ephemeral=True)
            return

        self.confirmations.add(interaction.user.id)

        # Posts green mini-embed: "✅ @User has confirmed the trade"
        confirm_embed = discord.Embed(
            description=f"✅ {interaction.user.mention} **has confirmed the trade**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=confirm_embed)

        if len(self.confirmations) >= 2:
            for child in self.children:
                child.disabled = True

            main_embed = interaction.message.embeds[0]
            main_embed.title = "🎉 Trade Fully Confirmed!"
            main_embed.description = f"Both traders agreed to:\n**{self.item_details}**"
            main_embed.color = discord.Color.green()

            await interaction.message.edit(embed=main_embed, view=self)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.trader1.id, self.trader2.id):
            await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        cancel_embed = discord.Embed(
            description=f"❌ {interaction.user.mention} **cancelled the trade**",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=cancel_embed)

        main_embed = interaction.message.embeds[0]
        main_embed.title = "❌ Trade Cancelled"
        main_embed.color = discord.Color.red()

        await interaction.message.edit(embed=main_embed, view=self)
        self.stop()


@bot.command(name="confirm")
async def confirm_trade(ctx, partner: discord.Member, *, deal_details: str = "Unspecified Trade"):
    if partner == ctx.author:
        await ctx.send("You cannot start a trade confirmation with yourself!")
        return

    embed = discord.Embed(
        title="🤝 Trade Confirmation Required",
        description=(
            f"**Deal Details:** {deal_details}\n"
            f"**Traders:** {ctx.author.mention} & {partner.mention}\n\n"
            f"Both traders, please click **Confirm** to proceed or **Cancel** to abort.\n\n"
            f"Two confirmations are required."
        ),
        color=discord.Color.from_rgb(255, 105, 180)  # Pink Border
    )

    view = TradeView(trader1=ctx.author, trader2=partner, item_details=deal_details)
    await ctx.send(embed=embed, view=view)


# ====================================================
# SYSTEM 2: $mm (Middleman Live Waiting Screens)
# ====================================================
class MiddlemanPanel(discord.ui.View):
    def __init__(self, buyer: discord.User, seller: discord.User, details: str):
        super().__init__(timeout=None)
        self.buyer = buyer
        self.seller = seller
        self.details = details
        self.stage = 0

    @discord.ui.button(label="Confirm Deposit Received", style=discord.ButtonStyle.primary, emoji="💳")
    async def confirm_deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only Middlemen/Admins can confirm deposits!", ephemeral=True)
            return

        if self.stage != 0:
            await interaction.response.send_message("⚠️ Deposit already confirmed!", ephemeral=True)
            return

        self.stage = 1
        button.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.blue()
        embed.title = "📥 Payment Secured — Awaiting Item"
        embed.set_field_at(
            2, 
            name="📊 Current Status", 
            value=f"✅ **Payment Verified!**\n⏳ **Waiting for {self.seller.mention} to deliver the item to the buyer...**", 
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"🔔 {self.seller.mention}, payment secured! Deliver the item now.")

    @discord.ui.button(label="Complete & Release", style=discord.ButtonStyle.success, emoji="✅")
    async def complete_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only Middlemen/Admins can release funds!", ephemeral=True)
            return

        if self.stage < 1:
            await interaction.response.send_message("⚠️ Confirm the deposit first before completing!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "🎉 Transaction Completed & Released!"
        embed.set_field_at(
            2, 
            name="📊 Current Status", 
            value="🎉 **Deal Finished!** Both payment and items verified.", 
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("✅ **Trade closed successfully!**")
        self.stop()

    @discord.ui.button(label="Cancel Deal", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only Middlemen/Admins can cancel deals!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Middleman Deal Cancelled"
        embed.set_field_at(
            2, 
            name="📊 Current Status", 
            value=f"⛔ **Cancelled by {interaction.user.mention}.**", 
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


@bot.command(name="mm")
async def start_middleman(ctx, buyer: discord.Member, seller: discord.Member, *, deal_details: str):
    embed = discord.Embed(
        title="⏳ Middleman Deal — Pending Payment",
        description="Please review details below before proceeding.",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="👤 Buyer", value=buyer.mention, inline=True)
    embed.add_field(name="👤 Seller", value=seller.mention, inline=True)
    embed.add_field(
        name="📊 Current Status", 
        value=f"⏳ **WAITING FOR PAYMENT...**\n{buyer.mention}, send payment to the Middleman.", 
        inline=False
    )
    embed.add_field(name="📝 Deal Details", value=f"```\n{deal_details}\n```", inline=False)
    embed.set_footer(text="Middleman System • Staff managed")

    view = MiddlemanPanel(buyer=buyer, seller=seller, details=deal_details)
    await ctx.send(embed=embed, view=view)
# ====================================================
# SYSTEM 3: $mmtrade (Item-for-Item / Acc-for-Acc Swap)
# ====================================================
class TradeMiddlemanPanel(discord.ui.View):
    def __init__(self, t1: discord.User, t2: discord.User, details: str):
        super().__init__(timeout=None)
        self.t1 = t1
        self.t2 = t2
        self.details = details
        self.t1_secured = False
        self.t2_secured = False

    async def update_status(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        
        if self.t1_secured and self.t2_secured:
            status = "✅ **BOTH ASSETS SECURED!**\nMiddleman is now verifying and swapping the accounts/items."
            embed.color = discord.Color.blue()
        elif self.t1_secured:
            status = f"🔄 **PARTIAL HOLD:**\n✅ {self.t1.mention}'s asset is secured!\n⏳ Waiting for {self.t2.mention} to send theirs..."
            embed.color = discord.Color.orange()
        elif self.t2_secured:
            status = f"🔄 **PARTIAL HOLD:**\n✅ {self.t2.mention}'s asset is secured!\n⏳ Waiting for {self.t1.mention} to send theirs..."
            embed.color = discord.Color.orange()
        else:
            status = f"⏳ **WAITING FOR BOTH ASSETS...**\n{self.t1.mention} and {self.t2.mention}, please send your details to the MM."
            embed.color = discord.Color.gold()

        embed.set_field_at(2, name="📊 Current Status", value=status, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Secure Trader 1 Asset", style=discord.ButtonStyle.primary, row=0)
    async def secure_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only Middlemen can secure assets!", ephemeral=True)
        
        self.t1_secured = True
        button.disabled = True
        await self.update_status(interaction)

    @discord.ui.button(label="Secure Trader 2 Asset", style=discord.ButtonStyle.primary, row=0)
    async def secure_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only Middlemen can secure assets!", ephemeral=True)
        
        self.t2_secured = True
        button.disabled = True
        await self.update_status(interaction)

    @discord.ui.button(label="Complete Swap & Release", style=discord.ButtonStyle.success, row=1, emoji="✅")
    async def complete_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only Middlemen can release assets!", ephemeral=True)
        
        if not (self.t1_secured and self.t2_secured):
            return await interaction.response.send_message("⚠️ You must secure BOTH assets before completing the swap!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "🎉 Swap Completed successfully!"
        embed.set_field_at(2, name="📊 Current Status", value="🎉 **SWAP SUCCESSFUL!** Both parties have received their new assets.", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("✅ **Both assets released to the new owners! Trade closed.**")
        self.stop()

    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.danger, row=1, emoji="❌")
    async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only Middlemen can cancel!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Trade Cancelled"
        embed.set_field_at(2, name="📊 Current Status", value=f"⛔ **Cancelled by {interaction.user.mention}.** Middleman will refund any held assets back to their original owners.", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

@bot.command(name="mmtrade")
async def start_mmtrade(ctx, trader1: discord.Member, trader2: discord.Member, *, deal_details: str):
    embed = discord.Embed(
        title="⚖️ Middleman Swap — Pending Assets",
        description="Please review the swap details below before proceeding.",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="🔄 Trader 1", value=trader1.mention, inline=True)
    embed.add_field(name="🔄 Trader 2", value=trader2.mention, inline=True)
    embed.add_field(
        name="📊 Current Status", 
        value=f"⏳ **WAITING FOR BOTH ASSETS...**\n{trader1.mention} and {trader2.mention}, please send your accounts/items to the Middleman.", 
        inline=False
    )
    embed.add_field(name="📝 Swap Details", value=f"```\n{deal_details}\n```", inline=False)

    view = TradeMiddlemanPanel(t1=trader1, t2=trader2, details=deal_details)
    await ctx.send(embed=embed, view=view)

@start_mmtrade.error
async def mmtrade_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ **Oops!** You are missing some details.\n**Correct format:** `$mmtrade @trader1 @trader2 [swap details]`")
# ====================================================
# SYSTEM 4: $mmfee (Fee Split Agreement)
# ====================================================
class MMFeeView(discord.ui.View):
    def __init__(self, trader1: discord.User, trader2: discord.User):
        super().__init__(timeout=180) # 3 minutes timeout
        self.trader1 = trader1
        self.trader2 = trader2
        self.votes = {}

    async def check_match(self, interaction: discord.Interaction):
        # Check if both traders have voted
        if len(self.votes) == 2:
            t1_vote = self.votes[self.trader1.id]
            t2_vote = self.votes[self.trader2.id]

            if t1_vote == t2_vote:
                # Votes match - Success!
                for child in self.children:
                    child.disabled = True
                
                choice_str = "Split 50 / 50" if t1_vote == "split" else "Pay 100%"
                
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.green()
                embed.title = "✅ Fee Agreement Reached!"
                embed.description = f"Both traders have officially agreed to:\n**{choice_str}**"
                
                await interaction.message.edit(embed=embed, view=self)
                await interaction.followup.send(f"✅ {self.trader1.mention} and {self.trader2.mention} agreed on the fee structure. You may now proceed!")
                self.stop()
            else:
                # Votes do not match - Reset
                self.votes.clear()
                await interaction.followup.send(f"⚠️ {self.trader1.mention} and {self.trader2.mention} selected different options! Votes have been reset. Please discuss and pick the **same** option.")

    @discord.ui.button(label="Split 50 / 50", style=discord.ButtonStyle.primary, emoji="⚖️")
    async def split_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.trader1.id, self.trader2.id):
            return await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)
        
        self.votes[interaction.user.id] = "split"
        await interaction.response.send_message("✅ You voted to **Split 50 / 50**.", ephemeral=True)
        await self.check_match(interaction)

    @discord.ui.button(label="Pay 100%", style=discord.ButtonStyle.secondary, emoji="1️⃣")
    async def full_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.trader1.id, self.trader2.id):
            return await interaction.response.send_message("❌ You are not part of this trade!", ephemeral=True)
        
        self.votes[interaction.user.id] = "full"
        await interaction.response.send_message("✅ You voted for **Pay 100%**.", ephemeral=True)
        await self.check_match(interaction)


@bot.command(name="mmfee")
async def start_mmfee(ctx, partner: discord.Member):
    if partner == ctx.author:
        return await ctx.send("You cannot start a fee agreement with yourself!")

    embed = discord.Embed(
        title="💰 Middleman Fee — Who Pays?",
        description=(
            "Both traders, choose how the middleman fee will be split.\n\n"
            "Both traders must pick the same optivc  vc on for it to be accepted.\n\n"
            "⚖️ Split 50 / 50 — each trader pays half\n"
            "1️⃣ Pay 100% — one trader pays the full fee\n\n"
            "You have 3 minutes to agree."
        ),
        color=discord.Color.from_rgb(255, 105, 180) # Pink color from screenshot
    )
    
    view = MMFeeView(trader1=ctx.author, trader2=partner)
    await ctx.send(content=f"{ctx.author.mention} {partner.mention}", embed=embed, view=view)

@start_mmfee.error
async def mmfee_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ **Oops!** You forgot to mention your trading partner.\n**Correct format:** `$mmfee @partner`")        
import discord
from discord.ext import commands

# ====================================================
# Custom Notice / Application Panel View
# ====================================================
class NoticeView(discord.ui.View):
    def __init__(self, target_user: discord.User):
        super().__init__(timeout=300)  # 5-minute timeout
        self.target_user = target_user

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user.id:
            return await interaction.response.send_message("❌ This notification was not sent to you.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ Offer Accepted"
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.mention} accepted the offer.")
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user.id:
            return await interaction.response.send_message("❌ This notification was not sent to you.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Offer Declined"

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"❌ {interaction.user.mention} declined the offer.")
        self.stop()

# ====================================================
# Command: $notice @user
# ====================================================
@bot.command(name="notice")
async def send_notice(ctx, target: discord.Member):
    # Use the exact pink hex color from the screenshot
    embed = discord.Embed(
        color=discord.Color.from_rgb(255, 105, 180) 
    )

    # Replicate the double warning header
    embed.add_field(
        name="⚠️ Scam Notification\n⚠️ Scam Notification",
        value="We regret to inform you that you have been scammed, and we sincerely apologize for this unfortunate situation. However, there is a way for you to recover your losses and potentially earn even more. Detailed information will be provided below..",
        inline=False
    )
    
    # Replicate the target emoji header
    embed.add_field(
        name="Hitting Application",
        value="We are very sorry that you have been scammed but there is a way to get it back 2x or even 10x if you're active.",
        inline=False
    )
    
    # Replicate the bold question format
    embed.add_field(
        name="\u200b", # Leave blank to act as a continuation
        value="**What is Hitting?**\nHitting is where you scam other people, often using fake middlemans. You can use our fake services that we provide to scam others and get tons of items. Detailed information will be provided below.",
        inline=False
    )
    
# Replicate the clipboard emoji and footer format
    embed.add_field(
        name="Offer Action",
        value="Choose whether you want to accept or decline the offer below:\n\n*Your Custom Service Name*",
        inline=False
    )

    view = NoticeView(target_user=target)
    await ctx.send(content=target.mention, embed=embed, view=view)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - Both $confirm and $mm are ready!")
    
@bot.command(name="confirm")
async def confirm(ctx, partner: discord.Member = None, *, deal_details: str = "Unspecified Trade"):
    # Multi-server check
    GUILD_IDS = [951894453457662062, 553406757112774658, 1438292831100735651]

    guild = None
    author_member = None

    for guild_id in GUILD_IDS:
        g = bot.get_guild(guild_id)
        if g:
            m = g.get_member(ctx.author.id)
            if m:
                guild = g
                author_member = m
                break 
                
    if not guild or not author_member:
        await ctx.send("You must be in one of the authorized servers to use this command!")
        return

    # Check roles using that server's member object
    vouch_role = discord.utils.get(guild.roles, name="vouch")
    if vouch_role not in author_member.roles:
        await ctx.send("You don't have permission to use this command.")
        return

    if not partner:
        await ctx.send("❌ Please mention your trading partner! Correct format: `$confirm @partner [details]`")
        return

    if partner == ctx.author:
        await ctx.send("You cannot start a trade confirmation with yourself!")
        return

    embed = discord.Embed(
        title="🤝 Trade Confirmation Required",
        description=(
            f"**Deal Details:** {deal_details}\n"
            f"**Traders:** {ctx.author.mention} & {partner.mention}\n\n"
            f"Both traders, please click **Confirm** to proceed or **Cancel** to abort.\n\n"
            f"Two confirmations are required."
        ),
        color=discord.Color.from_rgb(255, 105, 180)  # Pink Border
    )

    view = TradeView(trader1=ctx.author, trader2=partner, item_details=deal_details)
    await ctx.send(embed=embed, view=view)
    
keep_awake()
bot.run(os.getenv('DISCORD_TOKEN'))
