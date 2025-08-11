#
# COURSE II BOT - BACKEND SCRIPT
#
# This script powers the backend for the @Courser08bot on Telegram,
# managing student enrollment and course access.
#
# Author: Gemini, your Coding Partner
#

import logging
import re
import time
import os
import requests
import base64
import json
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from flask import Flask, request

# --- CONFIGURATION ---
# Set up logging for debugging purposes
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Hardcoded tokens as requested
BOT_API_KEY = "8307246591:AAG944GFK4ObvOB2aqH-bP7HmrlE-um7Xr8"
GITHUB_TOKEN = "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"

# Admin IDs and group IDs from your project brief
ADMIN_ID = 7637175761
ADMIN_GROUP_ID = -1002808712674

# Bank details for payment
BANK_DETAILS = {
    "bank_name": "CBE",
    "account_holder": "Dawit Fromsa",
    "account_number": "1000649392157",
}

# --- COURSE DATA ---
COURSES = {
    "Python Programming": {"cost": "2,000 ETB", "duration": "4 weeks", "group_id": -1002884750079},
    "Web Development": {"cost": "3,500 ETB", "duration": "6 weeks", "group_id": -1002835447592},
    "Data Science Fundamentals": {"cost": "5,000 ETB", "duration": "8 weeks", "group_id": -1002668822675},
}

# --- CONVERSATION HANDLER STATES ---
(
    ENROLLMENT_START,
    GET_FULLNAME,
    GET_PHONE,
    CHOOSE_COURSE,
    UPLOAD_RECEIPT,
) = range(5)


# --- HELPERS ---
def generate_course_keyboard():
    """Generates an inline keyboard with available courses."""
    keyboard = []
    for course_name in COURSES:
        keyboard.append([InlineKeyboardButton(course_name, callback_data=f"course_{course_name}")])
    return InlineKeyboardMarkup(keyboard)

def update_github_repo(username, repo_name, file_path, new_content, token):
    """
    Updates a file in a GitHub repository with new content.
    Creates the file if it does not exist.
    """
    url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    sha = None
    existing_content = ""
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        file_data = response.json()
        sha = file_data['sha']
        existing_content = base64.b64decode(file_data['content']).decode('utf-8')
    elif response.status_code == 404:
        header = "user_id,fullname,phone_number,course_name\n"
        existing_content = header
    else:
        logger.error(f"Failed to check for file existence: {response.text}")
        return False
        
    updated_content = existing_content + new_content
    
    commit_message = "Add new student enrollment data"
    payload = {
        "message": commit_message,
        "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
        "sha": sha,
    }
    
    update_response = requests.put(url, headers=headers, data=json.dumps(payload))
    
    if update_response.status_code in [200, 201]:
        logger.info(f"Successfully updated {file_path} on GitHub.")
        return True
    else:
        logger.error(f"Failed to update {file_path} on GitHub: {update_response.text}")
        return False


# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Greets the user and initiates the enrollment process."""
    user = update.effective_user
    logger.info("User %s started the bot.", user.id)

    if "is_enrolled" in context.user_data and context.user_data["is_enrolled"]:
        await update.message.reply_text(
            f"Hello, {user.first_name}!\n\n"
            "You are already enrolled."
        )
        return ConversationHandler.END

    enroll_keyboard = [[KeyboardButton("Enroll Now")]]
    await update.message.reply_text(
        f"Hello, {user.first_name}!\n\n"
        "Welcome to our academy! We offer various courses to help you "
        "level up your skills. To get started, please enroll now."
    )
    return ENROLLMENT_START


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the current conversation."""
    await update.message.reply_text(
        "Operation canceled. You can restart the process at any time by using the /start command."
    )
    context.user_data.clear()
    return ConversationHandler.END


# --- ENROLLMENT PROCESS HANDLERS ---
async def enroll_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the 'Enroll Now' button press."""
    await update.message.reply_text("Great! What is your full name?")
    return GET_FULLNAME


async def get_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and stores the student's full name."""
    fullname = update.message.text
    context.user_data["fullname"] = fullname
    logger.info("User %s provided full name: %s", update.effective_user.id, fullname)
    await update.message.reply_text("Thank you. Now, please share your phone number.")
    return GET_PHONE


async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives, validates, and stores the student's phone number."""
    phone_number = update.message.text
    if not re.match(r'^(251|0)?[97]\d{8}$', phone_number):
        await update.message.reply_text(
            "Invalid phone number format. Please use a valid Ethiopian number (e.g., 2519... or 09...)."
        )
        return GET_PHONE
    
    context.user_data["phone_number"] = phone_number
    logger.info("User %s provided phone number: %s", update.effective_user.id, phone_number)
    
    await update.message.reply_text(
        "Thank you! Please select a course from the list below.",
        reply_markup=generate_course_keyboard()
    )
    return CHOOSE_COURSE


