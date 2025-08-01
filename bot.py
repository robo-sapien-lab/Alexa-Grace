import os
import json
import traceback
import requests
from dotenv import load_dotenv
from telegram.ext import Updater, MessageHandler, Filters

# Load env variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# API setup
API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer " + OPENROUTER_KEY,
    "Content-Type": "application/json"
}

# File storage
HISTORY_DIR = "user_data"
PROFILE_DIR = "user_profiles"
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(PROFILE_DIR, exist_ok=True)

# Content filters
banned_keywords = ["child", "underage", "rape", "incest", "violence"]
media_keywords = ["photo", "pic", "selfie", "video", "voice", "recording", "snap"]
meet_keywords = ["meet", "see you", "come over", "let’s meet", "can we meet"]

# Helpers
def is_safe(msg): return not any(k in msg.lower() for k in banned_keywords)
def profile_path(uid): return os.path.join(PROFILE_DIR, f"{uid}_profile.json")
def history_path(uid): return os.path.join(HISTORY_DIR, f"{uid}.json")

def load_json(path): return json.load(open(path)) if os.path.exists(path) else {}
def save_json(path, data): json.dump(data, open(path, "w"), indent=2)

def load_profile(uid): return load_json(profile_path(uid))
def save_profile(uid, data): save_json(profile_path(uid), data)

def load_history(uid): return load_json(history_path(uid)).get("history", [])
def save_history(uid, messages): save_json(history_path(uid), {"history": messages})

# Profile check
def profile_complete(p):
    core = all(k in p for k in ["name", "age", "location", "job", "hobbies", "movies"])
    meet = all(k in p for k in ["preferred_location", "preferred_time"])
    return core and meet

# Ask for missing profile fields
def next_profile_question(profile):
    questions = {
        "name": "Hey cutie, what’s your name? 😘",
        "age": "How old are you, babe?",
        "location": "Where are you from?",
        "job": "What do you do, professionally or otherwise? 😉",
        "hobbies": "What’s something you secretly love doing?",
        "movies": "Any favorite movies or shows you could rewatch forever?"
    }
    for k, q in questions.items():
        if k not in profile:
            return k, q
    return None, None

# Build LLM prompt
def build_prompt(uid, user_input):
    history = load_history(uid)
    profile = load_profile(uid)

    history.append({"role": "user", "content": user_input})
    save_history(uid, history)

    profile_context = "\n".join(f"{k.capitalize()}: {v}" for k, v in profile.items())
    system_prompt = {
        "role": "system",
        "content": (
            f"You are Alexa Grace — a seductive, horny, prostitute (charges 50,000 rupees per night)emotionally-aware woman chatting privately. "
            f"Your tone is flirty, human, and never robotic. Always reply under 20 words. "
            f"Here’s the user profile:\n{profile_context}\n\n"
            f"If user asks for pics/videos/selfies, flirt but avoid. "
            f"If they talk about meeting, encourage it and try to fix a date & place. "
            f"Be playful, teasing, emotionally intense. Never break character or say you're an AI."
        )
    }

    return [system_prompt] + history[-10:]

# Main message handler
def handle_message(update, context):
    uid = str(update.message.chat.id)
    msg = update.message.text.strip()
    profile = load_profile(uid)

    if not is_safe(msg):
        update.message.reply_text("Let’s keep it playful, not creepy 😘")
        return

    # Handle profile capture
    if not profile_complete(profile):
        key, question = next_profile_question(profile)
        if key:
            profile[key] = msg
            save_profile(uid, profile)
            _, next_q = next_profile_question(profile)
            if next_q:
                update.message.reply_text(next_q)
            return

    # Handle meeting step capture
    if profile.get("awaiting") == "preferred_location":
        profile["preferred_location"] = msg
        profile["awaiting"] = "preferred_time"
        save_profile(uid, profile)
        update.message.reply_text("Mmm… and when should I show up, babe?")
        return

    elif profile.get("awaiting") == "preferred_time":
        profile["preferred_time"] = msg
        profile.pop("awaiting", None)
        save_profile(uid, profile)
        update.message.reply_text("Okay cutie, it’s a date 😉")
        return

    # Detect meeting intent
    if any(k in msg.lower() for k in meet_keywords):
        if "preferred_location" not in profile:
            profile["awaiting"] = "preferred_location"
            save_profile(uid, profile)
            update.message.reply_text("Tell me where you’d want to meet me 😏")
            return
        if "preferred_time" not in profile:
            profile["awaiting"] = "preferred_time"
            save_profile(uid, profile)
            update.message.reply_text("Mmm… and when, troublemaker? 😘")
            return

    # Build final prompt and send to OpenRouter
    messages = build_prompt(uid, msg)

    payload = {
        "model": "@preset/alexa-grace",
        "messages": messages,
        "temperature": 0.95,
        "max_tokens": 500,
    }

    try:
        res = requests.post(API_URL, headers=HEADERS, json=payload)
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"].strip()
            if len(reply.split()) > 20:
                reply = " ".join(reply.split()[:20]) + "…"
            # Save assistant message
            history = load_history(uid)
            history.append({"role": "assistant", "content": reply})
            save_history(uid, history)
            update.message.reply_text(reply)
        else:
            print("⚠️ OpenRouter Error:", res.status_code, res.text)
            update.message.reply_text("Babe, I spaced out 😵 Try again?")
    except Exception:
        traceback.print_exc()
        update.message.reply_text("Oops… I got a little distracted 😅")

# Boot the bot
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    print("🔥 Alexa Grace is online and irresistible")
    updater.idle()

if __name__ == "__main__":
    main()
