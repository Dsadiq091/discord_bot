```python
import os
import json
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands, tasks

# --- Web Server to keep bot alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Start web server in background
def keep_alive():
    Thread(target=run_web, daemon=True).start()

# --- Bot Setup ---
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Data storage
DATA_FILE = 'data.json'

def load_data():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return []
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(d):
    with open(DATA_FILE, 'w') as f:
        json.dump(d, f, indent=2)

# --- Bonus Rules Configuration ---
BONUS_RULES = {
    'informal':  {'win': 45000, 'loss': 4000},
    'rpticket':  {},  # special handled below
    'bizwar':    {'win': 30000, 'loss': 3000},
    'capturefoundry': {'win': 20000, 'loss': 5000},
    'weaponfactory':  {'win': 10000, 'loss': 2000},
    'hoteltakeover': {'win': 25000, 'loss': 5000},
    'ratingbattle':  {'win': 30000, 'loss': 5000},
    'sphere':        {'win': 20000, 'defend': 20000, 'loss': 0},
    'famraid':       {'win': 20000, 'loss': 0},
    'robbery':       {'win': 30000, 'loss': 0},
    'shopping':      {'win': 100000, 'loss': 0},
    'vineyard':      {'win': 30000, 'loss': 0},
    'harbour':       {'win': 20000, 'loss': 20000},
}
# RP Ticket special tickets by time
RP_TICKET_BONUS = {'10:30': 300000, '16:30': 350000, '22:30': 350000}

# Calculate bonuses
def calculate_bonus(event_type: str, result: str, time: str, kills: int):
    et = event_type.lower()
    res = result.lower()
    base_rate = BONUS_RULES.get(et, {}).get(res)
    # Base per-kill bonus if defined
    base_bonus = base_rate * kills if base_rate is not None else 0
    # Special RP Ticket bonus
    special_bonus = 0
    if et == 'rpticket' and res == 'win':
        special_bonus = RP_TICKET_BONUS.get(time, 0)
    # Total
    return base_bonus, special_bonus

# --- Slash Commands ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    hourly_signup.start()
    print(f"✅ Bot is ready as {bot.user}")

@bot.tree.command(name='add', description='Add player(s) bonus data')
@app_commands.describe(
    event_type='Type of event', result='Win or Loss',
    time='Event time (HH:MM)', date='Date (YYYY-MM-DD)',
    player_data='Lines: Name|ID|Kills (newline separated)')
async def add_slash(interaction: discord.Interaction, event_type: str,
                    result: str, time: str, date: str, player_data: str):
    entries = load_data()
    attachment_url = interaction.message.attachments[0].url if interaction.message and interaction.message.attachments else None
    for line in player_data.split("\n"):
        parts = [x.strip() for x in line.split("|")]
        if len(parts) != 3 or not parts[2].isdigit():
            await interaction.response.send_message(
                "⚠️ Use correct format: Name|ID|Kills", ephemeral=True)
            return
        name, pid, kills_str = parts
        kills = int(kills_str)
        base, special = calculate_bonus(event_type, result, time, kills)
        entries.append({
            'name': name, 'id': pid, 'kills': kills,
            'event_type': event_type, 'result': result,
            'time': time, 'date': date,
            'base_bonus': base, 'special_bonus': special,
            'net_bonus': base + special,
            'status': 'Due', 'proof': attachment_url
        })
    save_data(entries)
    await interaction.response.send_message("✅ Data added successfully.")

@bot.tree.command(name='summary', description='Show total bonuses per player')
async def summary_slash(interaction: discord.Interaction):
    entries = load_data()
    summary = {}
    for e in entries:
        key = (e['id'], e['name'])
        if key not in summary:
            summary[key] = {'kills': 0, 'base': 0, 'special': 0, 'total': 0, 'statuses': []}
        summary[key]['kills'] += e['kills']
        summary[key]['base'] += e['base_bonus']
        summary[key]['special'] += e['special_bonus']
        summary[key]['total'] += e['net_bonus']
        summary[key]['statuses'].append(e['status'])
    lines = []
    for (pid, name), v in summary.items():
        status = '✅ Paid' if all(s == 'Paid' for s in v['statuses']) else '❌ Due'
        lines.append(f"{name} ({pid}): Kills {v['kills']}, Total ${v['total']:,}, {status}")
    await interaction.response.send_message("\n".join(lines) or 'No data.')

@bot.tree.command(name='showall', description='Show all entries in detail')
async def showall_slash(interaction: discord.Interaction):
    entries = load_data()
    messages = []
    for i, e in enumerate(entries, 1):
        messages.append(
            f"{i}. {e['name']}|{e['id']} — {e['date']} {e['time']} — "
            f"${e['net_bonus']:,} — {e['status']}"
        )
    await interaction.response.send_message("\n".join(messages) or 'No entries')

@bot.tree.command(name='mark', description='Mark entries Paid or Due')
@app_commands.describe(player_id='Player ID', status='Paid or Due')
async def mark_slash(interaction: discord.Interaction, player_id: str, status: str):
    d = load_data()
    count = 0
    for e in d:
        if e['id'] == player_id:
            e['status'] = status.capitalize(); count += 1
    save_data(d)
    await interaction.response.send_message(f"✅ Marked {count} entries as {status}.")

@bot.tree.command(name='clearall', description='Clear all data (Admin only)')
async def clearall_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ Admin only.', ephemeral=True)
        return
    save_data([])
    await interaction.response.send_message('🗑️ All data cleared.')

@bot.tree.command(name='signuplist', description='Show current sign-ups')
async def signuplist_slash(interaction: discord.Interaction):
    mentions = [f"<@{uid}>" for uid in signed_up_users]
    await interaction.response.send_message("\n".join(mentions) or 'No sign-ups yet.')

@bot.tree.command(name='help', description='Show bot command help')
async def help_slash(interaction: discord.Interaction):
    help_text = (
        "/add event_type result time date player_data — Add data (newline separated)\n"
        "/summary — Show total bonus summary\n"
        "/showall — Show all entries\n"
        "/mark player_id status — Mark Paid/Due\n"
        "/clearall — Clear all (Admin only)\n"
        "/signuplist — List current sign-ups\n"
    )
    await interaction.response.send_message(help_text)

# --- Hourly Signup Feature ---
signup_channel_id = 1365834529549582416
role_id = 1365837910963785808
signed_up_users = set()
signup_msg_id = None

@tasks.loop(hours=1)
async def hourly_signup():
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    channel = bot.get_channel(signup_channel_id)
    if channel:
        signed_up_users.clear()
        msg = await channel.send(f"<@&{role_id}> Put '+' to sign up for the informal.")
        global signup_msg_id
        signup_msg_id = msg.id

@bot.event
async def on_raw_reaction_add(payload):
    global signup_msg_id
    if payload.message_id == signup_msg_id and str(payload.emoji) == "➕" and payload.user_id != bot.user.id:
        if payload.user_id not in signed_up_users and len(signed_up_users) < 10:
            signed_up_users.add(payload.user_id)
        else:
            ch = bot.get_channel(payload.channel_id)
            await ch.send("⛔ Cannot sign up.")

# --- Run the bot ---
if __name__ == '__main__':
    keep_alive()
    bot.run(TOKEN)
```
