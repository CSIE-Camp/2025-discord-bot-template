import discord
from discord.ext import commands
import random
import datetime
import asyncio
import requests
import base64
import google.generativeai as genai
from io import BytesIO
# import nest_asyncio


# ========================= 設定 ============================


intents = discord.Intents.all()
bot = commands.Bot(intents=intents, command_prefix="?")

import os
from dotenv import load_dotenv

load_dotenv()

# 替換成你的 ngrok URL
NGROK_URL = os.getenv('NGROK_URL') 
# 填入你的 discord 機器人 token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# 填入你的 gemini 的 API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')


async def request_photo(prompt) -> requests.Response:
    """
    發送請求到 ngrok 的 API 端點，並獲取生成的圖片
    回傳是 requests.Response 物件，需要用generate_photo_url() 來處理
    """
    return requests.post(f"{NGROK_URL}/",json={"prompt": prompt})

async def generate_photo_byteIO(ctx, *, prompt):
    """
    ctx: 可以發送訊息的物件。有可能是 channel, webhook, message 等等
    回傳是圖片的 URL，可以用embed 或者send等等方法發送
    """    
    try:
        response = await request_photo(prompt)

        if response.status_code != 200:
            print("API 請求失敗")
            return ""

        data = response.json()

        if data['status'] != 'success':
            print("生成圖片時發生錯誤")
            return ""
      
        #將 base64 轉回圖片
        image_data = base64.b64decode(data['image'])
        return BytesIO(image_data)                      
    except Exception as e:
         raise e # 暫時不處理錯誤

# 啟動 gemini
genai.configure(api_key=GEMINI_API_KEY)

# 設定模型
model = genai.GenerativeModel('gemini-2.0-flash')

def generate_word(arg):
    response = model.generate_content(arg)
    print(response.text)
    return response.text


# =================== 設定寵物資料的全域變數 ====================


"""
pet 字典的格式如下：
pet = {"name": (寵物名稱), "description": (寵物個性敘述), "photo_url": (寵物圖片), "channel_id": (頻道ID), "gift_due": (禮物時間)}
"""
pet = {}

def pet_is_adopted():
    """
    藉由測試任何一個字典值，判斷 pet 字典是否已經初始化
    """
    if not pet.get("name"):
        return False
    return True


# ================== 被動事件 ====================


def reset_gift_due():
    """
    重設禮物時間
    """
    random_minutes = random.randint(5, 10)
    deltatime = datetime.timedelta(minutes = random_minutes)
    pet["gift_due"] = datetime.datetime.now() + deltatime

def reset_bad_mood_due():
    """
    重設心情不好的時間
    """
    random_minutes = random.randint(7, 14)
    deltatime = datetime.timedelta(minutes = random_minutes)
    pet["bad_mood_due"] = datetime.datetime.now() + deltatime

@bot.event
async def on_gift():
    """
    定期發「伴手禮」給主人
    注意，這是一個自訂的事件，觸發機制寫在 on_ready 裡面
    """
    print("handle禮物事件")
    if not pet_is_adopted():
        return
    channel = bot.get_channel(pet["channel_id"])

    word = generate_word(f"你叫做 {pet["name"]}, 背景設定是 {pet["description"]}, 你去一個地方旅遊，你去一個地方旅遊，這個地方可能是觀光景點，可能是野外，請略為描述這個地方。現在你從這個地方給心愛主人帶回了一個禮物，是這個地方的土產或在這個地方買到的紀念品、美食、商品等等, 請描述你在此地的所見所聞，描述你帶的禮物，並給主人這一個禮物")
    place = generate_word(f"請根據以下文章，提取出文章中的地名: \n{word}")
    buffer = await generate_photo_byteIO(ctx=channel, prompt=word)
    file = discord.File(fp=buffer, filename="gift.png")

    embed = discord.Embed(title = f"{pet["name"]}", description = f"在 {place}", color=0x44ff00)
    embed.add_field(name=f"{pet["name"]}的紀錄", value=word, inline=False)
    embed.set_image(url = "attachment://gift.png")
    await channel.send(embed=embed, file=file)

