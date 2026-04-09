"""
InstaGrab Telegram Bot v2.0 — FIXED
=====================================
yt-dlp based Instagram downloader — No login required!
Works with: Posts, Reels, Videos, Carousel, Captions, Hashtags, Profiles
"""

import os
import re
import json
import asyncio
import tempfile
import subprocess
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
IG_COOKIES_FILE  = os.environ.get("IG_COOKIES_FILE", "")
MAX_FILE_SIZE_MB = 49

EMOJI = {
    "photo":"📷","video":"🎬","reel":"🎬","carousel":"🎠","profile":"👤",
    "caption":"📝","hashtag":"#️⃣","download":"⬇️","success":"✅",
    "error":"❌","loading":"⏳","fire":"🔥","heart":"❤️","stats":"📊","camera":"📸"
}

def is_instagram_url(text):
    return bool(re.search(r'(instagram\.com|instagr\.am)', text))

def extract_shortcode(url):
    m = re.search(r'instagram\.com/(?:p|reel|tv|reels)/([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else None

def extract_username_from_url(url):
    m = re.search(r'instagram\.com/([A-Za-z0-9._]+)/?(?:\?.*)?$', url)
    if m and m.group(1) not in ('p','reel','tv','reels','stories','explore','accounts'):
        return m.group(1)
    return None

def format_num(n):
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return "—"

def extract_hashtags(text):
    return re.findall(r'#\w+', text or "")

def clean_caption(text):
    return re.sub(r'#\w+', '', text or "").strip()

def file_size_mb(path):
    return path.stat().st_size / (1024 * 1024)

def run_ytdlp(url, out_dir, info_only=False):
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--write-info-json",
        "--merge-output-format", "mp4",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "--add-header", "Accept-Language:en-US,en;q=0.9",
        "--sleep-interval", "1",
        "--max-sleep-interval", "3",
    ]
    if IG_COOKIES_FILE and Path(IG_COOKIES_FILE).exists():
        cmd += ["--cookies", IG_COOKIES_FILE]
    if info_only:
        cmd += ["--skip-download", "-o", f"{out_dir}/%(id)s.%(ext)s"]
    else:
        cmd += ["--write-thumbnail", "-o", f"{out_dir}/%(playlist_index)s_%(id)s.%(ext)s"]
    cmd.append(url)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    info = {}
    for f in Path(out_dir).glob("*.info.json"):
        try:
            with open(f) as fh: info = json.load(fh)
            break
        except: pass
    if result.returncode != 0 and not info:
        raise RuntimeError(result.stderr[-600:] if result.stderr else "yt-dlp failed — no output")
    return info

async def cmd_start(update, context):
    user = update.effective_user
    text = (
        f"*🔥 InstaGrab Bot v2.0 — {user.first_name}!*\n\n"
        "Instagram ka koi bhi content download karo:\n\n"
        "📷 *Photos & Carousel*\n🎬 *Reels & Videos*\n📝 *Caption + Hashtags*\n👤 *Profile Info*\n\n"
        "Bas link paste karo 👇\n"
        "`https://instagram.com/p/ABC123/`\n"
        "`https://instagram.com/reel/XYZ/`\n\n"
        "/help — Help  |  /about — About"
    )
    kb = [[InlineKeyboardButton("📖 Help", callback_data="help"),
           InlineKeyboardButton("ℹ️ About", callback_data="about")]]
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(kb))

async def cmd_help(update, context):
    await update.message.reply_text(
        "*📖 Help*\n\n"
        "1️⃣ Instagram link paste karo\n"
        "2️⃣ Bot automatically detect karega — post, reel, ya profile\n"
        "3️⃣ Media + caption + hashtags sab milega!\n\n"
        "⚠️ Private accounts ka content nahi milta\n"
        "⚠️ 50MB se badi files Telegram mein nahi jaati",
        parse_mode=ParseMode.MARKDOWN)

async def cmd_about(update, context):
    await update.message.reply_text(
        "*🤖 InstaGrab Bot v2.0*\n\nBuilt with yt-dlp + python-telegram-bot\nFree to use!",
        parse_mode=ParseMode.MARKDOWN)

