"""
=======================================================================
                       Discord 虛擬寵物機器人
=======================================================================

功能說明：
這是一個可以認養虛擬寵物的 Discord 機器人
寵物會定時送禮物、表達心情，還可以跟主人玩遊戲
使用 AI 生成寵物的個性、對話和圖片

主要指令：
• ?adopt 寵物名字    - 認養一隻新寵物
• ?play_ball        - 跟寵物玩球遊戲
• ?test            - 測試機器人是否正常運作

寵物行為：
• 每 5-10 分鐘會帶禮物給主人
• 每 7-14 分鐘會表達心情不好
• 可以透過玩球遊戲互動
=======================================================================
"""

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


# ========================= 設定區域 ============================

# 建立機器人實例 - 設定權限和指令前綴
intents = discord.Intents.all()  # 設定機器人的權限 - 可以接收所有事件
bot = commands.Bot(intents=intents, command_prefix="?")  # 指令前綴是 "?"

# 讀取環境變數設定檔
import os
from dotenv import load_dotenv
load_dotenv()  # 載入 .env 檔案

# API 設定 - 從環境變數讀取敏感資訊
NGROK_URL = "" # AI 圖片生成服務的網址
DISCORD_TOKEN = ""  # Discord 機器人的 Token
GEMINI_API_KEY = "" # Google Gemini AI 的 API Key

# ========================= AI 圖片生成功能 ============================

async def request_photo(prompt) -> requests.Response:
    """
    向 AI 圖片生成服務發送請求
    參數:
        prompt (str): 圖片生成的描述文字
    回傳:
        requests.Response: HTTP 回應物件
    """
    # 使用 POST 方法向 ngrok URL 發送 JSON 資料
    return requests.post(f"{NGROK_URL}/", json={"prompt": prompt})

async def send_AI_picture(ctx, *, prompt):
    """
    生成 AI 圖片並發送到 Discord 頻道
    參數:
        ctx: Discord 上下文（可以是頻道、訊息等）
        prompt (str): 圖片生成的描述文字
    """
    try:
        # 步驟1: 發送圖片生成請求
        response = await request_photo(prompt)

        # 步驟2: 檢查 API 回應狀態
        if response.status_code != 200:
            print("❌ API 請求失敗")
            return ""

        # 步驟3: 解析 JSON 回應資料
        data = response.json()

        # 步驟4: 檢查圖片生成是否成功
        if data['status'] != 'success':
            print("❌ 圖片生成失敗")
            return ""
      
        # 步驟5: 將 base64 編碼的圖片轉換為檔案
        image_data = base64.b64decode(data['image'])  # 解碼 base64
        buffer = BytesIO(image_data)                   # 轉換為記憶體檔案
        file = discord.File(buffer, filename="gift.png")  # 建立 Discord 檔案物件
        
        # 步驟6: 發送圖片檔案到頻道
        await ctx.send(file=file)
        
    except Exception as e:
        print(f"❌ 發送圖片時發生錯誤: {e}")
        raise e
    
async def generate_AI_avatar(ctx, *, prompt):
    """
    生成寵物頭像圖片（回傳圖片資料，不直接發送）
    參數:
        ctx: Discord 上下文
        prompt (str): 頭像生成的描述文字
    回傳:
        bytes: 圖片的位元組資料（用於創建 webhook 頭像）
    """
    try:
        # 步驟1: 發送圖片生成請求
        response = await request_photo(prompt)

        # 步驟2: 檢查回應狀態
        if response.status_code != 200:
            print("❌ 頭像生成 API 請求失敗")
            return ""

        # 步驟3: 解析回應資料
        data = response.json()

        if data['status'] != 'success':
            print("❌ 頭像圖片生成失敗")
            return ""

        # 步驟4: 轉換圖片資料並回傳
        image_data = base64.b64decode(data['image'])
        buffer = BytesIO(image_data)
        return buffer.read()  # 回傳圖片的位元組資料
        
    except Exception as e:
        print(f"❌ 生成頭像時發生錯誤: {e}")
        raise e

# ========================= AI 文字生成功能 ============================

# 啟動 Gemini AI 服務
genai.configure(api_key=GEMINI_API_KEY)

# 設定 AI 模型
model = genai.GenerativeModel('gemini-2.0-flash')

def generate_word(prompt):
    """
    使用 Gemini AI 生成文字回應
    參數:
        prompt (str): 輸入給 AI 的提示文字
    回傳:
        str: AI 生成的回應文字
    """
    response = model.generate_content(prompt)
    print(f"AI 回應: {response.text}")
    return response.text


# ========================= 寵物資料管理 ============================

"""
pet 字典儲存寵物的所有資訊:
{
    "name": "寵物名稱",
    "description": "寵物個性描述", 
    "channel_id": "頻道ID",
    "avatar": "寵物頭像圖片資料",
    "gift_due": "下次送禮時間",
    "bad_mood_due": "下次心情不好時間"
}
"""
pet = {}

