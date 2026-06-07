import discord
from discord import app_commands
import json
import os
import hashlib
import asyncio

# ==================== LOAD CONFIG ====================
CONFIG_FILE = 'config.json'

if not os.path.exists(CONFIG_FILE):
    print("❌ config.json not found! Creating default one...")
    default_config = {
        "token": "YOUR_BOT_TOKEN_HERE",
        "owner_id": 0,
        "guild_settings": {}
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(default_config, f, indent=4)
    print("✅ Default config.json created!")

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_guild_settings(guild_id):
    gid = str(guild_id)
    if gid not in config["guild_settings"]:
        config["guild_settings"][gid] = {
            "afk_vc_id": 0,
            "warning_channel_id": 0,
            "whitelisted_channels": []
        }
    return config["guild_settings"][gid]

# ==================== BOT SETUP ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

muted_users = set()  # Still global for simplicity

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    print(f'✅ Bot is online as {bot.user} | Ready in {len(bot.guilds)} servers')
    await tree.sync()
    print("🔍 Slash commands synced")

# AFK Voice Channel - Per Server
@bot.event
async def on_voice_state_update(member, before, after):
    if not member.guild:
        return
    settings = get_guild_settings(member.guild.id)
    afk_id = settings.get("afk_vc_id")
    if not afk_id:
        return

    afk_vc = bot.get_channel(afk_id)
    if not afk_vc or not isinstance(afk_vc, discord.VoiceChannel):
        return

    # Bot stays in AFK VC
    if not afk_vc.guild.me.voice or afk_vc.guild.me.voice.channel != afk_vc:
        try:
            await afk_vc.connect()
        except:
            pass

    # Joined → Mute
    if after.channel and after.channel.id == afk_id:
        if member.id not in muted_users:
            try:
                await member.edit(mute=True, reason="AFK VC - Server Muted")
                muted_users.add(member.id)
            except:
                pass

    # Left → Unmute
    elif before.channel and before.channel.id == afk_id and (not after.channel or after.channel.id != afk_id):
        if member.id in muted_users:
            try:
                await member.edit(mute=False, reason="Left AFK VC")
                muted_users.discard(member.id)
            except:
                pass

# Message Moderation - Per Server
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    settings = get_guild_settings(message.guild.id)
    if message.channel.id in settings.get("whitelisted_channels", []):
        return

    content = message.content.lower()
    deleted = False

    if any(word in content for word in ["bonus", "withdraw", "$2700", "nustwin", "rackswin", "mrbeast", "ip", ".play", ".net", "mera smp", "nitro", "baap", "maa", "hosting", "my server"]) or \
       any(link in content for link in ["nustwin.com", "rackswin.com", "discord.gift", "nitro", "http", ".net", ".play", ".me", "invite", "youtube.com", "youtu.be", "instagram.com"]):
        deleted = True

    if message.attachments:
        for att in message.attachments:
            filename = att.filename.lower()
            if any(bad in filename for bad in ["IMG_7192.jpg", "1f5f3f0b.jpg", "7c0f7032.jpg", "202384c9-1.jpg", "rackswin", "nustwin", "withdrawal"]):
                deleted = True
                break

    if deleted:
        try:
            await message.delete()
        except:
            pass

        warning = f"{message.author.mention} I am moderator bot. I saw your account is hacked. We are receiving phishing image from your account and I am deleting it continuously. Please change your Discord password. Thank you."

        try:
            await message.channel.send(warning, delete_after=30)
        except:
            pass

# ==================== COMMANDS ====================
@tree.command(name="setafkvc", description="Set AFK Voice Channel for this server")
@app_commands.describe(channel="Voice Channel")
async def setafkvc(interaction: discord.Interaction, channel: discord.VoiceChannel):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    settings = get_guild_settings(interaction.guild.id)
    settings["afk_vc_id"] = channel.id
    save_config()

    await interaction.response.send_message(f"✅ AFK VC set to **{channel.name}** for this server.", ephemeral=True)

@tree.command(name="whitelist", description="Whitelist a channel in this server")
@app_commands.describe(channel="Channel to whitelist")
async def whitelist(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    settings = get_guild_settings(interaction.guild.id)
    if channel.id in settings.get("whitelisted_channels", []):
        return await interaction.response.send_message("✅ Already whitelisted.", ephemeral=True)

    settings.setdefault("whitelisted_channels", []).append(channel.id)
    save_config()
    await interaction.response.send_message(f"✅ Whitelisted {channel.mention} in this server.", ephemeral=True)

@tree.command(name="deletemsg", description="Delete many messages")
@app_commands.describe(quantity="Number of messages")
async def deletemsg(interaction: discord.Interaction, quantity: int):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    # (same loop code as before)
    await interaction.response.defer(ephemeral=True)
    total = 0
    rem = quantity
    while rem > 0:
        batch = min(100, rem)
        try:
            d = await interaction.channel.purge(limit=batch)
            total += len(d)
            rem -= len(d)
            if len(d) < batch: break
            await asyncio.sleep(0.5)
        except: break
    await interaction.followup.send(f"🗑️ Deleted **{total}** messages.", ephemeral=True)

@tree.command(name="deleteusrmsg", description="Delete user messages")
@app_commands.describe(user="User", quantity="Number")
async def deleteusrmsg(interaction: discord.Interaction, user: discord.Member, quantity: int):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    total = 0
    rem = quantity
    def check(m): return m.author.id == user.id
    while rem > 0:
        batch = min(100, rem)
        try:
            d = await interaction.channel.purge(limit=batch, check=check)
            total += len(d)
            rem -= len(d)
            if len(d) < batch: break
            await asyncio.sleep(0.5)
        except: break
    await interaction.followup.send(f"🗑️ Deleted **{total}** messages from {user}.", ephemeral=True)

@tree.command(name="invite", description="Bot Invite Link")
async def invite(interaction: discord.Interaction):
    link = "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID_HERE&scope=bot+applications.commands&permissions=8"
    await interaction.response.send_message(f"**Invite:**\n{link}", ephemeral=True)

# ==================== RUN ====================
if __name__ == "__main__":
    if config["token"] == "YOUR_BOT_TOKEN_HERE":
        print("❌ Put your token in config.json")
    else:
        bot.run(config["token"])
