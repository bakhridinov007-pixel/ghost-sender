import asyncio
import logging
import random
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, PeerFloodError, UserPrivacyRestrictedError

logging.basicConfig(level=logging.INFO)

API_ID = 35042766             
API_HASH = "0e8d2aca6a97d11cafb9506cbaff64e2" 
BOT_TOKEN = "8804071188:AAHHRtDNRTLia6ikhhZNR9mgtTVEIEoHmsA" 
ADMIN_ID = 8314132173        

bot = TelegramClient('new_ghost_bot_session_v2', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

connected_profiles = []    
user_steps = {}            
user_data = {}             
profile_sent_count = {}    

campaign_data = {
    "usernames": [],
    "message_object": None 
}

async def show_admin_panel(chat_id):
    await bot.send_message(
        chat_id,
        f"👻 **Ghost Sender — Admin Panel**\n\n🟢 Faol profillar: **{len(connected_profiles)} ta**\n\nBoshqarish uchun pastdagi tugmalardan foydalaning:",
        buttons=[
            [Button.text("📋 Usernamelar yuklash"), Button.text("✍️ Reklama xabari yuborish")],
            [Button.text("🚀 Tarqatishni boshlash"), Button.text("👁️ Tekshirish")]
        ]
    )

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    sender_id = event.sender_id
    if sender_id == ADMIN_ID:
        user_steps[sender_id] = "MAIN"
        await show_admin_panel(event.chat_id)
    else:
        user_steps[sender_id] = "WAITING_AGREEMENT"
        await event.respond(
            "⚠️ **Foydalanish shartlari!**\n\nProfilingiz reklama tarqatishga ulanadi va spam block olishi xavfi bor. Shartlarga rozimisiz?",
            buttons=[
                [Button.text("✅ Roziman"), Button.text("❌ Rad etaman")]
            ]
        )

@bot.on(events.NewMessage)
async def handle_messages(event):
    sender_id = event.sender_id
    step = user_steps.get(sender_id)
    text = event.text.strip() if event.text else ""

    if text == "📋 Usernamelar yuklash" and sender_id == ADMIN_ID:
        user_steps[ADMIN_ID] = "INPUT_USERNAMES"
        await event.respond("📝 Usernamelar ro'yxatini har bir qatorda bittadan qilib yuboring:\n\n@user1\n@user2")
        return
    elif text == "✍️ Reklama xabari yuborish" and sender_id == ADMIN_ID:
        user_steps[ADMIN_ID] = "INPUT_TEXT"
        await event.respond("✍️ Reklama xabarini (matn, rasm yoki stiker) yuboring:")
        return
    elif text == "👁️ Tekshirish" and sender_id == ADMIN_ID:
        await event.respond(f"📊 **Hozirgi holat:**\n\n🟢 Faol profillar: {len(connected_profiles)} ta\n📋 Yuklangan usernames: {len(campaign_data['usernames'])} ta")
        if campaign_data["message_object"]:
            await event.respond(" Saqlangan reklama xabari:")
            await bot.send_message(ADMIN_ID, campaign_data["message_object"])
        return
    elif text == "🚀 Tarqatishni boshlash" and sender_id == ADMIN_ID:
        if not connected_profiles:
            await event.respond("❌ Tizimda faol profil yo'q! Avval profillarni ulang.")
            return
        if not campaign_data["usernames"] or not campaign_data["message_object"]:
            await event.respond("❌ Usernamelar yoki Reklama xabari kiritilmagan!")
            return
        await event.respond("🚀 Tarqatish boshlandi...")
        asyncio.create_task(run_campaign())
        return

    if sender_id == ADMIN_ID:
        if step == "INPUT_USERNAMES" and text and not text.startswith('/'):
            lines = text.split('\n')
            campaign_data["usernames"] = [u.strip() for u in lines if u.strip().startswith('@')]
            user_steps[ADMIN_ID] = "MAIN"
            await event.respond(f"✅ Ro'yxat olindi! Jami **{len(campaign_data['usernames'])} ta** username yuklandi.")
            await show_admin_panel(event.chat_id)
        elif step == "INPUT_TEXT" and not text.startswith('/'):
            campaign_data["message_object"] = event.message 
            user_steps[ADMIN_ID] = "MAIN"
            await event.respond("✅ Reklama xabari saqlandi!")
            await show_admin_panel(event.chat_id)
        return

    if text == "✅ Roziman" and step == "WAITING_AGREEMENT":
        user_steps[sender_id] = "WAITING_PHONE"
        await event.respond("📞 Telefon raqamingizni pastdagi tugma orqali yuboring:", buttons=[Button.text("📱 Raqamni ulash", request_phone=True)])
    elif text == "❌ Rad etaman" and step == "WAITING_AGREEMENT":
        await event.respond("❌ Rad etildi.", buttons=Button.clear())
    elif step == "WAITING_PHONE" and event.media and getattr(event.media, 'phone_number', None):
        phone = event.media.phone_number
        await event.respond("⏳ Kod so'ralmoqda, kuting...", buttons=Button.clear())
        session_name = f"profile_{phone.replace('+', '')}"
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        try:
            send_code_obj = await client.send_code_request(phone)
            user_data[sender_id] = {
                "phone": phone, "client": client, 
                "phone_code_hash": send_code_obj.phone_code_hash, "session_name": session_name
            }
            user_steps[sender_id] = "WAITING_CODE"
            await event.respond("🔢 Telegramdan kelgan **5 xonali kodni** kiriting:")
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}")
    elif step == "WAITING_CODE" and text:
        data = user_data.get(sender_id)
        if data:
            try:
                await data["client"].sign_in(data["phone"], text, phone_code_hash=data["phone_code_hash"])
                await finish_login(sender_id, data)
            except SessionPasswordNeededError:
                user_steps[sender_id] = "WAITING_2FA"
                await event.respond("🔐 Ikki bosqichli parolni (2FA) kiriting:")
            except Exception as e:
                await event.respond(f"❌ Xatolik: {e}")
    elif step == "WAITING_2FA" and text:
        data = user_data.get(sender_id)
        if data:
            try:
                await data["client"].sign_in(password=text)
                await finish_login(sender_id, data)
            except Exception as e:
                await event.respond(f"❌ Xatolik: {e}")

