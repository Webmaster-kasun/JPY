OANDA_API_KEY=your_oanda_api_key_here
OANDA_ACCOUNT_ID=your_account_id_here

# OANDA_ENV controls which OANDA server is used:
#   practice = demo account (fxpractice.oanda.com)
#   live     = real money account (fxtrade.oanda.com)
OANDA_ENV=practice

TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# BOT_MODE controls order behaviour:
#   paper = connect to OANDA (shows real demo balance) but DO NOT place orders
#   demo  = connect to OANDA practice account and place real demo orders
#   live  = connect to OANDA live account and place real orders
BOT_MODE=paper
