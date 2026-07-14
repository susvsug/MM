import discord
from discord.ext import commands
import datetime
import json
import os

# إعداد الصلاحيات (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# تعيين بادئة الأوامر لتكون نقطة (.)
bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

# إعدادات المعرفات الثابتة (IDs)
ALLOWED_ROLE_ID = 1497438097128951899
LOG_CHANNEL_ID = 1509196870289981530

# تحديد مسار ملف حفظ البيانات (متوافق مع الـ Volumes في Railway)
DATA_DIR = "/app/data" if os.path.exists("/app") else "."
DATA_FILE = os.path.join(DATA_DIR, "warnings.json")

# تأكيد وجود المجلد قبل الحفظ
if DATA_DIR != "." and not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# --- وظائف إدارة البيانات (المخالفات) ---
def load_warnings():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_warnings(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_warning(user_id):
    data = load_warnings()
    str_user_id = str(user_id)
    if str_user_id not in data:
        data[str_user_id] = 0
    data[str_user_id] += 1
    save_warnings(data)
    return data[str_user_id]

# --- التحقق من الرتبة المسموح لها ---
def has_allowed_role():
    async def predicate(ctx):
        role = ctx.guild.get_role(ALLOWED_ROLE_ID)
        if role in ctx.author.roles or ctx.author.guild_permissions.administrator:
            return True
        return False
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"🟢 تم تشغيل البوت بنجاح بواسطة: {bot.user}")


# --- 1. أمر المساعدة ---
@bot.command(name="مساعده")
async def help_command(ctx):
    embed = discord.Embed(
        title="قائمة أوامر البوت المتاحة",
        description="إليك الأوامر المتوفرة وشرح مختصر لكل منها:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="`.مساعده`", 
        value="عرض قائمة الأوامر هذه مع الشرح.", 
        inline=False
    )
    embed.add_field(
        name="`.لهنت [السبب]`", 
        value="يُسخدم كـ (Reply) على رسالة المخالف. يحذف الرسالة، يسجل مخالفة، ويعطي Timeout تصاعدي (15 د، 30 د، 1 ساعة) لكل 3 مخالفات.", 
        inline=False
    )
    embed.add_field(
        name="`.اوت`", 
        value="يُستخدم كـ (Reply) على رسالة المخالف لإعطائه Timeout مباشرة لمدة ساعة كاملة وكتابة Log.", 
        inline=False
    )
    embed.add_field(
        name="`.تكت`", 
        value="تسجيل إنجاز التذكرة وإرسال السجل إلى روم السجلات (دون حذف الروم).", 
        inline=False
    )
    avatar_url = ctx.author.avatar.url if ctx.author.avatar else None
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name}", icon_url=avatar_url)
    await ctx.send(embed=embed)