async def finish_login(sender_id, data):
    if data["session_name"] not in connected_profiles:
        connected_profiles.append(data["session_name"])
        profile_sent_count[data["session_name"]] = 0
    await data["client"].disconnect()
    user_steps[sender_id] = "DONE"
    await bot.send_message(sender_id, "🎉 Profilingiz muvaffaqiyatli qo'shildi!")
    await bot.send_message(ADMIN_ID, f"🔔 Yangi profil qo'shildi: **{data['phone']}**\nJami: {len(connected_profiles)} ta.")

async def run_campaign():
    profile_index = 0
    username_index = 0
    usernames = campaign_data["usernames"]
    msg_obj = campaign_data["message_object"]
    
    while username_index < len(usernames):
        if not connected_profiles:
            await bot.send_message(ADMIN_ID, "🛑 Barcha profillar limitga yetdi yoki spam bo'ldi.")
            break
            
        current_session = connected_profiles[profile_index % len(connected_profiles)]
        if profile_sent_count.get(current_session, 0) >= 20:
            connected_profiles.remove(current_session)
            if connected_profiles: 
                profile_index = profile_index % len(connected_profiles)
            continue
            
        target_user = usernames[username_index]
        client = TelegramClient(current_session, API_ID, API_HASH)
        await client.connect()
        
        try:
            await bot.send_message(ADMIN_ID, f"🔄 `{current_session}` -> {target_user} ga yubormoqda...")
            await client.send_message(target_user, msg_obj)
            profile_sent_count[current_session] += 1
            username_index += 1 
            await client.disconnect()
            await asyncio.sleep(random.randint(2, 5))
        except (PeerFloodError, UserPrivacyRestrictedError):
            await bot.send_message(ADMIN_ID, f"⚠️ `{current_session}` spamga tushdi! Keyingisiga o'tilmoqda...")
            await client.disconnect()
            if current_session in connected_profiles:
                connected_profiles.remove(current_session)
            if connected_profiles: 
                profile_index = profile_index % len(connected_profiles)
            await asyncio.sleep(5) 
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"❌ Xatolik ({target_user}): {e}")
            await client.disconnect()
            username_index += 1
            await asyncio.sleep(3)

    await bot.send_message(ADMIN_ID, "🏁 Reklama kampaniyasi yakunlandi!")

bot.run_until_disconnected()
