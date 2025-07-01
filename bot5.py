import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor
import asyncio, datetime
from collections import defaultdict

API_TOKEN = '7431633642:AAHfAHIn5IcjXrt_lMD3z_Up5TgQpDidmYc'  # <- ဒီမှာသင့် bot token ထည့်ပါ
bot = Bot(API_TOKEN)
dp = Dispatcher(bot)

users = set()
user_digit_bs_map = {}
user_accuracy = defaultdict(lambda: [0, 0])
user_streaks = defaultdict(lambda: {'win': 0, 'lose': 0})
user_max_streaks = defaultdict(lambda: {'win': 0, 'lose': 0})
user_last_prediction = {}
user_result_log = defaultdict(str)  # ✅ Result digit log

def get_recent_blocks():
    try:
        url = "https://apilist.tronscanapi.com/api/block"
        params = {"start": 0, "limit": 30, "sort": "-number"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"[ERROR] get_recent_blocks: {e}")
        return []

def find_block_with_sec54(blocks):
    for b in blocks:
        ts = datetime.datetime.fromtimestamp(b["timestamp"] / 1000)
        if ts.second == 54:
            return b["number"], b["hash"], ts
    return None, None, None

def extract_last_digit(h):
    for c in reversed(h):
        if c.isdigit():
            d = int(c)
            return d, "S" if d <= 4 else "B"
    return None, "Invalid"

async def monitor():
    while True:
        try:
            now = datetime.datetime.now()
            await asyncio.sleep(60 - now.second)

            blocks = get_recent_blocks()
            if not blocks:
                continue

            block_num, block_hash, ts = find_block_with_sec54(blocks)
            if not block_num:
                for uid in users:
                    await bot.send_message(uid, "❌ sec=54 block မတွေ့ပါ။")
                continue

            digit, actual_result = extract_last_digit(block_hash)

            for uid in users:
                # ✅ Log result digit
                user_result_log[uid] += str(digit)

                pattern = user_digit_bs_map.get(uid, {})
                previous_prediction = user_last_prediction.get(uid)

                if previous_prediction:
                    correct, total = user_accuracy[uid]
                    streak = user_streaks[uid]
                    max_streak = user_max_streaks[uid]

                    is_correct = previous_prediction == actual_result

                    if is_correct:
                        correct += 1
                        streak['win'] += 1
                        streak['lose'] = 0
                        max_streak['win'] = max(max_streak['win'], streak['win'])
                    else:
                        streak['lose'] += 1
                        streak['win'] = 0
                        max_streak['lose'] = max(max_streak['lose'], streak['lose'])

                    total += 1
                    user_accuracy[uid] = [correct, total]
                    user_streaks[uid] = streak.copy()
                    user_max_streaks[uid] = max_streak.copy()

                    percent = round((correct / total) * 100, 2)
                    loss_percent = round(100 - percent, 2)

                else:
                    correct = user_accuracy[uid][0]
                    total = user_accuracy[uid][1]
                    percent = round((correct / total) * 100, 2) if total else 0
                    loss_percent = round(100 - percent, 2)

                prediction = pattern.get(digit)
                user_last_prediction[uid] = prediction

                actual_icon = "🟢" if actual_result == "S" else "🟡"
                predict_icon = "🟢" if prediction == "S" else "🟡"
                actual_text = "SMALL" if actual_result == "S" else "BIG"
                next_text = "SMALL" if prediction == "S" else "BIG"

                timestamp = ts.strftime("%Y%m%d%H%M%S")

                msg = (
                    f"💡{timestamp}\n"
                    f"{actual_icon} {digit} => {actual_text} ({block_num})\n"
                    f"➡️ Next Predict: {predict_icon}{next_text if prediction else '❓'}\n"
                    f"✅ Win - {user_accuracy[uid][0]} ကြိမ် ({percent}%)\n"
                    f"❌ Lose - {user_accuracy[uid][1] - user_accuracy[uid][0]} ကြိမ် ({loss_percent}%)\n"
                    f"📈 ဆက်တိုက်အနိုင်အများဆုံး - {user_max_streaks[uid]['win']} ကြိမ်\n"
                    f"📉 ဆက်တိုက်ရှုံးအများဆုံး - {user_max_streaks[uid]['lose']} ကြိမ်"
                )

                await bot.send_message(uid, msg)

        except Exception as e:
            print(f"[ERROR] monitor(): {e}")
            await asyncio.sleep(10)

@dp.message_handler(commands=['start'])
async def send_welcome(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🎯 Pattern ထည့်မယ်"), KeyboardButton("📊 Result Log"))
    await msg.answer("မင်္ဂလာပါ။ ခန့်မှန်းလိုတဲ့ pattern ကိုထည့်ရန် ခလုတ်ကိုနှိပ်ပါ။", reply_markup=kb)

@dp.message_handler(Text(equals="🎯 Pattern ထည့်မယ်"))
async def ask_pattern(msg: types.Message):
    await msg.answer(
        "📥 Digit-to-B/S pattern များကို format တစ်ခုစီအတိုင်း ပေးပါ:\n\n"
        "`0 S`\n`1 B`\n`2 S`\n...\n\n"
        "10 line ဆက်တိုက်ရေးပြီးပေးပါ။",
        parse_mode='Markdown'
    )

@dp.message_handler(lambda m: len(m.text.splitlines()) == 10)
async def receive_pattern(msg: types.Message):
    uid = msg.from_user.id
    lines = msg.text.strip().splitlines()
    mapping = {}

    try:
        for line in lines:
            digit_str, bs = line.strip().split()
            digit = int(digit_str)
            if digit < 0 or digit > 9 or bs not in ["B", "S"]:
                raise ValueError()
            mapping[digit] = bs

        user_digit_bs_map[uid] = mapping
        users.add(uid)
        user_accuracy[uid] = [0, 0]
        user_streaks[uid] = {'win': 0, 'lose': 0}
        user_max_streaks[uid] = {'win': 0, 'lose': 0}
        user_last_prediction[uid] = None
        user_result_log[uid] = ""  # ✅ reset log

        await msg.answer("✅ Pattern ထည့်ပြီးပါပြီ။ ခန့်မှန်းမှုများ စတင်လိမ့်မည်။")

    except:
        await msg.answer("❌ Format မှားနေပါသည်။ ဥပမာ:\n\n1 S\n2 B\n...\n0 S လိုမျိုး ပေးပါ။")

@dp.message_handler(Text(equals="📊 Result Log"))
async def show_result_log(msg: types.Message):
    uid = msg.from_user.id
    log = user_result_log.get(uid, "")
    if log:
        await msg.answer(f"📊 Result Digits:\n`{log}`", parse_mode='Markdown')
    else:
        await msg.answer("📭 Encoded result digit မရှိသေးပါ။ ခန့်မှန်းမှု စတင်ပြီးမှသာရရှိမည်။")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(monitor())
    executor.start_polling(dp, skip_updates=True)