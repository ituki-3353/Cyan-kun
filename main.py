import discord
import os
import json
import traceback
from openai import OpenAI
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

# --- 設定 ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# 会話履歴を保持する辞書（チャンネルIDごとに履歴を分ける）
# 最大10件まで保持
message_history = defaultdict(list)
MAX_HISTORY = 10

def load_cyan_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False, indent=2)

client_ai = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

intents = discord.Intents.default()
intents.message_content = True 
client_discord = discord.Client(intents=intents)

@client_discord.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content
    channel_id = message.channel.id

    # 「シアン」または「Cyan」が含まれる場合に反応
    if "シアン" in content or "Cyan" in content:
        async with message.channel.typing():
            try:
                current_settings = load_cyan_config()
                
                # システムプロンプトの構築
                system_message = {
                    "role": "system",
                    "content": f"You are a specific AI character based on this JSON:\n{current_settings}"
                }

                # 履歴に今回のユーザー入力を追加
                message_history[channel_id].append({"role": "user", "content": content})

                # 送信用メッセージリストの作成（System + 履歴）
                messages_to_send = [system_message] + message_history[channel_id]

                response = client_ai.chat.completions.create(
                    model="deepseek/deepseek-chat", 
                    messages=messages_to_send,
                    extra_headers={
                        "HTTP-Referer": "http://localhost",
                        "X-Title": "Cyan-kun Discord Bot",
                    }
                )
                
                answer = response.choices[0].message.content
                
                # 履歴にAIの回答を追加
                message_history[channel_id].append({"role": "assistant", "content": answer})

                # 履歴が長くなりすぎたら古いものから削除
                if len(message_history[channel_id]) > MAX_HISTORY:
                    message_history[channel_id] = message_history[channel_id][-MAX_HISTORY:]

                await message.reply(answer[:2000])
                
            except Exception as e:
                print(f"--- ERROR ---\n{traceback.format_exc()}")
                await message.reply("エラーが出てるみたい！/nあどみんさんに相談してみて！")

client_discord.run(DISCORD_TOKEN)