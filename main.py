# Cyan-kun本体の.pyファイル
# 手動起動の際はこのファイルを実行、systemdなどで自動起動する際は仮想環境のpythonからこのファイルを指定して起動してください。

import datetime
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

# --- 24行目付近を修正 ---
def load_full_config(): # 名前を load_cyan_config から load_full_config に変更
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f) # ここも辞書をそのまま返す形に変更
    return json.dumps(data, ensure_ascii=False, indent=2)

client_ai = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

intents = discord.Intents.default()
intents.message_content = True 
client_discord = discord.Client(intents=intents)

@client_discord.event
async def on_ready():
    print(f'Logged in as {client_discord.user} (Name: Cyan)')
    
    try:
        full_config = load_full_config()
        server_settings = full_config.get("server_settings", {})
        
        # 統計情報の計算
        # default設定を除いたサーバー数と、全サーバーの許可チャンネル合計数
        actual_servers = [s for s in server_settings.keys() if s != "default"]
        server_count = len(actual_servers)
        channel_count = sum(len(s.get("allowed_channels", [])) for s in server_settings.values())
        
        # 現在のUTC時刻
        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        for guild in client_discord.guilds:
            server_cfg = server_settings.get(str(guild.id))
            if server_cfg and server_cfg.get("log_channel"):
                log_channel_id = server_cfg.get("log_channel")
                channel = client_discord.get_channel(log_channel_id)
                
                if channel:
                    # 埋め込みメッセージ（Embed）の作成
                    embed = discord.Embed(
                        title="自動送信ログ",
                        description="Cyan-kunが起動しました。",
                        color=discord.Color.cyan()
                    )
                    embed.add_field(
                        name="ステータス", 
                        value="・☑実行中", 
                        inline=True
                    )
                    embed.add_field(
                        name="ログ時刻", 
                        value=f"{now_utc} (UTC)", 
                        inline=True
                    )
                    embed.add_field(
                        name="統計情報",
                        value=f"フィルターされているサーバー数: {server_count}\n許可されているチャンネル数: {channel_count}",
                        inline=False
                    )
                    
                    await channel.send(embed=embed)
                    print(f"Startup log sent to {guild.name}")
                    
    except Exception as e:
        print(f"Startup log error: {traceback.format_exc()}")

@client_discord.event
async def on_message(message):
    # 自分やBot、DMは無視
    if message.author.bot or not message.guild:
        return

    # 1. 設定の動的読み込み
    full_config = load_full_config()
    server_id = str(message.guild.id)
    
    # 2. サーバー固有設定の取得
    server_cfg = full_config.get("server_settings", {}).get(server_id, full_config["server_settings"]["default"])
    allowed_channels = server_cfg.get("allowed_channels", [])
    keywords = server_cfg.get("keywords", ["シアン"])

    # 3. チャンネル制限のチェック
    if allowed_channels and message.channel.id not in allowed_channels:
        return

    # 4. キーワード判定
    content = message.content
    if any(k in content for k in keywords):
        async with message.channel.typing():
            try:
                # 5. システムプロンプトの構築（AIに渡す情報を整理）
                # identity, behavior_rules, strict_observance, few_shot_examples を抽出
                ai_core_settings = {
                    "identity": full_config.get("bot_identity"),
                    "behavior": full_config.get("behavior_rules"),
                    "strict_rules": full_config.get("strict_observance"),
                    "examples": full_config.get("few_shot_examples"),
                    "prohibited": full_config.get("prohibited_answer_examples")
                }
                
                system_message = {
                    "role": "system", 
                    "content": f"You are Cyan. Strictly follow this JSON config:\n{json.dumps(ai_core_settings, ensure_ascii=False)}"
                }

                # 6. 会話履歴の管理
                channel_id = message.channel.id
                message_history[channel_id].append({"role": "user", "content": content})
                
                # 送信用メッセージ（システム設定 + 履歴）
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