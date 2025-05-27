print("✅ Script started")  # very top
from keep_alive import keep_alive
import discord
from discord.ext import tasks
from discord import app_commands
import json
import os
from dotenv import load_dotenv
import pytz
from datetime import datetime

# Load .env variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

# Initialize bot
class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

bot = MyBot()

# --- Data Handling ---
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- Bonus Calculation ---
def calculate_bonus(event_type, result, time, kills):
    base_bonus = 0
    special_bonus = 0
    et = event_type.lower()
    res = result.lower()

    if et == "informal":
        base_bonus = kills * (45000 if res == "win" else 4000)
    elif et == "rpticket":
        if res == "win":
            if time == "10:30":
                special_bonus = 300000
            elif time in ["16:30", "22:30"]:
                special_bonus = 350000
    elif et == "bizwar":
        base_bonus = kills * (30000 if res == "win" else 3000)
    elif et == "capturefoundry":
        base_bonus = kills * (20000 if res == "win" else 5000)
    elif et == "weaponfactory":
        base_bonus = kills * (10000 if res == "win" else 2000)
    elif et == "hoteltakeover":
        base_bonus = kills * (25000 if res == "win" else 5000)
    elif et == "ratingbattle":
        base_bonus = kills * (30000 if res == "win" else 5000)
    elif et == "sphere":
        base_bonus = 20000 if res in ["win", "defend"] else 0
    elif et == "famraid":
        base_bonus = 20000 if res == "win" else 0
    elif et == "robbery":
        base_bonus = 30000 if res == "win" else 0
    elif et == "shopping":
        base_bonus = 100000
    elif et == "vineyard":
        base_bonus = 30000 if res == "win" else 0
    elif et == "harbour":
        base_bonus = kills * 20000
    return base_bonus, special_bonus

# --- Slash Commands ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot is ready as {bot.user}")
    hourly_signup.start()

@bot.tree.command(name="add")
@app_commands.describe(
    event_type="Type of the event",
    result="Win or Loss",
    time="Time of event",
    date="Date of event",
    player_data="Player data in Name|ID|Kills format"
)
async def add(interaction: discord.Interaction, event_type: str, result: str, time: str, date: str, player_data: str):
    await interaction.response.defer()  # ✅ Prevents 404 error for long processing

    entries = load_data()
    attachment_url = interaction.attachments[0].url if interaction.attachments else None
    lines = player_data.strip().split("\n")

    for line in lines:
        try:
            name, pid, kills = [x.strip() for x in line.split("|")]
            kills = int(kills)
        except:
            await interaction.followup.send(f"⚠️ Invalid format in line: `{line}`. Use `Name|ID|Kills`.", ephemeral=True)
            return

        base_bonus, special_bonus = calculate_bonus(event_type, result, time, kills)
        net_bonus = base_bonus + special_bonus
        entry = {
            "name": name,
            "id": pid,
            "kills": kills,
            "event_type": event_type,
            "result": result,
            "time": time,
            "date": date,
            "base_bonus": base_bonus,
            "special_bonus": special_bonus,
            "net_bonus": net_bonus,
            "status": "Due",
            "proof": attachment_url
        }
        entries.append(entry)

    save_data(entries)
    await interaction.followup.send("✅ Data added successfully!")

@bot.tree.command(name="summary")
async def summary(interaction: discord.Interaction):
    entries = load_data()
    summary_dict = {}
    for e in entries:
        pid = e["id"]
        if pid not in summary_dict:
            summary_dict[pid] = {
                "name": e["name"],
                "kills": 0,
                "base": 0,
                "special": 0,
                "total": 0,
                "statuses": []
            }
        summary_dict[pid]["kills"] += e["kills"]
        summary_dict[pid]["base"] += e["base_bonus"]
        summary_dict[pid]["special"] += e["special_bonus"]
        summary_dict[pid]["total"] += e["net_bonus"]
        summary_dict[pid]["statuses"].append(e["status"])

    msg = "📊 **Weekly Player Summary**\n\n"
    for pid, data in summary_dict.items():
        all_paid = all(s == "Paid" for s in data["statuses"])
        status = "✅ Paid" if all_paid else "❌ Due"
        msg += f"👤 **{data['name']}** | 🆔 {pid}\n"
        msg += f"Kills: {data['kills']}, Base: ${data['base']:,}, Special: ${data['special']:,}, Total: ${data['total']:,}\n"
        msg += f"Status: {status}\n\n"
    await interaction.response.send_message(msg[:1900] if len(msg) > 1900 else msg)