async def handle_message(update, context):
    text = (update.message.text or "").strip()
    if not is_instagram_url(text):
        await update.message.reply_text("❌ Instagram link nahi hai!")
        return
    shortcode = extract_shortcode(text)
    username  = extract_username_from_url(text) if not shortcode else None
    if shortcode:
        await handle_post(update, context, text)
    elif username:
        await handle_profile(update, context, username)
    else:
        await update.message.reply_text("❌ Link samajh nahi aaya. Sahi Instagram link bhejo.")

async def handle_post(update, context, url):
    msg = await update.message.reply_text("⏳ Downloading... thoda ruko!")
    await update.effective_chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            info = run_ytdlp(url, tmpdir)

            description = info.get("description") or info.get("caption") or info.get("title") or ""
            uploader_id = info.get("uploader_id") or info.get("channel_id") or "unknown"
            likes    = info.get("like_count", 0)
            comments = info.get("comment_count", 0)
            views    = info.get("view_count", 0)
            ts       = info.get("upload_date", "")
            post_url = info.get("webpage_url") or url

            hashtags  = extract_hashtags(description)
            clean_cap = clean_caption(description)
            date_str  = f"{ts[6:8]}/{ts[4:6]}/{ts[:4]}" if ts and len(ts)==8 else ""

            cap_msg = f"*📸 @{uploader_id}*"
            if date_str: cap_msg += f"  📅 {date_str}"
            cap_msg += f"\n❤️ {format_num(likes)}  💬 {format_num(comments)}"
            if views: cap_msg += f"  👁 {format_num(views)}"
            cap_msg += "\n\n"
            if clean_cap:
                cap_msg += f"📝 *Caption:*\n{clean_cap[:300]}{'…' if len(clean_cap)>300 else ''}\n\n"
            if hashtags:
                cap_msg += f"#️⃣ *Hashtags ({len(hashtags)}):*\n" + " ".join(hashtags[:15])

            sc = extract_shortcode(url) or "x"
            context.bot_data[f"cap_{sc}"] = description
            context.bot_data[f"ht_{sc}"]  = hashtags

            kb = []
            if description:
                kb.append([InlineKeyboardButton("📋 Full Caption", callback_data=f"cap_{sc}"),
                           InlineKeyboardButton("#️⃣ Hashtags", callback_data=f"ht_{sc}")])
            kb.append([InlineKeyboardButton("🔗 Original", url=post_url)])

            media_files = sorted([
                f for f in Path(tmpdir).iterdir()
                if f.suffix.lower() in ('.jpg','.jpeg','.png','.mp4','.webp')
                and '.info.' not in f.name
                and file_size_mb(f) <= MAX_FILE_SIZE_MB
            ])

            await msg.delete()

            if not media_files:
                await update.message.reply_text(
                    "❌ Media file nahi mili. Post private hai ya Instagram ne block kiya.\n\n" + cap_msg[:400],
                    parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                return

            if len(media_files) == 1:
                f = media_files[0]
                if f.suffix.lower() == '.mp4':
                    await update.effective_chat.send_action(ChatAction.UPLOAD_VIDEO)
                    await update.message.reply_video(video=open(f,'rb'), caption=cap_msg[:1024],
                                                     parse_mode=ParseMode.MARKDOWN,
                                                     reply_markup=InlineKeyboardMarkup(kb),
                                                     supports_streaming=True)
                else:
                    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
                    await update.message.reply_photo(photo=open(f,'rb'), caption=cap_msg[:1024],
                                                     parse_mode=ParseMode.MARKDOWN,
                                                     reply_markup=InlineKeyboardMarkup(kb))
            else:
                await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
                mg = []
                for i, f in enumerate(media_files[:10]):
                    c = cap_msg[:1024] if i==0 else None
                    p = ParseMode.MARKDOWN if i==0 else None
                    if f.suffix.lower() == '.mp4':
                        mg.append(InputMediaVideo(media=open(f,'rb'), caption=c, parse_mode=p))
                    else:
                        mg.append(InputMediaPhoto(media=open(f,'rb'), caption=c, parse_mode=p))
                await update.message.reply_media_group(media=mg)
                await update.message.reply_text(f"🎠 *Carousel:* {len(media_files)} items!",
                                                parse_mode=ParseMode.MARKDOWN,
                                                reply_markup=InlineKeyboardMarkup(kb))

    except subprocess.TimeoutExpired:
        await msg.edit_text("❌ Timeout! Instagram slow hai, dobara try karo.")
    except RuntimeError as e:
        err = str(e)
        if "private" in err.lower() or "login" in err.lower():
            tip = "🔒 Post *private* hai ya Instagram login maang raha hai."
        elif "429" in err or "rate" in err.lower():
            tip = "⏳ Instagram rate limit — 5 minute baad try karo."
        else:
            tip = f"yt-dlp error:\n`{err[-300:]}`"
        try: await msg.edit_text(f"❌ {tip}", parse_mode=ParseMode.MARKDOWN)
        except: pass
    except Exception as e:
        print(f"[handle_post] {e}")
        try: await msg.edit_text(f"❌ Error: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)
        except: pass

async def handle_profile(update, context, username):
    msg = await update.message.reply_text(f"⏳ @{username} ka profile fetch ho raha hai...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp","--no-warnings","--flat-playlist","--playlist-items","1",
                "--write-info-json","--skip-download",
                "--add-header","User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "-o", f"{tmpdir}/%(id)s.%(ext)s",
                f"https://www.instagram.com/{username}/"
            ]
            if IG_COOKIES_FILE and Path(IG_COOKIES_FILE).exists():
                cmd.insert(1,"--cookies"); cmd.insert(2, IG_COOKIES_FILE)
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            info = {}
            for f in Path(tmpdir).glob("*.json"):
                try:
                    with open(f) as fh: info = json.load(fh)
                    break
                except: pass

            name    = info.get("uploader") or username
            uid     = info.get("uploader_id") or username
            desc    = info.get("description") or "_(Bio available nahi)_"
            entries = info.get("n_entries") or "?"
            pic_url = info.get("thumbnail") or ""

            text = (f"*👤 @{uid}*\n_{name}_\n\n"
                    f"📝 *Bio:*\n{desc[:300]}\n\n"
                    f"📸 Posts visible: *{entries}*")
            kb = [[InlineKeyboardButton("🔗 Profile Dekhein", url=f"https://instagram.com/{username}/")]]
            await msg.delete()
            if pic_url:
                try:
                    await update.message.reply_photo(photo=pic_url, caption=text,
                                                     parse_mode=ParseMode.MARKDOWN,
                                                     reply_markup=InlineKeyboardMarkup(kb))
                    return
                except: pass
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                            reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        print(f"[handle_profile] {e}")
        try: await msg.edit_text(f"❌ Profile load nahi ho saka.\n`{str(e)[:200]}`",
                                  parse_mode=ParseMode.MARKDOWN)
        except: pass

async def handle_callback(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "help":
        await q.message.reply_text("Instagram link paste karo — post, reel, ya profile!")
    elif d == "about":
        await q.message.reply_text("*🤖 InstaGrab Bot v2.0* — yt-dlp powered", parse_mode=ParseMode.MARKDOWN)
    elif d.startswith("cap_"):
        cap = context.bot_data.get(d, "Caption nahi mili.")
        for i in range(0, len(cap), 4000):
            await q.message.reply_text(cap[i:i+4000])
    elif d.startswith("ht_"):
        ht = context.bot_data.get(d, [])
        if ht:
            await q.message.reply_text(
                f"*#️⃣ Hashtags ({len(ht)}):*\n\n" + "\n".join(f"`{h}`" for h in ht),
                parse_mode=ParseMode.MARKDOWN)
        else:
            await q.message.reply_text("Koi hashtag nahi mila.")

async def error_handler(update, context):
    print(f"[ERROR] {context.error}")

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN set nahi hai!")
        return
    print("🚀 InstaGrab Bot v2.0 (yt-dlp) starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)
    print("✅ Bot polling shuru!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
