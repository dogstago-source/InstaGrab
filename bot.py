"""
InstaGrab Telegram Bot
======================
Instagram Posts, Reels, Videos, Carousel, Captions, Hashtags & Profile Downloader
Author: InstaGrab Bot
"""

import os
import re
import asyncio
import tempfile
import aiohttp
import instaloader
from pathlib import Path
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")          # Set in Railway env vars
INSTAGRAM_USERNAME = os.environ.get("IG_USERNAME", "") # Optional: for private posts
INSTAGRAM_PASSWORD = os.environ.get("IG_PASSWORD", "") # Optional: for private posts
MAX_FILE_SIZE_MB = 50  # Telegram bot limit

# ─── EMOJIS ──────────────────────────────────────────────────────────────────
EMOJI = {
    "photo": "📷", "video": "🎬", "reel": "🎬", "carousel": "🎠",
    "profile": "👤", "caption": "📝", "hashtag": "#️⃣",
    "download": "⬇️", "success": "✅", "error": "❌", "loading": "⏳",
    "fire": "🔥", "star": "⭐", "heart": "❤️", "link": "🔗",
    "info": "ℹ️", "stats": "📊", "camera": "📸"
}

# ─── INSTALOADER SETUP ───────────────────────────────────────────────────────
def create_loader():
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
    if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        try:
            L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        except Exception as e:
            print(f"Instagram login failed: {e}")
    return L

# ─── URL HELPERS ─────────────────────────────────────────────────────────────
def extract_shortcode(url: str) -> str | None:
    """Extract Instagram post shortcode from URL"""
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',
        r'instagram\.com/reels/([A-Za-z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_username(url: str) -> str | None:
    """Extract Instagram username from profile URL"""
    match = re.search(r'instagram\.com/([A-Za-z0-9._]+)/?$', url)
    if match and match.group(1) not in ['p', 'reel', 'tv', 'reels', 'stories']:
        return match.group(1)
    return None

def is_instagram_url(text: str) -> bool:
    return 'instagram.com' in text

def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def extract_hashtags(text: str) -> list[str]:
    return re.findall(r'#\w+', text)

def clean_caption(text: str) -> str:
    """Remove hashtags from caption for clean display"""
    return re.sub(r'#\w+', '', text).strip()

# ─── COMMAND HANDLERS ────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"*🔥 InstaGrab Bot mein Aapka Swagat Hai, {user.first_name}!*\n\n"
        f"Main Instagram ka koi bhi content download kar sakta hoon:\n\n"
        f"{EMOJI['photo']} *Photos* — Single ya Carousel\n"
        f"{EMOJI['video']} *Reels & Videos* — HD quality\n"
        f"{EMOJI['caption']} *Captions* — Poora text\n"
        f"{EMOJI['hashtag']} *Hashtags* — Alag se extract\n"
        f"{EMOJI['profile']} *Profile* — Bio, followers, posts\n\n"
        f"*Kaise Use Karein:*\n"
        f"Bas koi bhi Instagram link yahan paste karo! 👇\n\n"
        f"`https://www.instagram.com/p/...`\n"
        f"`https://www.instagram.com/reel/...`\n"
        f"`https://www.instagram.com/username/`\n\n"
        f"Commands:\n"
        f"/help — Help\n"
        f"/about — Bot ke baare mein"
    )
    keyboard = [[
        InlineKeyboardButton("📖 Help", callback_data="help"),
        InlineKeyboardButton("ℹ️ About", callback_data="about"),
    ]]
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*📖 Help & Instructions*\n\n"
        "*Post/Reel Download:*\n"
        "Instagram post ya reel ka link paste karo:\n"
        "`https://www.instagram.com/p/ABC123/`\n"
        "`https://www.instagram.com/reel/ABC123/`\n\n"
        "*Profile Info:*\n"
        "Username ya profile link bhejo:\n"
        "`https://www.instagram.com/username/`\n\n"
        "*Kya milega:*\n"
        "• Original quality photo/video\n"
        "• Caption (hashtags ke saath)\n"
        "• Hashtags alag se\n"
        "• Likes, comments, views count\n"
        "• Profile: bio, followers, following\n\n"
        "*⚠️ Note:* Private accounts download nahi ho sakte."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*🤖 InstaGrab Bot*\n\n"
        "Instagram content downloader bot.\n\n"
        "Built with: Python, python-telegram-bot, instaloader\n"
        "Hosted on: Railway.app\n\n"
        "Free to use — No limits!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─── MAIN MESSAGE HANDLER ────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not is_instagram_url(text):
        await update.message.reply_text(
            f"{EMOJI['error']} Yeh Instagram link nahi lagti!\n\n"
            "instagram.com ka link bhejo. /help dekho."
        )
        return

    # Detect type: profile or post
    shortcode = extract_shortcode(text)
    username = extract_username(text) if not shortcode else None

    if shortcode:
        await handle_post(update, context, shortcode)
    elif username:
        await handle_profile(update, context, username)
    else:
        await update.message.reply_text(
            f"{EMOJI['error']} Link samajh nahi aaya. Sahi Instagram post/reel/profile link bhejo."
        )