def pet_is_adopted():
    """
    檢查寵物是否已經被認養
    回傳:
        bool: True 表示已認養，False 表示未認養
    """
    # 如果寵物有名字，代表已經被認養了
    if not pet.get("name"):
        return False
    return True


# ========================= 定時事件系統 ============================

def reset_gift_due():
    """
    重新設定下次送禮的時間（隨機 5-10 分鐘後）
    """
    random_minutes = random.randint(5, 10)
    future_time = datetime.datetime.now() + datetime.timedelta(minutes=random_minutes)
    pet["gift_due"] = future_time
    print(f"🎁 下次送禮時間設定為: {future_time.strftime('%H:%M:%S')}")

def reset_bad_mood_due():
    """
    重新設定下次心情不好的時間（隨機 7-14 分鐘後）
    """
    random_minutes = random.randint(7, 14)
    future_time = datetime.datetime.now() + datetime.timedelta(minutes=random_minutes)
    pet["bad_mood_due"] = future_time
    print(f"😢 下次心情不好時間設定為: {future_time.strftime('%H:%M:%S')}")

async def on_gift():
    """
    寵物送禮事件 - 寵物會帶禮物給主人
    這是一個自動觸發的事件，在 on_ready 中設定觸發條件
    """
    print("🎁 處理寵物送禮事件")
    
    # 檢查是否有寵物
    if not pet_is_adopted():
        return
    
    # 取得寵物所在的頻道
    channel = bot.get_channel(pet["channel_id"])

    # 生成寵物旅遊和送禮的故事
    gift_prompt = f"""
    你叫做 {pet['name']}，背景設定是 {pet['description']}。
    你去了一個地方旅遊（可能是觀光景點或野外），
    請描述這個地方，並說明你從那裡帶回了什麼禮物給心愛的主人。
    描述你在當地的見聞和帶回的土產或紀念品。
    """
    
    # 請 AI 生成故事
    story = generate_word(gift_prompt)
    
    # 從故事中提取地點名稱
    place_prompt = f"請從以下文章中提取地名：\n{story}"
    place = generate_word(place_prompt)
    
    # 建立漂亮的嵌入訊息
    embed = discord.Embed(
        title=f"🎁 {pet['name']} 的禮物", 
        description=f"📍 在 {place}", 
        color=0x44ff00  # 綠色
    )
    embed.add_field(name=f"{pet['name']} 的旅遊日記", value=story, inline=False)
    
    # 發送嵌入訊息和 AI 生成的圖片
    await channel.send(embed=embed)
    await send_AI_picture(ctx=channel, prompt=story)

async def on_bad_mood():
    """
    寵物心情不好事件 - 寵物會表達它的壞心情
    這是一個自動觸發的事件
    """
    print("😢 處理寵物心情不好事件")
    
    # 檢查是否有寵物
    if not pet_is_adopted():
        return
        
    # 取得寵物所在的頻道
    channel = bot.get_channel(pet["channel_id"])
    
    # 生成寵物心情不好的情境
    mood_prompt = f"""
    你叫做 {pet['name']}，背景設定是 {pet['description']}。
    你現在心情不好，請描述發生了什麼讓你心情不好的情況。
    """
    
    # 請 AI 生成心情故事
    mood_story = generate_word(mood_prompt)

    # 建立紅色的嵌入訊息（表示心情不好）
    embed = discord.Embed(
        title=f"😢 {pet['name']} 心情不好", 
        description="需要主人的關心", 
        color=0xff0000  # 紅色
    )
    embed.add_field(name=f"{pet['name']} 的心情", value=mood_story, inline=False)
    
    # 發送嵌入訊息和相應的圖片
    await channel.send(embed=embed)
    await send_AI_picture(ctx=channel, prompt=mood_story)
    


# ========================= Discord 指令功能 ============================

@bot.command()
async def adopt(ctx, name):
    """
    認養寵物的指令：?adopt 寵物名字
    參數:
        ctx: Discord 指令上下文
        name: 要給寵物取的名字
    """
    # 告訴使用者正在處理認養
    await ctx.channel.send("🔍 正在尋找最適合您的寵物...")
    
    # 步驟1: 使用 AI 生成寵物的個性描述
    personality_prompt = f"你是一隻可愛的寵物，名字叫做{name}，請描述你的個性、喜好、特點等"
    description = generate_word(personality_prompt)

    # 步驟2: 使用 AI 生成寵物的頭像
    avatar_prompt = f"你是一隻名叫{name}的寵物，設定是{description}，請根據這個設定，生成一張作為寵物頭像的圖片"
    avatar_data = await generate_AI_avatar(ctx=ctx, prompt=avatar_prompt)

    # 步驟3: 建立 Webhook（用來模擬寵物說話）
    webhook = await ctx.channel.create_webhook(name="PET_Webhook", avatar=avatar_data)

    # 步驟4: 儲存寵物資料到全域變數
    global pet
    pet = {
        "name": name, 
        "description": description, 
        "channel_id": ctx.channel.id, 
        "avatar": avatar_data
    }

    # 步驟5: 設定定時事件的時間
    reset_gift_due()
    reset_bad_mood_due()
    
    # 步驟6: 讓寵物跟主人打招呼
    greet_prompt = f"你是一隻名叫{name}的寵物，背景設定是{description}，現在要跟剛認養你的主人打招呼" 
    greeting = generate_word(greet_prompt)
    await webhook.send(greeting, username=name)

    # 步驟7: 清理 Webhook
    await webhook.delete()
    
    print(f"✅ 寵物 {name} 認養成功！")