@bot.event
async def on_bad_mood():
    """
    定期觸發「心情不好的事件」
    """
    channel = bot.get_channel(pet["channel_id"])
    word = generate_word(f"你叫做 {pet["name"]}, 背景設定是 {pet["description"]}, 你心情不好, 請描述情境")
    buffer = await generate_photo_byteIO(ctx=channel, prompt=word)
    file = discord.File(fp=buffer, filename="bad_mood.png")
    
    embed = discord.Embed(title = f"{pet["name"]}", description = f"心情不好", color=0xff0000)
    embed.add_field(name="undefined", value="", inline=False)
    embed.set_image(url = "attachment://bad_mood.png")
    await channel.send(embed=embed, file=file)


# ======================== 主動事件 ==========================

@bot.command()
async def adopt(ctx, name):
    """
    處理認養的事件。
    """
    await ctx.channel.send("正在尋找最適合您的寵物...")
    
    description = generate_word(f"你是一隻可愛的寵物，名字叫做{name}，請描述一下你自己")
    buffer = await generate_photo_byteIO(ctx=ctx, prompt=f"你是一隻名叫{name}的寵物，設定是{description}，請根據這個設定，生成一張作為寵物頭像的圖片")
    webhook = await ctx.channel.create_webhook(name="PET_Webhook", avatar=buffer.read())

    pet = {"name": name, "description": description, "channel_id": ctx.channel.id, "photo_byteIO": buffer}

    reset_gift_due()
    reset_bad_mood_due()
    
    greet_word = generate_word(f"你是一隻名叫{name}的寵物，背景設定是{description}，跟主人打招呼吧") 
    await webhook.send(greet_word, username=name)

    await webhook.delete()
    # await webhook.send(greet_word, username=name)

    pass

@bot.command()
async def play_ball(ctx):
    """
    玩一個猜寵物想玩什麼球的遊戲
    """
    # 檢查是否已認養寵物
    if not pet_is_adopted():
        await ctx.channel.send("請先認養寵物！")
        return
    
    # 創建 webhook
    webhook = await ctx.channel.create_webhook(name="PET_Webhook", avatar=pet["photo_byteIO"].read())
    # 使用 webhook 發送訊息
    question_message = await webhook.send(f"{pet['name']}現在想玩球♪(´▽｀)，我們一起玩好不好~", username=pet["name"], wait=True)

    # 把球的表情符號加入訊息
    balls = ["🏀", "⚽", "⚾"]
    for ball in balls:
        await question_message.add_reaction(ball)

    # 等待使用者的反應
    def check(reaction, user): 
        if user.bot:  # 忽略bot自己傳的訊息
            return False
        return True
    await bot.wait_for("reaction_add", check=check, timeout=10)

    # 隨機選擇心情
    mood = random.randint(1, 3) # 1 ~ 3 => 從心情差到好
    if mood == 1:
        await question_message.edit(content="我不想玩這個o(≧口≦)o")
    elif mood == 2:
        await question_message.edit(content="嗚，好，這個球也不錯⊙.☉")
    else:
        await question_message.edit(content="好開心，最喜歡一起玩了(≧▽≦)")

    # 把選項移除
    await question_message.clear_reactions()
    # 刪除 webhook
    await webhook.delete()
    return


# ================== Discord 機器人設定 =======================


@bot.event
async def on_ready():
    print(f'已登入為 {bot.user}')

    while True:
        await asyncio.sleep(5)

        if not pet_is_adopted():
            continue
        
        print(f"{pet["name"]} 的禮物時間：{pet["gift_due"]}")
        if datetime.datetime.now() >= pet["gift_due"]:
            """
            定期觸發「送禮」事件，並且重新設定時間
            """
            bot.dispatch("on_gift")
            reset_gift_due()

        if datetime.datetime.now() >= pet["bad_mood_due"]:
            """
            定期發「心情不好」事件，並且重新設定時間
            """
            bot.dispatch("on_bad_mood")
            reset_bad_mood_due()

@bot.event
async def on_message(message):
    if message.author.bot:  # 忽略bot自己傳的訊息
        return

    if message.content == "?force_due_gift":
        print("【測試】強制觸發禮物事件")
        bot.dispatch("gift")
        reset_gift_due()

    if message.content == "?force_due_bad_mood":
        print("【測試】強制觸發心情不好的事件")
        bot.dispatch("bad_mood")
        reset_bad_mood_due()
    
    if message.content == "?test":
        """
        小提醒：注意符號的半形、全形
        """
        await message.channel.send("測試成功！")
        return

    await bot.process_commands(message)  # 確保指令可以被處理
    return


# ==================== 機器人，啟動！ ==================


# nest_asyncio.apply()
bot.run(DISCORD_TOKEN)