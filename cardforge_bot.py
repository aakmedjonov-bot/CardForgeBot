#!/usr/bin/env python3
"""
CardForge — Telegram Business Card Bot
Deployment-ready for Render.com
TOKEN is read from environment variable — never hardcoded
"""

import io
import logging
import os
import textwrap

import qrcode
from PIL import Image, ImageDraw, ImageFont

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── TOKEN from environment variable ───────────────────────────
TOKEN = os.environ.get("TOKEN")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── CONVERSATION STATES ───────────────────────────────────────
(
    FIRST_NAME, LAST_NAME, JOB_TITLE, COMPANY, BIO,
    EMAIL, PHONE, WEBSITE, LOCATION, LINKEDIN, SOCIAL,
    DESIGN_THEME, CONFIRM,
) = range(13)

# ── THEMES ────────────────────────────────────────────────────
THEMES = {
    "futuristic": {
        "label": "⚡ Futuristic",
        "bg": (2, 13, 31),
        "fg": (0, 229, 255),
        "sub": (100, 200, 230),
        "info": (140, 200, 220),
        "border": (0, 180, 220),
    },
    "modern": {
        "label": "◈ Modern",
        "bg": (18, 18, 27),
        "fg": (250, 250, 250),
        "sub": (160, 160, 200),
        "info": (120, 120, 170),
        "border": (124, 58, 237),
    },
    "classic": {
        "label": "❧ Classic",
        "bg": (254, 252, 232),
        "fg": (120, 53, 15),
        "sub": (146, 64, 14),
        "info": (87, 83, 78),
        "border": (217, 119, 6),
    },
    "vintage": {
        "label": "⊕ Vintage",
        "bg": (253, 240, 220),
        "fg": (69, 26, 3),
        "sub": (120, 53, 15),
        "info": (87, 83, 78),
        "border": (146, 64, 14),
    },
}