@bot.command()
async def play_ball(ctx):
    """
    跟寵物玩球的互動遊戲：?play_ball
    使用者點擊表情符號選擇球類，寵物會隨機回應心情
    """
    # 步驟1: 檢查是否已認養寵物
    if not pet_is_adopted():
        await ctx.channel.send("❌ 請先用 `?adopt 寵物名字` 認養寵物！")
        return
    
    # 步驟2: 建立 Webhook 來模擬寵物說話
    webhook = await ctx.channel.create_webhook(name="PET_Webhook", avatar=pet["avatar"])
    
    # 步驟3: 寵物邀請玩球
    invitation = f"{pet['name']}現在想玩球♪(´▽｀) 我們一起玩好不好~"
    question_message = await webhook.send(invitation, username=pet["name"], wait=True)

    # 步驟4: 加入球類表情符號選項
    ball_options = ["🏀", "⚽", "⚾"]  # 籃球、足球、棒球
    for ball in ball_options:
        await question_message.add_reaction(ball)

    # 步驟5: 等待使用者點擊表情符號（10秒內）
    def check_reaction(reaction, user): 
        # 忽略機器人自己的反應
        if user.bot:
            return False
        return True
    
    try:
        # 等待使用者的反應
        await bot.wait_for("reaction_add", check=check_reaction, timeout=10)
        
        # 步驟6: 寵物隨機回應（心情好壞程度）
        mood_level = random.randint(1, 3)  # 1=心情差, 2=普通, 3=開心
        
        if mood_level == 1:
            response = "我不想玩這個 o(≧口≦)o"
        elif mood_level == 2:
            response = "嗯...好吧，這個球也不錯 ⊙.☉"
        else:
            response = "好開心！最喜歡跟主人一起玩了 (≧▽≦)"
            
        # 更新訊息內容
        await question_message.edit(content=response)
        
    except asyncio.TimeoutError:
        # 如果10秒內沒有反應，寵物會失望
        await question_message.edit(content="嗚...主人都不理我 (´･ω･`)")

    # 步驟7: 清理表情符號和 Webhook
    await question_message.clear_reactions()
    await webhook.delete()
    
    print(f"🎾 完成與 {pet['name']} 的玩球遊戲")


# ========================= Discord 機器人事件系統 ============================

@bot.event
async def on_ready():
    """
    機器人啟動時執行的事件
    負責處理定時系統 - 定期檢查是否該觸發寵物事件
    """
    print(f'🤖 機器人已成功登入: {bot.user}')
    print('📡 開始監聽寵物事件...')

    # 無限循環 - 持續監聽定時事件
    while True:
        await asyncio.sleep(5)  # 每5秒檢查一次

        # 如果沒有寵物，跳過檢查
        if not pet_is_adopted():
            continue
        
        current_time = datetime.datetime.now()
        
        # 檢查是否該送禮了
        if current_time >= pet["gift_due"]:
            print(f"⏰ 觸發送禮事件 - 時間: {current_time.strftime('%H:%M:%S')}")
            await on_gift()       # 直接呼叫送禮函數
            reset_gift_due()      # 重設下次送禮時間

        # 檢查是否該心情不好了
        if current_time >= pet["bad_mood_due"]:
            print(f"⏰ 觸發心情不好事件 - 時間: {current_time.strftime('%H:%M:%S')}")
            await on_bad_mood()   # 直接呼叫心情不好函數
            reset_bad_mood_due()  # 重設下次心情不好時間

@bot.event
async def on_message(message):
    """
    處理使用者傳送的訊息事件
    包含測試指令和強制觸發事件的隱藏指令
    """
    # 忽略機器人自己發送的訊息（避免無限循環）
    if message.author.bot:
        return

    # 隱藏的測試指令 - 強制觸發送禮事件
    if message.content == "?force_due_gift":
        print("🔧 【開發者測試】強制觸發送禮事件")
        await on_gift()
        reset_gift_due()
        return

    # 隱藏的測試指令 - 強制觸發心情不好事件  
    if message.content == "?force_due_bad_mood":
        print("🔧 【開發者測試】強制觸發心情不好事件")
        await on_bad_mood()
        reset_bad_mood_due()
        return
    
    # 基本測試指令
    if message.content == "?test":
        await message.channel.send("✅ 機器人運作正常！")
        return

    # 重要：確保其他指令能正常執行
    await bot.process_commands(message)


# ========================= 啟動機器人 ============================

# 使用環境變數中的 Token 啟動機器人
print("🚀 正在啟動 Discord 寵物機器人...")
bot.run(DISCORD_TOKEN)