@bot.tree.command(name="showall")
async def showall(interaction: discord.Interaction):
    entries = load_data()
    if not entries:
        await interaction.response.send_message("📂 No data found.")
        return
    msg = ""
    for i, e in enumerate(entries, 1):
        msg += f"{i}. **{e['name']}** | ID: {e['id']}\n"
        msg += f"Event: {e['event_type']} ({e['result']}), Date: {e['date']} {e['time']}\n"
        msg += f"Kills: {e['kills']} | Base: ${e['base_bonus']:,}, Special: ${e['special_bonus']:,}, Net: ${e['net_bonus']:,}\n"
        msg += f"Status: {e['status']}\n"
        if e.get("proof"):
            msg += f"📸 Proof: {e['proof']}\n"
        msg += "\n"
    await interaction.response.send_message(msg[:1900] if len(msg) > 1900 else msg)

@bot.tree.command(name="mark")
@app_commands.describe(pid="Player ID", status="Paid or Due")
async def mark(interaction: discord.Interaction, pid: str, status: str):
    status = status.capitalize()
    if status not in ["Paid", "Due"]:
        await interaction.response.send_message("❌ Status must be either `Paid` or `Due`.")
        return
    entries = load_data()
    count = 0
    for e in entries:
        if e["id"] == pid:
            e["status"] = status
            count += 1
    save_data(entries)
    await interaction.response.send_message(f"✅ Marked {count} entries for ID `{pid}` as `{status}`.")

@bot.tree.command(name="clearall")
async def clearall(interaction: discord.Interaction):
    if not any(r.name == "Admin" for r in interaction.user.roles):
        await interaction.response.send_message("❌ Only users with the `Admin` role can clear data.")
        return
    save_data([])
    await interaction.response.send_message("🗑️ All data has been cleared.")

@bot.tree.command(name="cmdhelp")
async def help_command(interaction: discord.Interaction):
    help_text = """
**📜 Help — Bonus Bot Guide**

__Slash Commands__:
- `/add <event_type> <Win/Loss> <time> <date> <PlayerID|PlayerName|Kills>`
- `/summary`
- `/mark <PlayerID> <Paid/Due>`
- `/clearall`
- `/showall`
    """
    await interaction.response.send_message(help_text)

# --- Hourly Signup ---
signup_channel_id = 1365834529549582416
role_id = 1365837910963785808
signed_up_users = set()
signup_message_id = None

@tasks.loop(minutes=1)
async def hourly_signup():
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    if now.minute == 0:
        channel = bot.get_channel(signup_channel_id)
        if channel:
            global signed_up_users, signup_message_id
            signed_up_users = set()
            msg = await channel.send(f"<@&{role_id}> Put '+' to sign up for the informal.")
            signup_message_id = msg.id
            await msg.add_reaction("➕")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    global signup_message_id
    if (payload.message_id == signup_message_id or payload.channel_id == signup_message_id) and str(payload.emoji) == "➕":
        guild = discord.utils.get(bot.guilds, id=payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member and not member.bot:
            if member.id not in signed_up_users and len(signed_up_users) < 10:
                signed_up_users.add(member.id)
            elif member.id in signed_up_users:
                channel = bot.get_channel(payload.channel_id)
                if hasattr(channel, 'send'):
                    await channel.send(f"{member.display_name}, you're already signed up.")
            else:
                channel = bot.get_channel(payload.channel_id)
                if hasattr(channel, 'send'):
                    await channel.send("⛔ Sign-up limit reached (10 members).")

@bot.tree.command(name="signuplist")
async def signuplist(interaction: discord.Interaction):
    if not signed_up_users:
        await interaction.response.send_message("📭 No one has signed up yet.")
    else:
        names = [interaction.guild.get_member(uid).mention for uid in signed_up_users]
        await interaction.response.send_message("✅ Signed-up Users:\n" + "\n".join(names))

# --- Run the bot ---
if __name__ == '__main__':
    keep_alive()
    bot.run(TOKEN)
    
@bot.event
async def on_ready():
    print(f"✅ Bot is ready as {bot.user}")
