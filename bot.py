import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import Forbidden


import os
TOKEN = os.getenv("BOT_TOKEN")

WORDS = [
"տուն","մեքենա","գիրք","հեռախոս","կոմպյուտեր","ծաղիկ","փողոց","գետ","լուսին","արև","ծով","փրկիչ","թռչուն","ձի","կատու","շուն","խաղալիք","սեղան","աթոռ","պատուհան","դուռ", "պատ","գորգ","սենյակ","խոհանոց","լվացարան","սառնարան","թեյ","սուրճ","հաց","տորթ","պիցցա","սուրճի մեքենա","լուսանկարիչ","գործիքներ","մարզադահլիճ","մարզիչ","հրապարակ","պուրակ","մատիտ","գրիչ","թուղթ","գրադարան","թատրոն","կինոթատրոն","ռեստորան","սրճարան","հյուրանոց","օդանավակայան","բժշկություն","դեղատուն","մատնահետք","գանձեր","փողոցային երաժիշտ","մետրոպոլիտեն", "հրապարակ","մայրաքաղաք","պետություն","պատմություն","գիտություն","տեխնոլոգիա","համակարգիչ","սմարթֆոն","համացանց","սոցիալական ցանց","վիդեոխաղեր","սպորտ","ֆուտբոլ","բասկետբոլ","վոլեյբոլ","տենիս","շախմատ","պարապմունք","դպրոց","համալսարան","ուսանող","դասախոս","գիտնական","հրապարակախոս","ժուռնալիստ","լրագրող","ֆոտոլրագրող","ռադիոհաղորդում","հեռուստահաղորդում","կոմպոզիտոր","երգիչ","երաժշտական գործիք","թատրոնական ներկայացում","կատակերգություն","դրամա","թրիլլեր","հայկական կինո","արտասահմանյան կինո", "կինոռեժիսոր","խաղարկային ֆիլմ","դոկումենտալ ֆիլմ","անիմացիոն ֆիլմ","մուլտֆիլմ","կոմիքս","գրաֆիկական վեպ","վեպ","պոեզիա","հեքիաթ","լեգենդ","միֆ","պատմվածք","բանաստեղծություն","նովել","թրիլլեր գրականություն","հայկական գրականություն","արտասահմանյան գրականություն","բանաստեղծ","նովելիստ","պատմաբան","միֆոլոգիա","լեգենդար հերոս","հերոսական էպոս"
]

# ---------- GAME STATE ----------

def reset_game():
    return {
        "phase": "idle",          # idle | register | round | voting
        "players": {},            # user_id -> full_name
        "chat_id": None,
        "join_msg_id": None,
        "time_left": 60,
        "word": None,
        "spies": [],
        "votes": {},
        "voted": set(),
        "task": None,
    }

game = reset_game()

# ---------- HELPERS ----------

def spy_count(n):
    if n <= 4:
        return 1
    elif n <= 8:
        return 2
    else:
        return max(1, n // 4)

def players_text():
    return "\n".join(f"• {n}" for n in game["players"].values()) or "—"

# ---------- COMMANDS ----------

async def start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Բոտը ակտիվ է, կարող ես փակել այս չատը")

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game

    if game["phase"] != "idle":
        await update.message.reply_text("⚠️ Խաղն արդեն ակտիվ է")
        return

    game = reset_game()
    game["phase"] = "register"
    game["chat_id"] = update.effective_chat.id

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕵️ Միանալ", callback_data="join")]
    ])

    msg = await update.message.reply_text(
        "🎮 Լրտես խաղ — գրանցում\n"
        "⏳ 1 րոպե\n\n"
        "👥 Մասնակիցներ:\n"
        f"{players_text()}",
        reply_markup=keyboard
    )

    game["join_msg_id"] = msg.message_id
    game["task"] = asyncio.create_task(registration_timer(context))

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game

    if game["task"]:
        game["task"].cancel()

    await context.bot.send_message(game["chat_id"], "🛑 Խաղը կանգնեցվեց")
    game = reset_game()

# ---------- JOIN ----------

