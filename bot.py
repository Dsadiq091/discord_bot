from keep_alive import keep_alive
import discord
import json
import os
from dotenv import load_dotenv
import asyncio
import pytz
from datetime import datetime
from discord.ext import commands, tasks

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
intents.reactions = True
intents.members = True

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
async def add(ctx, event_type, result, time, date, *, player_data):
    admin_role = discord.utils.get(ctx.author.roles, name="Admin")
    if not admin_role:
        await ctx.send("❌ Only users with the `Admin` role can add data.")
        return

    entries = load_data()
    attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None
    lines = player_data.strip().split("\n")
    
    for line in lines:
        try:
            name, pid, kills = [x.strip() for x in line.split("|")]
            kills = int(kills)

            if not name.isalpha():
                await ctx.send(f"❌ Invalid name in line: `{line}`. Name must contain only alphabets.")
                return
            if not pid.isdigit():
                await ctx.send(f"❌ Invalid ID in line: `{line}`. ID must be numeric.")
                return

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
    await ctx.send(msg[:1900] if len(msg) > 1900 else msg)

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
    admin_role = discord.utils.get(ctx.author.roles, name="Admin")
    if not admin_role:
        await ctx.send("❌ Only users with the `Admin` role can mark entries.")
        return

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
async def clear(ctx, pid):
    admin_role = discord.utils.get(ctx.author.roles, name="Admin")
    if not admin_role:
        await ctx.send("❌ Only users with the `Admin` role can clear player data.")
        return

    entries = load_data()
    original_length = len(entries)
    entries = [entry for entry in entries if entry["id"] != pid]
    removed_count = original_length - len(entries)

    if removed_count > 0:
        save_data(entries)
        await ctx.send(f"🧹 Removed {removed_count} entries for player ID `{pid}`.")
    else:
        await ctx.send(f"⚠️ No data found for player ID `{pid}`.")

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
- `!summary`
- `!mark <PlayerID> <Paid/Due>`
- `!clearall`
- `!showall`
- `!signuplist`
    """
    await ctx.send(help_text)

# --- Hourly Signup Feature ---
signup_channel_id = 1365834529549582416
role_id = 1365837910963785808
signed_up_users = set()
signup_message_id = None

async def wait_until_next_hour():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    if now.minute != 0 or now.second != 0:
        next_hour = next_hour.replace(hour=(now.hour + 1) % 24)
    wait_seconds = (next_hour - now).total_seconds()
    print(f"⏳ Waiting {int(wait_seconds)} seconds until next hour...")
    await asyncio.sleep(wait_seconds)

@tasks.loop(hours=1)
async def hourly_signup():
    print("📤 Running hourly signup task...")
    channel = bot.get_channel(signup_channel_id)
    if channel:
        global signed_up_users, signup_message_id
        signed_up_users = set()
        msg = await channel.send(f"<@&{role_id}> Put '+' to sign up for the informal.")
        signup_message_id = msg.id
        await msg.add_reaction("➕")

@bot.command()
async def signuplist(ctx):
    if not signed_up_users:
        await ctx.send("📭 No one has signed up yet.")
    else:
        names = [bot.get_user(uid).mention for uid in signed_up_users]
        await ctx.send("✅ Signed-up Users:\n" + "\n".join(names))

@bot.event
async def on_ready():
    print(f"✅ Bot is ready as {bot.user}")
    await bot.wait_until_ready()
    if not hourly_signup.is_running():
        await wait_until_next_hour()
        hourly_signup.start()
        print("📌 Hourly signup task started.")

# --- Run the bot ---
if __name__ == '__main__':
    keep_alive()
    bot.run(TOKEN)
