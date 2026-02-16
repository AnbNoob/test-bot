import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import json
import os
from threading import Thread
from datetime import datetime

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask app for receiving webhooks
app = Flask(__name__)

# Environment variables (will be set in Railway)
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to send alerts to channel: {DISCORD_CHANNEL_ID}')

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive alerts from TradingView"""
    
    # Verify secret
    secret = request.headers.get('X-Webhook-Secret')
    if secret != WEBHOOK_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        print(f"Received webhook: {json.dumps(data, indent=2)}")
        
        # Send to Discord in a non-blocking way
        bot.loop.create_task(send_alert(data))
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

async def send_alert(data):
    """Format and send alert to Discord"""
    
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f"Channel {DISCORD_CHANNEL_ID} not found!")
        return
    
    alert_type = data.get('type', 'unknown')
    
    if alert_type == 'entry':
        await send_entry_alert(channel, data)
    elif alert_type == 'tp1':
        await send_tp1_alert(channel, data)
    elif alert_type == 'tp2':
        await send_tp2_alert(channel, data)
    elif alert_type == 'sl':
        await send_sl_alert(channel, data)
    elif alert_type == 'eod':
        await send_eod_alert(channel, data)
    else:
        # Generic alert
        await channel.send(f"📢 Alert: {json.dumps(data, indent=2)}")

async def send_entry_alert(channel, data):
    """Send formatted entry alert"""
    
    direction = data.get('direction', 'UNKNOWN')
    entry = float(data.get('entry', 0))
    stop = float(data.get('stop', 0))
    tp1 = float(data.get('tp1', 0))
    tp2 = float(data.get('tp2', 0))
    mode = data.get('mode', '')
    time_str = data.get('time', '')
    day = data.get('day', '')
    timeframe = data.get('timeframe', 'Unknown')
    
    # Calculate distances
    risk = abs(entry - stop)
    tp1_dist = abs(tp1 - entry)
    tp2_dist = abs(tp2 - entry)
    
    # Color based on direction
    color = 0x00FF00 if direction == 'LONG' else 0xFF0000
    emoji = '🟢' if direction == 'LONG' else '🔴'
    
    embed = discord.Embed(
        title=f"{emoji} {direction} ENTRY - {mode} [{timeframe}]",
        color=color,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="📍 Entry", value=f"**{entry:,.2f}**", inline=True)
    embed.add_field(name="🛑 Stop Loss", value=f"{stop:,.2f}\n({risk:+.2f} pts)", inline=True)
    embed.add_field(name="📊 Risk", value=f"**{risk:.2f}** pts", inline=True)
    
    embed.add_field(name="🎯 TP1 (1.3R)", value=f"{tp1:,.2f}\n({tp1_dist:+.2f} pts)", inline=True)
    embed.add_field(name="🎯 TP2 (2.0R)", value=f"{tp2:,.2f}\n({tp2_dist:+.2f} pts)", inline=True)
    embed.add_field(name="⏰ Time", value=f"{time_str}\n{day}", inline=True)
    
    # Add midnight open info if present
    if 'mo_bias' in data:
        embed.add_field(name="🌙 Midnight Open", value=data['mo_bias'], inline=False)
    
    embed.set_footer(text=f"ICT Pro v10 Optimized | {timeframe} Chart | Trade at your own risk")
    
    await channel.send(embed=embed)

async def send_tp1_alert(channel, data):
    """Send TP1 hit notification"""
    
    direction = data.get('direction', 'UNKNOWN')
    price = float(data.get('price', 0))
    profit = float(data.get('profit', 0))
    
    color = 0x00FF00 if direction == 'LONG' else 0xFF0000
    
    embed = discord.Embed(
        title=f"✅ TP1 HIT - 50% Closed",
        description=f"**{direction}** position moved to breakeven",
        color=color,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="💰 TP1 Price", value=f"{price:,.2f}", inline=True)
    embed.add_field(name="📈 Profit", value=f"+{profit:.2f} pts", inline=True)
    embed.add_field(name="🔒 Status", value="Breakeven Active", inline=True)
    
    embed.set_footer(text="Remaining 50% running to TP2")
    
    await channel.send(embed=embed)

async def send_tp2_alert(channel, data):
    """Send TP2 hit notification"""
    
    direction = data.get('direction', 'UNKNOWN')
    price = float(data.get('price', 0))
    profit = float(data.get('profit', 0))
    
    embed = discord.Embed(
        title=f"🎯 TP2 HIT - Trade Complete",
        description=f"**{direction}** position fully closed",
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="💰 TP2 Price", value=f"{price:,.2f}", inline=True)
    embed.add_field(name="📈 Total Profit", value=f"+{profit:.2f} pts", inline=True)
    embed.add_field(name="✅ Result", value="WINNER", inline=True)
    
    await channel.send(embed=embed)

async def send_sl_alert(channel, data):
    """Send stop loss hit notification"""
    
    direction = data.get('direction', 'UNKNOWN')
    price = float(data.get('price', 0))
    loss = float(data.get('loss', 0))
    
    embed = discord.Embed(
        title=f"🛑 STOP LOSS HIT",
        description=f"**{direction}** position closed at stop",
        color=0xFF0000,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="💰 Exit Price", value=f"{price:,.2f}", inline=True)
    embed.add_field(name="📉 Loss", value=f"{loss:.2f} pts", inline=True)
    embed.add_field(name="❌ Result", value="STOPPED OUT", inline=True)
    
    await channel.send(embed=embed)

async def send_eod_alert(channel, data):
    """Send end of day close notification"""
    
    direction = data.get('direction', 'UNKNOWN')
    price = float(data.get('price', 0))
    pnl = float(data.get('pnl', 0))
    
    color = 0x00FF00 if pnl > 0 else 0xFF0000
    result = "PROFIT" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
    
    embed = discord.Embed(
        title=f"🌅 EOD CLOSE (3:00 PM)",
        description=f"**{direction}** position closed at end of day",
        color=color,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="💰 Exit Price", value=f"{price:,.2f}", inline=True)
    embed.add_field(name="📊 P&L", value=f"{pnl:+.2f} pts", inline=True)
    embed.add_field(name="📋 Result", value=result, inline=True)
    
    await channel.send(embed=embed)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'bot_ready': bot.is_ready()}), 200

def run_flask():
    """Run Flask server"""
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def run_bot():
    """Run Discord bot"""
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run Discord bot in main thread
    run_bot()