async def join_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = q.from_user

    if game["phase"] != "register":
        await q.answer("Գրանցումը փակ է", show_alert=True)
        return

    if u.id in game["players"]:
        await q.answer("Դու արդեն գրանցված ես", show_alert=True)
        return

    game["players"][u.id] = u.full_name

    await context.bot.edit_message_text(
        chat_id=game["chat_id"],
        message_id=game["join_msg_id"],
        text=(
            "🎮 Լրտես խաղ — գրանցում\n"
            f"⏳ Մնացել է {game['time_left']} վրկ\n\n"
            "👥 Մասնակիցներ:\n"
            f"{players_text()}"
        ),
        reply_markup=q.message.reply_markup
    )

    await q.answer("Միացար խաղին")

# ---------- GAME FLOW ----------

async def registration_timer(context):
    try:
        while game["time_left"] > 0 and game["phase"] == "register":
            await asyncio.sleep(1)
            game["time_left"] -= 1

        await start_game(context)
    except asyncio.CancelledError:
        pass

async def start_game(context):
    if len(game["players"]) < 3:
        await context.bot.send_message(game["chat_id"], "❌ Բավարար խաղացողներ չկան")
        return

    game["phase"] = "round"
    game["word"] = random.choice(WORDS)

    ids = list(game["players"].keys())
    game["spies"] = random.sample(ids, spy_count(len(ids)))

    await context.bot.send_message(
        game["chat_id"],
        "🎲 Խաղը սկսվեց\n📩 Բառերը ուղարկվել են private"
    )

    for uid in game["players"]:
        try:
            if uid in game["spies"]:
                await context.bot.send_message(uid, "🕵️‍♂️ Դու լրտես ես")
            else:
                await context.bot.send_message(uid, f"🎯 Քո բառը՝ {game['word']}")
        except Forbidden:
            pass  # user չի սեղմել /start — ignore

    await asyncio.sleep(300)
    await start_voting(context)

# ---------- VOTING ----------

async def start_voting(context):
    game["phase"] = "voting"
    game["votes"] = {n: 0 for n in game["players"].values()}
    game["voted"].clear()

    kb = [
        [InlineKeyboardButton(f"{n} (0)", callback_data=f"vote:{n}")]
        for n in game["votes"]
    ]

    await context.bot.send_message(
        game["chat_id"],
        "🗳 Քվեարկությունը բաց է",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def vote_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    voter = q.from_user.id
    name = q.data.split(":")[1]

    if voter not in game["players"]:
        await q.answer("Դու խաղի մասնակից չես", show_alert=True)
        return

    if voter in game["voted"]:
        await q.answer("Դու արդեն քվեարկել ես", show_alert=True)
        return

    game["voted"].add(voter)
    game["votes"][name] += 1

    kb = [
        [InlineKeyboardButton(f"{n} ({c})", callback_data=f"vote:{n}")]
        for n, c in game["votes"].items()
    ]

    await q.edit_message_reply_markup(InlineKeyboardMarkup(kb))
    await q.answer("Ձայնդ ընդունվեց")

    if len(game["voted"]) == len(game["players"]):
        await finish_voting(context)

async def finish_voting(context):
    global game

    suspect = max(game["votes"], key=game["votes"].get)
    spies = [game["players"][uid] for uid in game["spies"]]

    await context.bot.send_message(
        game["chat_id"],
        f"🕵️ Ամենաշատ ձայներ հավաքեց՝ {suspect}\n🔍 Ստուգում ենք..."
    )

    await asyncio.sleep(2)

    await context.bot.send_message(
        game["chat_id"],
        f"🕵️ Լրտեսներն էին՝ {', '.join(spies)}"
    )

    game = reset_game()

# ---------- APP ----------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start_private))
app.add_handler(CommandHandler("game", game_command))
app.add_handler(CommandHandler("stop", stop_command))
app.add_handler(CallbackQueryHandler(join_button, pattern="^join$"))
app.add_handler(CallbackQueryHandler(vote_button, pattern="^vote:"))

app.run_polling()

