import discord
from discord import app_commands
import json
import os
import hashlib

# ==================== LOAD CONFIG ====================
CONFIG_FILE = 'config.json'

if not os.path.exists(CONFIG_FILE):
    print("❌ config.json not found! Creating default one...")
    default_config = {
        "token": "YOUR_BOT_TOKEN_HERE",
        "owner_id": 0,
        "afk_vc_id": 0,
        "warning_channel_id": 0,
        "banned_links": ["nustwin.com", "rackswin.com", "discord.gift", "nitro", "http", ".net", ".play", ".me", "invite"],
        "banned_words": ["bonus", "withdraw", "$2700", "nustwin", "rackswin", "mrbeast", "ip", ".play", ".net", "mera smp", "nitro", "baap", "maa", "hosting", "my server"],
        "banned_image_filenames": ["IMG_7192.jpg", "1f5f3f0b.jpg", "7c0f7032.jpg", "202384c9-1.jpg", "rackswin", "nustwin"]
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(default_config, f, indent=4)
    print("✅ Default config.json created. Please edit it!")

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# ==================== BOT SETUP ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

muted_users = set()
warning_sent = False
known_phishing_hashes = set()

# Load hashes of the 4 phishing images
async def load_phishing_hashes():
    phishing_files = [
        "/home/workdir/attachments/IMG_7192.jpg",
        "/home/workdir/attachments/1f5f3f0b.jpg",
        "/home/workdir/attachments/7c0f7032.jpg",
        "/home/workdir/attachments/202384c9-1.jpg"
    ]
    for path in phishing_files:
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                    known_phishing_hashes.add(hashlib.md5(data).hexdigest())
                print(f"✅ Loaded hash for {os.path.basename(path)}")
        except:
            pass

@bot.event
async def on_ready():
    global active_channel
    print(f'✅ Bot is online as {bot.user}')
    await tree.sync()
    await load_phishing_hashes()

    # Auto-detect most active channel for warnings
    if config.get("warning_channel_id") == 0 and bot.guilds:
        guild = bot.guilds[0]
        channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
        if channels:
            active_channel = max(channels, key=lambda c: len(c.members) if hasattr(c, 'members') else 0)
            print(f"📢 Warning channel set to: {active_channel.name}")

# AFK Voice Channel - Auto mute on join
@bot.event
async def on_voice_state_update(member, before, after):
    afk_id = config.get("afk_vc_id")
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

    # Joined AFK VC → Mute (even owner)
    if after.channel and after.channel.id == afk_id:
        if member.id not in muted_users:
            try:
                await member.edit(mute=True, reason="AFK VC - Server Muted")
                muted_users.add(member.id)
            except:
                pass

    # Left AFK VC → Unmute
    elif before.channel and before.channel.id == afk_id and (not after.channel or after.channel.id != afk_id):
        if member.id in muted_users:
            try:
                await member.edit(mute=False, reason="Left AFK VC")
                muted_users.discard(member.id)
            except:
                pass

# Phishing & Scam Message Detector
@bot.event
async def on_message(message):
    global warning_sent
    if message.author.bot:
        return

    content = message.content.lower()
    deleted = False

    # Check banned words and links
    if any(word in content for word in config.get("banned_words", [])) or \
       any(link in content for link in config.get("banned_links", [])):
        deleted = True

    # Check attachments (images)
    if message.attachments:
        for att in message.attachments:
            filename = att.filename.lower()
            if any(bad in filename for bad in config.get("banned_image_filenames", [])):
                deleted = True
                break

            # Advanced hash detection
            try:
                data = await att.read()
                img_hash = hashlib.md5(data).hexdigest()
                if img_hash in known_phishing_hashes:
                    deleted = True
                    break
            except:
                pass

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

        # Send alert once in most active channel
        if not warning_sent and 'active_channel' in globals():
            try:
                await active_channel.send(f"**🚨 Phishing Alert** {warning}")
                warning_sent = True
            except:
                pass

# Slash Commands
@tree.command(name="deletemsg", description="Delete last N messages")
@app_commands.describe(quantity="Number of messages to delete")
async def deletemsg(interaction: discord.Interaction, quantity: int):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(quantity + 1, 100))
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)-1} messages.", ephemeral=True)

@tree.command(name="deleteusrmsg", description="Delete messages from a user")
@app_commands.describe(user="Target user", quantity="Number of messages")
async def deleteusrmsg(interaction: discord.Interaction, user: discord.Member, quantity: int):
    if interaction.user.id != config["owner_id"] and not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    def check(m): return m.author.id == user.id
    deleted = await interaction.channel.purge(limit=min(quantity + 10, 100), check=check)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages from {user}.", ephemeral=True)

# ==================== RUN BOT ====================
if __name__ == "__main__":
    if config["token"] == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please put your real bot token in config.json")
    else:
        bot.run(config["token"])