def render_card(data: dict) -> io.BytesIO:
    t = THEMES[data.get("theme", "modern")]
    W, H = 700, 380
    img = Image.new("RGB", (W, H), t["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W - 1, H - 1], outline=t["border"], width=4)

    if data.get("theme") in ("classic", "vintage"):
        draw.rectangle([14, 14, W - 15, H - 15], outline=t["border"], width=1)

    if data.get("theme") in ("modern", "futuristic"):
        draw.rectangle([40, 55, 120, 60], fill=t["border"])

    def font(size, bold=False):
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        return ImageFont.load_default()

    fn_name  = font(38, bold=True)
    fn_title = font(22)
    fn_info  = font(18)
    fn_small = font(15)
    centered = data.get("theme") in ("classic", "vintage")

    def draw_text(text, y, fn, color):
        bbox = draw.textbbox((0, 0), text, font=fn)
        x = (W - (bbox[2] - bbox[0])) // 2 if centered else 40
        draw.text((x, y), text, fill=color, font=fn)

    draw_text(f"{data['first_name']} {data['last_name']}", 68, fn_name, t["fg"])

    if centered:
        draw.line([(W // 2 - 90, 120), (W // 2 + 90, 120)], fill=t["border"], width=1)

    title = data.get("job_title", "")
    if data.get("company"):
        title += f"  ·  {data['company']}"
    draw_text(title, 126, fn_title, t["sub"])

    y = 162
    if data.get("bio"):
        draw_text(textwrap.shorten(data["bio"], width=72, placeholder="…"), y, fn_small, t["info"])
        y += 28

    if data.get("theme") == "vintage":
        draw_text("✦ ─── ✦", y, fn_small, t["border"])

    lines = [f"  {data[k]}" for k in ("email","phone","website","location","linkedin","social") if data.get(k)]
    info_y = H - 26 - len(lines) * 24
    for line in lines:
        draw_text(line, info_y, fn_info, t["info"])
        info_y += 24

    if data.get("theme") == "futuristic":
        for pts in [[(W-45,4),(W-4,4)],[(W-4,4),(W-4,45)],[(4,H-45),(4,H-4)],[(4,H-4),(45,H-4)]]:
            draw.line(pts, fill=t["fg"], width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def make_vcard(data: dict) -> str:
    lines = [
        "BEGIN:VCARD", "VERSION:3.0",
        f"FN:{data['first_name']} {data['last_name']}",
        f"N:{data['last_name']};{data['first_name']};;;",
        f"TITLE:{data.get('job_title', '')}",
        f"ORG:{data.get('company', '')}",
        f"EMAIL:{data.get('email', '')}",
    ]
    if data.get("phone"):    lines.append(f"TEL:{data['phone']}")
    if data.get("website"):  lines.append(f"URL:{data['website']}")
    if data.get("location"): lines.append(f"ADR:;;{data['location']};;;;")
    if data.get("linkedin"): lines.append(f"X-SOCIALPROFILE;type=linkedin:{data['linkedin']}")
    if data.get("social"):   lines.append(f"X-SOCIALPROFILE;type=twitter:{data['social']}")
    if data.get("bio"):      lines.append(f"NOTE:{data['bio']}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def make_qr(content: str) -> io.BytesIO:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def build_summary(data: dict) -> str:
    lines = [
        "📋 *Preview of your card:*\n",
        f"👤 *{data['first_name']} {data['last_name']}*",
        f"💼 _{data.get('job_title', '')}_{' @ ' + data['company'] if data.get('company') else ''}",
    ]
    if data.get("bio"):      lines.append(f"💬 {textwrap.shorten(data['bio'], 60, placeholder='…')}")
    lines.append("")
    for emoji, key in [("✉️","email"),("📞","phone"),("🌐","website"),("📍","location"),("🔗","linkedin"),("🐦","social")]:
        if data.get(key): lines.append(f"{emoji}  {data[key]}")
    lines.append(f"\n🎨 Theme: *{THEMES[data.get('theme','modern')]['label']}*")
    return "\n".join(lines)


# ── HANDLERS ──────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        "✦ *Welcome to CardForge!*\n\nI'll create your digital business card + QR code.\n\nWhat is your *first name*?",
        parse_mode="Markdown",
    )
    return FIRST_NAME

async def get_first_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["first_name"] = update.message.text.strip()
    await update.message.reply_text("And your *last name*?", parse_mode="Markdown")
    return LAST_NAME

async def get_last_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["last_name"] = update.message.text.strip()
    await update.message.reply_text("What is your *job title*?", parse_mode="Markdown")
    return JOB_TITLE

async def get_job_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["job_title"] = update.message.text.strip()
    await update.message.reply_text("Company or brand name? _(or /skip)_", parse_mode="Markdown")
    return COMPANY

async def get_company(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["company"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("Short bio or tagline? _(or /skip)_", parse_mode="Markdown")
    return BIO

async def get_bio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["bio"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("Your *email address*? ✉️", parse_mode="Markdown")
    return EMAIL

async def get_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["email"] = update.message.text.strip()
    await update.message.reply_text("Phone number? 📞 _(or /skip)_", parse_mode="Markdown")
    return PHONE

async def get_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["phone"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("Website or portfolio? 🌐 _(or /skip)_", parse_mode="Markdown")
    return WEBSITE

async def get_website(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["website"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("City or location? 📍 _(or /skip)_", parse_mode="Markdown")
    return LOCATION

async def get_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["location"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("LinkedIn URL? 🔗 _(or /skip)_", parse_mode="Markdown")
    return LINKEDIN

async def get_linkedin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["linkedin"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("Twitter/Instagram handle? _(or /skip)_", parse_mode="Markdown")
    return SOCIAL

async def get_social(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["social"] = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    keyboard = [[InlineKeyboardButton(v["label"], callback_data=k)] for k, v in THEMES.items()]
    await update.message.reply_text(
        "🎨 Almost done! Choose your *card design theme*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return DESIGN_THEME

async def get_theme(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ctx.user_data["theme"] = query.data
    keyboard = [[
        InlineKeyboardButton("✅ Generate my card!", callback_data="confirm"),
        InlineKeyboardButton("🔄 Start over", callback_data="restart"),
    ]]
    await query.edit_message_text(
        build_summary(ctx.user_data),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CONFIRM

async def confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "restart":
        await query.edit_message_text("🔄 Restarted. Type /newcard to begin again.")
        return ConversationHandler.END

    await query.edit_message_text("⚙️ Generating your card, please wait…")
    data = ctx.user_data
    chat_id = update.effective_chat.id

    try:
        await ctx.bot.send_photo(
            chat_id=chat_id,
            photo=render_card(data),
            caption=(
                f"✦ *{data['first_name']} {data['last_name']}*\n"
                f"_{data.get('job_title', '')}_{' @ ' + data['company'] if data.get('company') else ''}\n\n"
                f"Theme: {THEMES[data['theme']]['label']}"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Card render error: {e}")
        await ctx.bot.send_message(chat_id=chat_id, text="⚠️ Card image could not be rendered.")

    vcf_str = make_vcard(data)

    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo=make_qr(vcf_str),
        caption="📲 *QR Code* — scan with any phone camera to save contact!",
        parse_mode="Markdown",
    )

    vcf_buf = io.BytesIO(vcf_str.encode("utf-8"))
    vcf_buf.name = f"{data['first_name']}_{data['last_name']}.vcf"
    await ctx.bot.send_document(
        chat_id=chat_id,
        document=vcf_buf,
        filename=vcf_buf.name,
        caption="📇 *vCard file* — tap to save to your phone contacts.",
        parse_mode="Markdown",
    )

    await ctx.bot.send_message(
        chat_id=chat_id,
        text="✅ *All done!* Your digital business card is ready.\n\nType /newcard to create another!",
        parse_mode="Markdown",
    )
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled. Type /newcard to start again.")
    return ConversationHandler.END


# ── MAIN ──────────────────────────────────────────────────────

def main() -> None:
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable not set! Add it in Render → Environment.")

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("newcard", start)],
        states={
            FIRST_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            LAST_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            JOB_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_job_title)],
            COMPANY:      [MessageHandler(filters.TEXT, get_company)],
            BIO:          [MessageHandler(filters.TEXT, get_bio)],
            EMAIL:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            PHONE:        [MessageHandler(filters.TEXT, get_phone)],
            WEBSITE:      [MessageHandler(filters.TEXT, get_website)],
            LOCATION:     [MessageHandler(filters.TEXT, get_location)],
            LINKEDIN:     [MessageHandler(filters.TEXT, get_linkedin)],
            SOCIAL:       [MessageHandler(filters.TEXT, get_social)],
            DESIGN_THEME: [CallbackQueryHandler(get_theme)],
            CONFIRM:      [CallbackQueryHandler(confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("CardForge Bot is running 24/7...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
