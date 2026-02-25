# Cyan-kun本体の.pyファイル
# 手動起動の際はこのファイルを実行、systemdなどで自動起動する際は仮想環境のpythonからこのファイルを指定して起動してください。

import datetime
import discord
import os
import json
import traceback
import asyncio
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

client_ai = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# --- エラー防止のため client_discord の定義をイベント定義より前に移動 ---
intents = discord.Intents.default()
intents.message_content = True 
intents.guilds = True  # サーバー情報を取得するために必要
client_discord = discord.Client(intents=intents)

@client_discord.event
async def on_ready():
    print(f'--- 起動処理開始: {client_discord.user} ---')
    await asyncio.sleep(5) 
    
    try:
        full_config = load_full_config()
        server_settings = full_config.get("server_settings", {})
        
        target_guild_id = 1326883091662508043
        # get_guildで見つからない場合はfetchを試みる
        guild = client_discord.get_guild(target_guild_id)
        if not guild:
            try:
                guild = await client_discord.fetch_guild(target_guild_id)
            except:
                pass

        if guild:
            # config内のキーは文字列であることが多いため str() でラップ
            server_cfg = server_settings.get(str(guild.id))
            if server_cfg:
                log_channel_id = server_cfg.get("log_channel")
                # チャンネルも同様に fetch を試みる
                channel = client_discord.get_channel(int(log_channel_id))
                
                if channel:
                    embed = discord.Embed(
                        title="🟢 起動ログ",
                        description=f"{client_discord.user.name} が起動しました。",
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    embed.set_footer(text="Cyan-kun")
                    await channel.send(embed=embed)
                    print(f"Successfully sent log to {channel.name}")
                else:
                    print(f"Error: {log_channel_id} に送信できないよ～")
            else:
                print(f"Error: こんふぃぐの中に {target_guild_id} の設定が見つからないよ～")
        else:
            print(f"Error: サーバーID {target_guild_id} が見つからないよ～")
            
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
    server_settings = full_config.get("server_settings", {})
    # デフォルト設定がない場合やキーエラーを防ぐために安全に取得
    server_cfg = server_settings.get(server_id, server_settings.get("default", {}))
    allowed_channels = server_cfg.get("allowed_channels", [])
    keywords = server_cfg.get("keywords", ["シアン"])

    # 3. チャンネル制限のチェック
    # configのIDがintかstrか混在する可能性があるため、両方チェックする
    if allowed_channels:
        if message.channel.id not in allowed_channels and str(message.channel.id) not in allowed_channels:
            return

    # 履歴リセット機能
    if message.content.strip() == "?reset-log":
        message_history[message.channel.id].clear()
        await message.reply("会話履歴をリセットしたよ！")
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
                    "prohibited": full_config.get("Examples of prohibited answers")
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
                await message.reply("エラーが出てるみたい！\nあどみんさんに相談してみて！")

client_discord.run(DISCORD_TOKEN)