# --- 2. أمر .لهنت ---
@bot.command(name="لهنت")
@has_allowed_role()
async def lahnt(ctx, *, reason: str = None):
    if not ctx.message.reference:
        await ctx.reply("❌ يجب استخدام هذا الأمر كرد (Reply) على رسالة العضو المخالف!")
        return

    if not reason:
        await ctx.reply("❌ يجب كتابة سبب المخالفة بعد الأمر. مثال: `.لهنت صورة مخالفة`")
        return

    try:
        replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except discord.NotFound:
        await ctx.reply("❌ لم يتم العثور على الرسالة الأصلية!")
        return

    offender = replied_message.author

    if offender.bot:
        await ctx.reply("❌ لا يمكنك تطبيق هذا الأمر على البوتات.")
        return

    try:
        await replied_message.delete()
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    warnings_count = add_warning(offender.id)

    timeout_duration = None
    if warnings_count % 9 == 3:
        timeout_duration = datetime.timedelta(minutes=15)
    elif warnings_count % 9 == 6:
        timeout_duration = datetime.timedelta(minutes=30)
    elif warnings_count % 9 == 0 and warnings_count > 0:
        timeout_duration = datetime.timedelta(hours=1)

    timeout_applied = False
    if timeout_duration:
        try:
            await offender.timeout(timeout_duration, reason=f"تراكم المخالفات: المخالفة رقم {warnings_count}")
            timeout_applied = True
        except discord.Forbidden:
            pass

    log_embed = discord.Embed(color=discord.Color.from_rgb(255, 255, 255))
    log_embed.add_field(name="العضو المخالف", value=f"{offender.mention} ({offender.id})", inline=False)
    log_embed.add_field(name="الإداري المسؤول", value=ctx.author.mention, inline=False)
    log_embed.add_field(name="سبب المخالفة", value=reason, inline=False)
    log_embed.add_field(name="عدد المخالفات الحالي", value=f"`{warnings_count}` مخالفة", inline=False)

    if timeout_applied:
        duration_str = "15 دقيقة" if timeout_duration.seconds == 900 else "30 دقيقة" if timeout_duration.seconds == 1800 else "ساعة واحدة"
        log_embed.add_field(name="العقوبة المطبقة", value=f"Timeout لمدة {duration_str} بسبب الوصول للمخالفة رقم {warnings_count}", inline=False)

    if replied_message.content:
        log_embed.add_field(name="محتوى الرسالة المحذوفة", value=replied_message.content, inline=False)
    
    if replied_message.attachments:
        attachment = replied_message.attachments[0]
        if attachment.content_type and attachment.content_type.startswith("image/"):
            log_embed.set_image(url=attachment.url)
        else:
            log_embed.add_field(name="مرفقات محذوفة (ليست صورة)", value=attachment.url, inline=False)

    if replied_message.stickers:
        sticker = replied_message.stickers[0]
        log_embed.add_field(name="الملصق المستخدم (Sticker)", value=f"الاسم: {sticker.name} (ID: {sticker.id})", inline=False)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=log_embed)


# --- 3. أمر .اوت ---
@bot.command(name="اوت")
@has_allowed_role()
async def out(ctx):
    if not ctx.message.reference:
        await ctx.reply("❌ يجب استخدام هذا الأمر كرد (Reply) على رسالة العضو!")
        return

    try:
        replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except discord.NotFound:
        await ctx.reply("❌ لم يتم العثور على الرسالة الأصلية!")
        return

    offender = replied_message.author

    if offender.bot:
        await ctx.reply("❌ لا يمكنك إعطاء تايم أوت للبوتات.")
        return

    duration = datetime.timedelta(hours=1)
    try:
        await offender.timeout(duration, reason="استخدام أمر .اوت بواسطة الإداري")
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.reply("❌ لا أملك الصلاحيات الكافية لتطبيق Timeout على هذا العضو.")
        return

    log_embed = discord.Embed(color=discord.Color.from_rgb(255, 255, 255))
    log_embed.add_field(name="العضو المعاقب", value=f"{offender.mention} ({offender.id})", inline=False)
    log_embed.add_field(name="الإداري المسؤول", value=ctx.author.mention, inline=False)
    log_embed.add_field(name="مدة التايم أوت", value="ساعة كاملة (1 Hour)", inline=False)
    log_embed.add_field(name="وقت التنفيذ", value=f"<t:{int(datetime.datetime.now().timestamp())}:F>", inline=False)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=log_embed)


# --- 4. أمر .تكت (تم إلغاء حذف الروم تلقائياً) ---
@bot.command(name="تكت")
@has_allowed_role()
async def ticket_close(ctx):
    channel_name = ctx.channel.name

    log_embed = discord.Embed(color=discord.Color.from_rgb(255, 255, 255))
    log_embed.add_field(name="الإداري المسؤول", value=ctx.author.mention, inline=False)
    log_embed.add_field(name="اسم التذكرة", value=f"`# {channel_name}`", inline=False)
    log_embed.add_field(name="الحالة", value="✅ تم تسجيل إنجاز التذكرة وإرسال السجل بنجاح (الروم محفوظ ولم يتم حذفه).", inline=False)
    log_embed.set_footer(text=f"التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=log_embed)

    # يرسل تأكيد للإداري داخل الروم نفسه بأنه تم الحفظ
    await ctx.send("✅ **تم تسجيل إنجاز التذكرة وإرسال التقرير لغرفة السجلات بنجاح!**")


# قراءة التوكن بأمان من متغيرات البيئة الخاصة بـ Railway
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

if BOT_TOKEN:
    bot.run(BOT_TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على متغير البيئة DISCORD_TOKEN. يرجى إضافته في إعدادات Railway!")
