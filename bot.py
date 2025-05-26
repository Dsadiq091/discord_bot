import discord
from discord.ext import commands
import json
from dotenv import load_dotenv
from keep_alive import keep_alive
import os 

load_dotenv()
TOKEN = os.getenv("TOKEN")
keep_alive()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")

@bot.command()
async def add(ctx, event_type, result, time, date, *, player_data):
    entries = load_data()
    attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None
    lines = player_data.strip().split("\n")
    for line in lines:
        try:
            name, pid, kills = [x.strip() for x in line.split("|")]
            kills = int(kills)
        except:
            await ctx.send(f"⚠️ Invalid format in line: `{line}`. Use `Name|ID|Kills`.")
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
    await ctx.send("✅ Data added successfully!")

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

@bot.command()
async def summary(ctx):
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
    await ctx.send(msg)

@bot.command()
async def showall(ctx):
    entries = load_data()
    if not entries:
        await ctx.send("📂 No data found.")
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
    await ctx.send(msg[:1900] if len(msg) > 1900 else msg)

@bot.command()
async def mark(ctx, pid, status):
    status = status.capitalize()
    if status not in ["Paid", "Due"]:
        await ctx.send("❌ Status must be either `Paid` or `Due`.")
        return
    entries = load_data()
    count = 0
    for e in entries:
        if e["id"] == pid:
            e["status"] = status
            count += 1
    save_data(entries)
    await ctx.send(f"✅ Marked {count} entries for ID `{pid}` as `{status}`.")

@bot.command()
async def clearall(ctx):
    admin_role = discord.utils.get(ctx.author.roles, name="Admin")
    if not admin_role:
        await ctx.send("❌ Only users with the `Admin` role can clear data.")
        return
    save_data([])
    await ctx.send("🗑️ All data has been cleared.")

@bot.command(name='cmdhelp')
async def help_command(ctx):
    help_text = """
**📜 Help — Bonus Bot Guide**

__Main Commands__:
- `!add <event_type> <Win/Loss> <time> <date> <PlayerID|PlayerName|Kills> ...`
  ➤ Adds player data and calculates bonuses.
  ➤ Example:
    `!add Informal Win 10:30 2024-05-26 101|John Doe|5 102|Jane Smith|3`

- `!summary`
  ➤ Shows all stored data with total bonuses (player not repeated).

- `!markpaid <PlayerID>` or `!markdue <PlayerID>`
  ➤ Marks a player’s status.

- `!proof <image_url>`
  ➤ Adds proof image to be shown in summary.

- `!clear`
  ➤ Admin only. Clears all stored data.

- `!showproof`
  ➤ Displays the last proof image uploaded.

__Note__:
- Use `|` between PlayerID, Name, and Kills.
- Event types and Win/Loss are **case-sensitive**.
- You can add multiple players in one `!add` command.

__Example Workflow__:
1. `!add Informal Win 10:30 2024-05-26 101|John|5 102|Jane|3`
2. `!proof https://i.imgur.com/sample.png`
3. `!summary`
4. `!markpaid 101`
    """
    await ctx.send(help_text)

from discord.ext import tasks
import pytz
from datetime import datetime

signup_channel_id = 1365834529549582416  # replace with your channel ID
role_id = 1365837910963785808

signed_up_users = set()
signup_message_id = None

@tasks.loop(minutes=1)
async def hourly_signup():
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    if now.minute == 0:  # At the top of every hour
        channel = bot.get_channel(signup_channel_id)
        if channel:
            global signed_up_users, signup_message_id
            signed_up_users = set()  # reset
            msg = await channel.send(f"<@&{1365837910963785808}> Put '+' to sign up for the informal.")
            signup_message_id = msg.id
            await msg.add_reaction("➕")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id == signup_message_id and str(payload.emoji) == "➕":
        user = payload.member
        if user.bot:
            return
        if user.id not in signed_up_users and len(signed_up_users) < 10:
            signed_up_users.add(user.id)
        elif len(signed_up_users) >= 10:
            channel = bot.get_channel(payload.channel_id)
            await channel.send("⛔ Sign-up limit reached (10 members).")
        elif user.id in signed_up_users:
            channel = bot.get_channel(payload.channel_id)
            await channel.send(f"{user.display_name}, you're already signed up.")

@bot.command()
async def signuplist(ctx):
    if not signed_up_users:
        await ctx.send("📭 No one has signed up yet.")
    else:
        names = [bot.get_user(uid).mention for uid in signed_up_users]
        await ctx.send("✅ Signed-up Users:\n" + "\n".join(names))

@bot.event
async def on_ready():
    hourly_signup.start()
    print(f"Bot is ready and running as {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
