# InstaGrab Bot - Railway Deployment

## Setup
1. Create Railway account
2. Create new project
3. Connect GitHub repository
4. Set environment variables:
   - BOT_TOKEN: Your Telegram bot token
   - IG_COOKIES_FILE: (Optional) Instagram cookies file

## Deploy
1. Push to GitHub
2. Railway will auto-deploy
3. Check logs for status

## Testing
1. Send Instagram link to bot
2. Verify download works
3. Check error handling

## Environment Variables
```
BOT_TOKEN=your_telegram_bot_token_here
IG_COOKIES_FILE=optional_cookies_file_path
```