async def choose_course(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the course selection from an inline keyboard."""
    query = update.callback_query
    await query.answer()

    course_name = query.data.replace("course_", "")
    context.user_data["course_name"] = course_name
    course_info = COURSES.get(course_name)
    
    if course_info:
        await query.edit_message_text(
            f"You have selected *{course_name}*.\n\n"
            f"Details:\n"
            f"Cost: {course_info['cost']}\n"
            f"Duration: {course_info['duration']}\n\n"
            "To proceed with enrollment, please continue with the payment.",
            parse_mode="Markdown"
        )
        await query.message.reply_text(
            "Please make the payment to the following bank details and send us a picture of the receipt.\n\n"
            f"Bank Name: {BANK_DETAILS['bank_name']}\n"
            f"Account Holder: {BANK_DETAILS['account_holder']}\n"
            f"Account Number: {BANK_DETAILS['account_number']}\n"
        )
        await query.message.reply_text("Please upload the transaction receipt image now.")
        return UPLOAD_RECEIPT
    else:
        await query.edit_message_text("Sorry, that course is not available. Please try again.")
        return CHOOSE_COURSE


async def upload_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the payment receipt upload and forwards it to the admin."""
    photo_file_id = update.message.photo[-1].file_id
    user = update.effective_user
    
    context.user_data["receipt_file_id"] = photo_file_id

    student_data_row = (
        f"{user.id},"
        f"\"{context.user_data['fullname']}\","
        f"\"{context.user_data['phone_number']}\","
        f"\"{context.user_data['course_name']}\"\n"
    )

    GITHUB_USERNAME = "Drknyt199711"
    REPO_NAME = "Students"
    FILE_PATH = "student_enrollments.csv"
    
    update_github_repo(GITHUB_USERNAME, REPO_NAME, FILE_PATH, student_data_row, GITHUB_TOKEN)
    
    await update.message.reply_text(
        "Thank you! Your payment receipt has been received and is being checked by the system."
    )
    
    verification_text = (
        f"**New Enrollment Request!**\n\n"
        f"**User ID:** {user.id}\n"
        f"**Full Name:** {context.user_data['fullname']}\n"
        f"**Phone Number:** {context.user_data['phone_number']}\n"
        f"**Course:** {context.user_data['course_name']}\n"
    )
    
    keyboard = [[
        InlineKeyboardButton("Verify ✅", callback_data=f"verify_{user.id}"),
        InlineKeyboardButton("Deny ❌", callback_data=f"deny_{user.id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=ADMIN_GROUP_ID,
        photo=photo_file_id,
        caption=verification_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


# --- ADMIN CALLBACK HANDLERS ---
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin's 'Verify' or 'Deny' button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = int(data.split('_')[-1])
    action = data.split('_')[0]

    if action == "verify":
        course_name = context.user_data.get("course_name")
        course_info = COURSES.get(course_name)
        
        if not course_info:
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❌ Failed to find a course group for user {user_id}. "
                     "No invitation link was generated."
            )
            return

        COURSE_GROUP_ID = course_info["group_id"]
        
        try:
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=COURSE_GROUP_ID,
                member_limit=1,
                expire_date=int(time.time()) + 86400
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Your payment has been verified successfully! 🎉\n\n"
                     f"Here is your one-time invitation link to the course group for *{course_name}*. "
                     f"This link is valid for 24 hours and can only be used by you.\n\n"
                     f"**Invitation Link:** {invite_link.invite_link}",
                parse_mode="Markdown"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"✅ A one-time invitation link has been successfully sent to user {user_id} for the *{course_name}* course."
            )
            
            await query.edit_message_caption(caption=query.message.caption + "\n\n✅ Verified and link sent by admin.", reply_markup=None)
            
        except Exception as e:
            logger.error(f"Failed to create and send invite link for user {user_id}: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❌ Failed to create an invitation link for user {user_id}. "
                     f"Please check if the bot is an admin of the course group."
            )
        
    elif action == "deny":
        await context.bot.send_message(
            chat_id=user_id,
            text="Sorry, your payment could not be verified. "
                 "Please check your transaction and try again."
        )
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ Denied by admin.", reply_markup=None)


# --- WEBHOOK SETUP ---
# Flask app instance
app = Flask(__name__)

@app.route(f"/{BOT_API_KEY}", methods=["POST"])
async def webhook_handler():
    """Handle incoming Telegram updates via webhook."""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    return "ok"

# --- MAIN FUNCTION ---
# Build the bot application
application = ApplicationBuilder().token(BOT_API_KEY).build()

def main():
    """Start the bot by setting up handlers."""
    
    enrollment_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            ENROLLMENT_START: [MessageHandler(filters.Regex("^Enroll Now$"), enroll_now)],
            GET_FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fullname)],
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone_number)],
            CHOOSE_COURSE: [CallbackQueryHandler(choose_course)],
            UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, upload_receipt)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    
    application.add_handler(enrollment_handler)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(verify|deny)_"))


# We'll call main() in the WSGI file to configure the app
# The Flask app 'app' is what PythonAnywhere will run