# ─── POST HANDLER ────────────────────────────────────────────────────────────
async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE, shortcode: str):
    msg = await update.message.reply_text(
        f"{EMOJI['loading']} Content download ho raha hai... thoda ruko!"
    )
    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)

    try:
        L = create_loader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        # ── Caption & Hashtags ──
        caption_text = post.caption or ""
        hashtags = extract_hashtags(caption_text)
        clean_cap = clean_caption(caption_text)

        # ── Stats ──
        stats = (
            f"{EMOJI['heart']} {format_number(post.likes)}  "
            f"💬 {format_number(post.comments)}  "
            f"👤 @{post.owner_username}"
        )
        if post.is_video and post.video_view_count:
            stats += f"  👁 {format_number(post.video_view_count)}"

        # ── Build caption message ──
        caption_msg = f"*{EMOJI['camera']} @{post.owner_username}*\n{stats}\n"
        if post.date_utc:
            caption_msg += f"📅 {post.date_utc.strftime('%d %b %Y')}\n"
        caption_msg += "\n"

        if clean_cap:
            cap_preview = clean_cap[:300] + ("..." if len(clean_cap) > 300 else "")
            caption_msg += f"*{EMOJI['caption']} Caption:*\n{cap_preview}\n\n"

        if hashtags:
            ht_str = " ".join(hashtags[:20])
            caption_msg += f"*{EMOJI['hashtag']} Hashtags ({len(hashtags)}):*\n`{ht_str}`\n"

        # ── Keyboard ──
        keyboard = []
        if caption_text:
            keyboard.append([
                InlineKeyboardButton("📋 Full Caption", callback_data=f"cap_{shortcode}"),
                InlineKeyboardButton("#️⃣ All Hashtags", callback_data=f"ht_{shortcode}"),
            ])
        keyboard.append([
            InlineKeyboardButton("🔗 Original Link", url=f"https://instagram.com/p/{shortcode}/"),
        ])

        # ── Download & Send Media ──
        with tempfile.TemporaryDirectory() as tmpdir:
            L2 = instaloader.Instaloader(
                dirname_pattern=tmpdir,
                filename_pattern="{shortcode}",
                download_pictures=True,
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                quiet=True,
            )
            L2.download_post(post, target=Path(tmpdir))

            # Collect downloaded files
            media_files = []
            for f in sorted(Path(tmpdir).iterdir()):
                if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.mp4', '.mov']:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    if size_mb <= MAX_FILE_SIZE_MB:
                        media_files.append(f)

            await msg.delete()

            if not media_files:
                await update.message.reply_text(
                    f"{EMOJI['error']} Media download nahi ho saka. Post private ho sakta hai.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            # Single media
            if len(media_files) == 1:
                f = media_files[0]
                if f.suffix.lower() == '.mp4':
                    await update.effective_chat.send_action(ChatAction.UPLOAD_VIDEO)
                    await update.message.reply_video(
                        video=open(f, 'rb'),
                        caption=caption_msg[:1024],
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        supports_streaming=True,
                    )
                else:
                    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
                    await update.message.reply_photo(
                        photo=open(f, 'rb'),
                        caption=caption_msg[:1024],
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
            else:
                # Carousel — send as media group (max 10)
                await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
                media_group = []
                for i, f in enumerate(media_files[:10]):
                    cap = caption_msg[:1024] if i == 0 else None
                    parse = ParseMode.MARKDOWN if i == 0 else None
                    if f.suffix.lower() == '.mp4':
                        media_group.append(InputMediaVideo(
                            media=open(f, 'rb'), caption=cap, parse_mode=parse
                        ))
                    else:
                        media_group.append(InputMediaPhoto(
                            media=open(f, 'rb'), caption=cap, parse_mode=parse
                        ))

                await update.message.reply_media_group(media=media_group)
                # Send keyboard separately for carousel
                await update.message.reply_text(
                    f"🎠 *Carousel:* {len(media_files)} items downloaded!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        # Store caption/hashtags for callback
        context.bot_data[f"cap_{shortcode}"] = caption_text
        context.bot_data[f"ht_{shortcode}"] = hashtags

    except instaloader.exceptions.PrivateProfileNotFollowedException:
        await msg.edit_text(
            f"{EMOJI['error']} *Private Account!*\n\nYeh account private hai. Sirf public posts download ho sakte hain.",
            parse_mode=ParseMode.MARKDOWN
        )
    except instaloader.exceptions.PostChangedException:
        await msg.edit_text(f"{EMOJI['error']} Post delete ho chuki hai ya available nahi.")
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit_text(
            f"{EMOJI['error']} Kuch gadbad ho gayi!\n\n`{str(e)[:200]}`\n\nDobara try karo.",
            parse_mode=ParseMode.MARKDOWN
        )

# ─── PROFILE HANDLER ─────────────────────────────────────────────────────────
async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    msg = await update.message.reply_text(
        f"{EMOJI['loading']} @{username} ka profile fetch ho raha hai..."
    )

    try:
        L = create_loader()
        profile = instaloader.Profile.from_username(L.context, username)

        bio = profile.biography or "_(Koi bio nahi)_"
        website = f"\n🌐 {profile.external_url}" if profile.external_url else ""

        text = (
            f"*{EMOJI['profile']} @{profile.username}*\n"
            f"_{profile.full_name}_\n\n"
            f"*{EMOJI['stats']} Stats:*\n"
            f"👥 Followers: *{format_number(profile.followers)}*\n"
            f"➡️ Following: *{format_number(profile.followees)}*\n"
            f"📸 Posts: *{format_number(profile.mediacount)}*\n"
            f"{'✅ Verified' if profile.is_verified else ''}\n\n"
            f"*📝 Bio:*\n{bio}{website}\n\n"
            f"{'🔒 Private Account' if profile.is_private else '🌐 Public Account'}"
        )

        keyboard = [[
            InlineKeyboardButton("🔗 Profile Dekhein", url=f"https://instagram.com/{username}/"),
        ]]
        if not profile.is_private:
            keyboard.append([
                InlineKeyboardButton("📸 Recent Posts Download", callback_data=f"recent_{username}"),
            ])

        # Profile picture
        try:
            pic_url = profile.profile_pic_url
            await msg.delete()
            await update.message.reply_photo(
                photo=pic_url,
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await msg.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except instaloader.exceptions.ProfileNotExistsException:
        await msg.edit_text(f"{EMOJI['error']} @{username} exist nahi karta ya banned ho gaya.")
    except Exception as e:
        print(f"Profile error: {e}")
        await msg.edit_text(f"{EMOJI['error']} Profile load nahi ho saka.\n`{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ─── CALLBACK HANDLERS ───────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help":
        await query.message.reply_text(
            "*📖 Help*\n\nInstagram link paste karo — post, reel, ya profile ka!",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "about":
        await query.message.reply_text("*🤖 InstaGrab Bot* — Free Instagram Downloader", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("cap_"):
        shortcode = data[4:]
        caption = context.bot_data.get(f"cap_{shortcode}", "Caption nahi mili.")
        # Send in chunks if too long
        for i in range(0, len(caption), 4000):
            await query.message.reply_text(caption[i:i+4000])

    elif data.startswith("ht_"):
        shortcode = data[3:]
        hashtags = context.bot_data.get(f"ht_{shortcode}", [])
        if hashtags:
            ht_text = "\n".join([f"`{h}`" for h in hashtags])
            await query.message.reply_text(
                f"*{EMOJI['hashtag']} Saare Hashtags ({len(hashtags)}):*\n\n{ht_text}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text("Koi hashtag nahi mila.")

    elif data.startswith("recent_"):
        username = data[7:]
        await query.message.reply_text(
            f"⚠️ Recent posts feature ke liye Instagram login credentials chahiye.\n"
            f"Bot admin se contact karo."
        )

# ─── ERROR HANDLER ───────────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Exception: {context.error}")

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN environment variable set nahi hai!")
        return

    print("🚀 InstaGrab Bot start ho raha hai...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    print("✅ Bot ready! Polling shuru...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
