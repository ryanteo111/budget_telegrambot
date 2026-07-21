import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from datetime import datetime
from telegram import ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler
from functools import wraps
import json
import os
from pathlib import Path

from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=script_dir / ".env")

allowed_user_ids = os.getenv("ALLOWED_USER_IDS")
ALLOWED_USER_IDS = [int(user_id) for user_id in allowed_user_ids.split(",") if user_id.strip()]

def check_authorized_user(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.message and update.message.from_user:
            user_id = update.message.from_user.id
            if user_id not in ALLOWED_USER_IDS:
                return
        else:
            user_id = update.message
            return
    
        return await func(update, context, *args, **kwargs)
    
    return wrapper

NAME, CATEGORY, AMOUNT, ADD_AMOUNT, CUSTOM_CATEGORY, DELETE_USER, DELETE_DETAILS, DELETE_CONFIRM,CARD_SELECTION  = range(9)

# Google Sheets setup
SHEET_ID = os.getenv("SHEET_ID", "1ZGLkL20tZUYazKMMZNKsb7NyujxXkEdwUHcJ6_JOcBg")
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_file = os.getenv("GOOGLE_CREDS_FILE", str(script_dir / "suss-435307-621fd9e04900.json"))

if creds_json:
    parsed_creds = json.loads(creds_json)
    if isinstance(parsed_creds, str):
        parsed_creds = json.loads(parsed_creds)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(parsed_creds, SCOPE)
else:
    credentials = ServiceAccountCredentials.from_json_keyfile_name(creds_file, SCOPE)

client = gspread.authorize(credentials)
spreadsheet = client.open_by_key(SHEET_ID)

# /start command handler
@check_authorized_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
    "💰 Welcome to the Budget Bot! 💰\n\n"
    "✨ Use the commands below to manage your budget:\n\n"
    "📝 /input – Log your spendings\n"
    "💵 /addamount – Top up the joint account balance\n"
    "📊 /view – View spendings for the month\n"
    "📅 /monthlyview – View monthly spendings for a selected month\n"
    "❌ /cancel – Cancel and return to the main menu\n"
    "🗑️ /delete – Remove specific spendings\n\n"
    "🚀 Let's keep track of your finances!",
    reply_markup=ReplyKeyboardRemove())

## /ADD AMOUNT HANDLER
@check_authorized_user
async def add_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the amount.")
        return ADD_AMOUNT

    sheet = spreadsheet.worksheet("Ryloe")

    records = sheet.get_all_records()

    latest_record = records[-1] if records else None

    current_month = datetime.now().strftime("%m-%Y")

    if latest_record:
        try:
            balance = float(str(latest_record["Total"]).strip())  # Make sure it's a float
        except ValueError:
            balance = 0.0 

    balance += amount

    date = update.message.date.strftime("%m-%d-%Y")

    # Write only manual columns (A:E) without touching Month/Total formulas
    next_row = len(sheet.col_values(1)) + 1
    sheet.update(f"A{next_row}:E{next_row}", [["Add", amount, "", date, ""]], value_input_option='USER_ENTERED')

    await update.message.reply_text(
        f"💰 You've successfully added ${amount:.2f} to Ryloe's balance.\n\n"
        f"🔄 Updated Balance: ${balance:.2f}"
)
    await update.message.reply_text(
        "💰 Welcome to the Budget Bot! 💰\n\n"
        "✨ Use the commands below to manage your budget:\n\n"
        "📝 /input – Log your spendings\n"
        "💵 /addamount – Top up the joint account balance\n"
        "📊 /view – View spendings for the month\n"
        "📅 /monthlyview – View monthly spendings for a selected month\n"
        "❌ /cancel – Cancel and return to the main menu\n"
        "🗑️ /delete – Remove specific spendings\n\n"
        "🚀 Let's keep track of your finances!",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

@check_authorized_user
async def add_amount_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("💵 How much would you like to add to Ryloe's balance?")
    return ADD_AMOUNT

CATEGORIES = [
    "🍽️ Food", "🚗 Transport", "🛍️ Shopping", "🛒 Groceries",
    "💰 Misc", "👶 Liam", "✈️ Travels", "🏥 Health",
    "📚 Education", "💡 Utilities", "🛡️ Insurance", "🔖 Others"
]
CUSTOM_CATEGORY = 4
DATE, CATEGORY, AMOUNT = range(3)

@check_authorized_user
async def input_spending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply_keyboard = [["💳 Ryan", "💳 Chloe", "👫 Ryloe"]]
    await update.message.reply_text(
        "Who is this spending for? 🤔\n",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return NAME

@check_authorized_user
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Save the user's selection in context
    context.user_data["name"] = update.message.text

    # Check if the user selected "Ryloe"
    if update.message.text == "👫 Ryloe":
        user_id = update.message.from_user.id
        # Check if the user is the special user (ID: 188171287)
        if user_id == 188171287:
            # If the user is 188171287, proceed as normal
            await show_category_page(update, context, page=0)
        else:
            # Otherwise, ask whose card (Ryan or Chloe) the spending should be charged to
            reply_keyboard = [["💳 Ryan", "💳 Chloe"]]
            await update.message.reply_text(
                "Who should the spending be charged to? 🤔\n",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
            )
            return CARD_SELECTION
    else:
        # Proceed with the category selection if it's not "Ryloe"
        await show_category_page(update, context, page=0)
    return CATEGORY

@check_authorized_user
async def card_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_card = update.message.text.strip()
    context.user_data["selected_card"] = selected_card

    await show_category_page(update, context, page=0)
    return CATEGORY

async def show_category_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    buttons = [[InlineKeyboardButton(f"{category}", callback_data=f"category_{category}")] for category in CATEGORIES]
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "📋 Which category does this spending fall under?\n\nChoose a category below:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        await update.message.reply_text(
            "📋 Which category does this spending fall under?\n\nSelect a category from the options below:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    context.user_data["current_page"] = page

async def category_handler_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("page_"):
        page = int(query.data.split("_")[1])
        await show_category_page(update, context, page=page)
        return CATEGORY

    elif query.data.startswith("category_"):
        category = query.data.split("_")[1]

        if category == "Others":
            await query.edit_message_text("✏️ Please enter the name of your custom category:")
            return CUSTOM_CATEGORY

        else:
            context.user_data["category"] = category
            await query.edit_message_text(f"✅ Selected category: {category}")
            await query.message.reply_text(
                "💰 *How much did you spend?*\n\n"
                "📌 Example: `188.80 Hai Di Lao` or `188.80`")
            return AMOUNT
    return CATEGORY 
    
@check_authorized_user
async def custom_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Capture and save the custom category
    custom_category = update.message.text.strip()
    context.user_data["category"] = custom_category  # Save custom category in user_data

    # Move to the next step to get the amount
    await update.message.reply_text(f"✅ Selected custom category: {custom_category}")
    await update.message.reply_text(
                "💰 *How much did you spend?*\n\n"
                "📌 Example: `188.80 Hai Di Lao` or `188.80`")
    return AMOUNT

@check_authorized_user
async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = context.user_data["name"]
    category = context.user_data["category"]
    selected_card = context.user_data.get("selected_card", "")
    user_input = update.message.text.strip()
    try:
        parts = user_input.split(" ", 1)  # Split at the first space
        amount = float(parts[0])         # First part is the amount
        comments = parts[1] if len(parts) > 1 else ""  # Second part is the comments if available
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter in the format: '<amount> <remarks>' or '<amount>'.")
        return AMOUNT

    date = update.message.date.strftime("%m-%d-%Y")
    user_id = update.message.from_user.id

    if name == "💳 Ryan":
        user_sheet = spreadsheet.worksheet("Ryan")
        user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
    elif name == "💳 Chloe":
        user_sheet = spreadsheet.worksheet("Chloe")
        user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
    else:
        user_sheet = spreadsheet.worksheet("Ryloe")
        if user_id == 188171287:
            user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
        else:
            if selected_card == "💳 Ryan":
                user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
            elif selected_card == "💳 Chloe":
                user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
    if name == "💳 Ryan":
        user_sheet = spreadsheet.worksheet("Ryan")
        user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
        # Use Column A to find next data row, and only write manual columns
        next_row = len(user_sheet.col_values(1)) + 1
        user_sheet.update(f"A{next_row}:D{next_row}", [[category, amount, comments, date]], value_input_option='USER_ENTERED')
        
        next_row2 = len(user_sheet2.col_values(1)) + 1
        user_sheet2.update(f"A{next_row2}:D{next_row2}", [[category, amount, comments, date]], value_input_option='USER_ENTERED')
    elif name == "💳 Chloe":
        user_sheet = spreadsheet.worksheet("Chloe")
        user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
        # Use Column A to find next data row, and only write manual columns
        next_row = len(user_sheet.col_values(1)) + 1
        user_sheet.update(f"A{next_row}:D{next_row}", [[category, amount, comments, date]], value_input_option='USER_ENTERED')
        
        next_row2 = len(user_sheet2.col_values(1)) + 1
        user_sheet2.update(f"A{next_row2}:D{next_row2}", [[category, amount, comments, date]], value_input_option='USER_ENTERED')
    else:
        user_sheet = spreadsheet.worksheet("Ryloe")
        if user_id == 188171287:
            user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
        else:
            if selected_card == "💳 Ryan":
                user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
            elif selected_card == "💳 Chloe":
                user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
        
        # Use Column A to find next data row, and only write manual columns
        next_row = len(user_sheet.col_values(1)) + 1
        if user_id == 188171287:
            user_sheet.update(f"A{next_row}:E{next_row}", [[category, amount, comments, date, "Chloe"]], value_input_option='USER_ENTERED')
        else:
            if selected_card == "💳 Ryan":
                user_sheet.update(f"A{next_row}:E{next_row}", [[category, amount, comments, date, "Ryan"]], value_input_option='USER_ENTERED')
            elif selected_card == "💳 Chloe":
                user_sheet.update(f"A{next_row}:E{next_row}", [[category, amount, comments, date, "Chloe"]], value_input_option='USER_ENTERED')
        
        next_row2 = len(user_sheet2.col_values(1)) + 1
        user_sheet2.update(f"A{next_row2}:D{next_row2}", [[category, amount, comments, date]], value_input_option='USER_ENTERED')

    ryloe_sheet = spreadsheet.worksheet("Ryloe")
    records = ryloe_sheet.get_all_records()
    if not records:
        balance = 0.0  # If no records, set balance to 0
    else:
        latest_record = records[-1]  # Get the last record
        balance = float(latest_record["Total"])  # Get the balance value from the "Total" column


    if name == "👫 Ryloe":
        await update.message.reply_text(f"✅ {amount} {comments} recorded for {name} in {category} category!\n\n💰 Ryloe's Updated Balance: ${balance:.2f}"
        )
    else:
        await update.message.reply_text(f"✅ {amount} {comments} recorded for {name} in {category} category!")    
    await update.message.reply_text(
        "💰 *Welcome to the Budget Bot!* 💰\n\n"
        "✨ Use the commands below to manage your budget:\n\n"
        "📝 */input* – Log your spendings\n"
        "💵 */addamount* – Top up the joint account balance\n"
        "📊 */view* – View spendings for the month\n"
        "📅 /monthlyview – View monthly spendings for a selected month\n"
        "❌ */cancel* – Cancel and return to the main menu\n"
        "🗑️ */delete* – Remove specific spendings\n\n"
        "🚀 Let's keep track of your finances!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    return ConversationHandler.END


@check_authorized_user
async def view_spending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_keyboard = [["💳 Ryan", "💳 Chloe", "👫 Ryloe"]]
    await update.message.reply_text(
        "Whose spendings would you like to view?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    context.user_data["view"] = True

@check_authorized_user
async def handle_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        name = update.message.text.strip()
        current_month = datetime.now().strftime("%m-%Y")

        if name == "👫 Ryloe":
            current_month = datetime.now().strftime("%m-%Y")
            records = spreadsheet.worksheet("Ryloe").get_all_records()
            records = records[1:]  # Skip header row

            latest_record = records[-1]

            try:
                balance = float(str(latest_record["Total"]).strip())  # Ensure it's a number
            except ValueError:
                balance = "Unknown"

            response = f"💰 Ryloe's Balance: ${balance:.2f}\n"

            # Filter records for the current month & remove "Add" transactions
            current_month_records = [
                row for row in records 
                if row.get("Date") and datetime.strptime(row["Date"], "%m-%d-%Y").strftime("%m-%Y") == current_month 
                and row["Category"] != "Add"
            ]

            current_month_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))


            if not current_month_records:
                response += "\n 📭 No spending transactions found this month."
            else:
                ryan_transactions = []
                chloe_transactions = []
                ryan_total = 0.0
                chloe_total = 0.0

                for row in current_month_records:
                    who_paid = row["Who Paid"].strip()
                    if who_paid == "Ryan":
                        ryan_transactions.append(f'{row["Date"]}: {row["Category"]} - ${float(row["Amount"]):.2f}\nComments:{row["Comments"]}\n')
                        ryan_total += float(row["Amount"])
                    elif who_paid == "Chloe":
                        chloe_transactions.append(f'{row["Date"]}: {row["Category"]} - ${float(row["Amount"]):.2f}\nComments:{row["Comments"]}\n')
                        chloe_total += float(row["Amount"])

                # Append transactions under their respective cards
                if ryan_transactions:
                    response += f"\n\nRyan's Card (Total: ${ryan_total:.2f}):\n" + "\n".join(ryan_transactions)
                if chloe_transactions:
                    response += f"\n\nChloe's Card (Total: ${chloe_total:.2f}):\n" + "\n".join(chloe_transactions)


            await update.message.reply_text(response if response else "📭 No transactions found this month.")

        elif name == "💳 Ryan":
            records = spreadsheet.worksheet("Ryan").get_all_records()
            records = records[1:]  # Remove header row if needed

            current_month = datetime.now().strftime("%m-%Y")
            user_records = []

            for row in records:
                try:
                    row_date = datetime.strptime(row["Date"], "%m-%d-%Y")
                    if row_date.strftime("%m-%Y") == current_month:
                        user_records.append(row)
                except ValueError:
                    continue  # Skip invalid date formats
            user_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))

            if not user_records:
                await update.message.reply_text(f"No records found for {name} this month.")
                await update.message.reply_text(
                    "💰 Welcome to the Budget Bot! 💰\n\n"
                    "✨ Use the commands below to manage your budget:\n\n"
                    "📝 /input – Log your spendings\n"
                    "💵 /addamount – Top up the joint account balance\n"
                    "📊 /view – View spendings for the month\n"
                    "📅 /monthlyview – View monthly spendings for a selected month\n"
                    "❌ /cancel – Cancel and return to the main menu\n"
                    "🗑️ /delete – Remove specific spendings\n\n"
                    "🚀 Let's keep track of your finances! 🌟",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END

            spending_transactions = []
            total = 0.0

            for row in user_records:
                amount = float(row["Amount"])
                total += amount
                spending_transactions.append(f'{row["Date"]}: {row["Category"]} - ${amount:.2f}\nComments:{row["Comments"]}\n')

            response = "\n".join(spending_transactions)
            response += f"\n\n🧾 Total Spent: ${total:.2f}"

            await update.message.reply_text(response if response else "📭 No transactions found this month.")

        elif name == "💳 Chloe":
            records = spreadsheet.worksheet("Chloe").get_all_records()
            records = records[1:]  # Remove header row if needed

            current_month = datetime.now().strftime("%m-%Y")
            user_records = []

            for row in records:
                try:
                    row_date = datetime.strptime(row["Date"], "%m-%d-%Y")
                    if row_date.strftime("%m-%Y") == current_month:
                        user_records.append(row)
                except ValueError:
                    continue  # Skip invalid date formats
            user_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))

            if not user_records:
                await update.message.reply_text(f"No records found for {name} this month.")
                await update.message.reply_text(
                    "💰 Welcome to the Budget Bot! 💰\n\n"
                    "✨ Use the commands below to manage your budget:\n\n"
                    "📝 /input – Log your spendings\n"
                    "💵 /addamount – Top up the joint account balance\n"
                    "📊 /view – View spendings for the month\n"
                    "📅 /monthlyview – View monthly spendings for a selected month\n"
                    "❌ /cancel – Cancel and return to the main menu\n"
                    "🗑️ /delete – Remove specific spendings\n\n"
                    "🚀 Let's keep track of your finances! 🌟",
                    reply_markup=ReplyKeyboardRemove())
            
                return ConversationHandler.END

            spending_transactions = []
            total = 0.0

            for row in user_records:
                amount = float(row["Amount"])
                total += amount
                spending_transactions.append(f'{row["Date"]}: {row["Category"]} - ${amount:.2f}\nComments:{row["Comments"]}\n')

            response = "\n".join(spending_transactions)
            response += f"\n\n🧾 Total Spent: ${total:.2f}"

            await update.message.reply_text(response if response else "No transactions found this month.")

        else:
            await update.message.reply_text(f"⚠️ Error: {name} is not a valid user.")
            await update.message.reply_text(
            "💰 Welcome to the Budget Bot! 💰\n\n"
            "✨ Use the commands below to manage your budget:\n\n"
            "📝 /input – Log your spendings\n"
            "💵 /addamount – Top up the joint account balance\n"
            "📊 /view – View spendings for the month\n"
            "📅 /monthlyview – View monthly spendings for a selected month\n"
            "❌ /cancel – Cancel and return to the main menu\n"
            "🗑️ /delete – Remove specific spendings\n\n"
            "🚀 Let's keep track of your finances!",
            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")
    
    await update.message.reply_text(
    "💰 Welcome to the Budget Bot! 💰\n\n"
    "✨ Use the commands below to manage your budget:\n\n"
    "📝 /input – Log your spendings\n"
    "💵 /addamount – Top up the joint account balance\n"
    "📊 /view – View spendings for the month\n"
    "📅 /monthlyview – View monthly spendings for a selected month\n"
    "❌ /cancel – Cancel and return to the main menu\n"
    "🗑️ /delete – Remove specific spendings\n\n"
    "🚀 Let's keep track of your finances!",
    reply_markup=ReplyKeyboardRemove())



@check_authorized_user
async def monthly_view_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📅 Which month and year would you like to view?\n"
        "Please use the format: MM-YYYY\n"
        "Example: 02-2025 📆"
    )
    return MONTH_YEAR

async def handle_month_year_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    month_year = update.message.text.strip()

    try:
        datetime.strptime(month_year, "%m-%Y")
    except ValueError:
        await update.message.reply_text("❌ Invalid format! Please enter the month and year in MM-YYYY format.")
        return MONTH_YEAR

    # Store the month-year in context for later use
    context.user_data["selected_month_year"] = month_year

    await update.message.reply_text(
        f"✅ Showing spendings for {month_year}. Please select whose records you'd like to view:",
        reply_markup=ReplyKeyboardMarkup([["💳 Ryan", "💳 Chloe", "👫 Ryloe"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return MONTH_VIEW

@check_authorized_user
async def view_selected_month_spending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Get the selected month-year from user data
    month_year = context.user_data.get("selected_month_year", None)
    if not month_year:
        await update.message.reply_text("⚠️ Error: No month-year selected.")
        return

    # Get the user’s selected name (Ryan, Chloe, or Ryloe)
    name = update.message.text.strip()
    month = month_year
    try:
        if name == "👫 Ryloe":
            records = spreadsheet.worksheet("Ryloe").get_all_records()
            records = records[1:]

            latest_record = records[-1]

            try:
                balance = float(str(latest_record["Total"]).strip())  # Ensure it's a number
            except ValueError:
                balance = "Unknown"

            response = f"💰 Ryloe's Balance: ${balance:.2f}\n"

            # Filter records for the current month & remove "Add" transactions
            current_month_records = [
                row for row in records 
                if row.get("Date") and datetime.strptime(row["Date"], "%m-%d-%Y").strftime("%m-%Y") == month 
                and row["Category"] != "Add"
            ]

            if not current_month_records:
                response += "\n 📭 No spending transactions found this month."
            else:
                current_month_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))
                ryan_transactions = []
                chloe_transactions = []
                ryan_total = 0.0
                chloe_total = 0.0

                for row in current_month_records:
                    who_paid = row["Who Paid"].strip()
                    if who_paid == "Ryan":
                        ryan_transactions.append(f'{row["Date"]}: {row["Category"]} - ${float(row["Amount"]):.2f}\nComments:{row["Comments"]}\n')
                        ryan_total += float(row["Amount"])
                    elif who_paid == "Chloe":
                        chloe_transactions.append(f'{row["Date"]}: {row["Category"]} - ${float(row["Amount"]):.2f}\nComments:{row["Comments"]}\n')
                        chloe_total += float(row["Amount"])

                # Append transactions under their respective cards
                if ryan_transactions:
                    response += f"\n\nRyan's Card (Total: ${ryan_total:.2f}):\n" + "\n".join(ryan_transactions)
                if chloe_transactions:
                    response += f"\n\nChloe's Card (Total: ${chloe_total:.2f}):\n" + "\n".join(chloe_transactions)

            # Send message with balance + categorized transactions
            await update.message.reply_text(response if response else "📭 No transactions found this month.")

        elif name == "💳 Ryan":
            records = spreadsheet.worksheet("Ryan").get_all_records()
            records = records[1:]  # Remove header row if needed

            month = month_year
            user_records = []

            for row in records:
                try:
                    row_date = datetime.strptime(row["Date"], "%m-%d-%Y")
                    if row_date.strftime("%m-%Y") == month:
                        user_records.append(row)
                except ValueError:
                    continue
            user_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))
            if not user_records:
                await update.message.reply_text(f"📭 No records found for {name} this month.")
            spending_transactions = []
            total = 0.0

            for row in user_records:
                amount = float(row["Amount"])
                total += amount
                spending_transactions.append(f'{row["Date"]}: {row["Category"]} - ${amount:.2f}\nComments:{row["Comments"]}\n')

            response = "\n".join(spending_transactions)
            response += f"\n\n🧾 Total Spent: ${total:.2f}"

            await update.message.reply_text(response if response else "📭 No transactions found this month.")
            await update.message.reply_text(
                    "💰 Welcome to the Budget Bot! 💰\n\n"
                    "✨ Use the commands below to manage your budget:\n\n"
                    "📝 /input – Log your spendings\n"
                    "💵 /addamount – Top up the joint account balance\n"
                    "📊 /view – View spendings for the month\n"
                    "📅 /monthlyview – View monthly spendings for a selected month\n"
                    "❌ /cancel – Cancel and return to the main menu\n"
                    "🗑️ /delete – Remove specific spendings\n\n"
                    "🚀 Let's keep track of your finances! 🌟",
                    reply_markup=ReplyKeyboardRemove()
                )

        elif name == "💳 Chloe":
            records = spreadsheet.worksheet("Chloe").get_all_records()
            records = records[1:]

            month = month_year
            user_records = []

            for row in records:
                try:
                    row_date = datetime.strptime(row["Date"], "%m-%d-%Y")
                    if row_date.strftime("%m-%Y") == month:
                        user_records.append(row)
                except ValueError:
                    continue
            user_records.sort(key=lambda row: datetime.strptime(row["Date"], "%m-%d-%Y"))
            if not user_records:
                await update.message.reply_text(f"📭 No records found for {name} this month.")

            spending_transactions = []
            total = 0.0

            for row in user_records:
                amount = float(row["Amount"])
                total += amount
                spending_transactions.append(f'{row["Date"]}: {row["Category"]} - ${amount:.2f}\nComments:{row["Comments"]}\n')
            response = "\n".join(spending_transactions)
            response += f"\n\n🧾 Total Spent: ${total:.2f}"

            await update.message.reply_text(response if response else "📭 No transactions found this month.")
            await update.message.reply_text(
                    "💰 Welcome to the Budget Bot! 💰\n\n"
                    "✨ Use the commands below to manage your budget:\n\n"
                    "📝 /input – Log your spendings\n"
                    "💵 /addamount – Top up the joint account balance\n"
                    "📊 /view – View spendings for the month\n"
                    "📅 /monthlyview – View monthly spendings for a selected month\n"
                    "❌ /cancel – Cancel and return to the main menu\n"
                    "🗑️ /delete – Remove specific spendings\n\n"
                    "🚀 Let's keep track of your finances! 🌟",
                    reply_markup=ReplyKeyboardRemove())

        else:
            await update.message.reply_text(f"error: {name} is not a valid user.")
            await update.message.reply_text(
                "💰 Welcome to the Budget Bot! 💰\n\n"
                "✨ Use the commands below to manage your budget:\n\n"
                "📝 /input – Log your spendings\n"
                "💵 /addamount – Top up the joint account balance\n"
                "📊 /view – View spendings for the month\n"
                "📅 /monthlyview – View monthly spendings for a selected month\n"
                "❌ /cancel – Cancel and return to the main menu\n"
                "🗑️ /delete – Remove specific spendings\n\n"
                "🚀 Let's keep track of your finances! 🌟",
                reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")
    
    await update.message.reply_text(
        "💰 Welcome to the Budget Bot! 💰\n\n"
        "✨ Use the commands below to manage your budget:\n\n"
        "📝 /input – Log your spendings\n"
        "💵 /addamount – Top up the joint account balance\n"
        "📊 /view – View spendings for the month\n"
        "📅 /monthlyview – View monthly spendings for a selected month\n"
        "❌ /cancel – Cancel and return to the main menu\n"
        "🗑️ /delete – Remove specific spendings\n\n"
        "🚀 Let's keep track of your finances!",
    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

@check_authorized_user
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
    "💰 Welcome to the Budget Bot! 💰\n\n"
    "✨ Use the commands below to manage your budget:\n\n"
    "📝 /input – Log your spendings\n"
    "💵 /addamount – Top up the joint account balance\n"
    "📊 /view – View spendings for the month\n"
    "📅 /monthlyview – View monthly spendings for a selected month\n"
    "❌ /cancel – Cancel and return to the main menu\n"
    "🗑️ /delete – Remove specific spendings\n\n"
    "🚀 Let's keep track of your finances!",
    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def split_message(message, max_chars=4000):
    """Splits long message into chunks within Telegram's message limit."""
    lines = message.split("\n")
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 < max_chars:
            current_chunk += line + "\n"
        else:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

@check_authorized_user
async def delete_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["delete_name"] = update.message.text
    name = update.message.text
    try:
        if name == "💳 Ryan":
            user_sheet = spreadsheet.worksheet("Ryan")
        elif name == "💳 Chloe":
            user_sheet = spreadsheet.worksheet("Chloe")
        else:
            user_sheet = spreadsheet.worksheet("Ryloe")

        records = user_sheet.get_all_records()[1:]  # Skip header row

        if not records:
            await update.message.reply_text(f"{name} has no recorded spendings.")
            await update.message.reply_text(    
                "💰 Welcome to the Budget Bot! 💰\n\n"
                "✨ Use the commands below to manage your budget:\n\n"
                "📝 /input – Log your spendings\n"
                "💵 /addamount – Top up the joint account balance\n"
                "📊 /view – View spendings for the month\n"
                "📅 /monthlyview – View monthly spendings for a selected month\n"
                "❌ /cancel – Cancel and return to the main menu\n"
                "🗑️ /delete – Remove specific spendings\n\n"
                "🚀 Let's keep track of your finances!",
                reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        # Build the full spendings message
        spendings_message = f"{name}'s current spendings:\n"
        for index, row in enumerate(records, start=1):
            date = row.get('Date', '')
            category = row.get('Category', '')
            amount = row.get('Amount', '')
            spendings_message += f"{index}: {date}: {category} - ${round(float(amount), 2):.2f}\n"

        # Split and send in chunks
        for chunk in split_message(spendings_message):
            await update.message.reply_text(chunk)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error occurred while retrieving spendings: {str(e)}")
        return ConversationHandler.END

    await update.message.reply_text(
        "🗑️ *Delete an Entry*\n\n"
        "Please specify the details of the entry you want to remove. Simply enter the index number of the entry you wish to delete.",
        parse_mode="Markdown"
    )
    return DELETE_DETAILS

# Function to start the deletion process
@check_authorized_user
async def delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply_keyboard = [["💳 Ryan", "💳 Chloe", "👫 Ryloe"]]
    await update.message.reply_text(
    "👤 *Select a User*\n\n"
    "Which user's records would you like to delete? Please choose from the options below.",
    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    parse_mode="Markdown"
)
    return DELETE_USER

# @check_authorized_user
# async def delete_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     context.user_data["delete_name"] = update.message.text
#     name = update.message.text
#     try:
#         if name == "💳 Ryan":
#             user_sheet = spreadsheet.worksheet("Ryan")
#             records = user_sheet.get_all_records()
#         elif name == "💳 Chloe":
#             user_sheet = spreadsheet.worksheet("Chloe")
#             records = user_sheet.get_all_records()
#         else:
#             user_sheet = spreadsheet.worksheet("Ryloe")
#             records = user_sheet.get_all_records()

#         records = records[1:]
#         # Format the current spendings as a message
#         if records:
#             spendings_message = f"{name}'s current spendings:\n"
#             index = 1
#             for row in records:
#                 date = row.get('Date', '')
#                 category = row.get('Category', '')
#                 amount = row.get('Amount', '')
#                 spendings_message += f"{index}: {date}: {category} - ${round(float(amount), 2):.2f}\n"
#                 index += 1
#         else:
#             spendings_message = f"{name} recorded spendings."
#             await update.message.reply_text(spendings_message)
#             await update.message.reply_text(    
#                 "💰 Welcome to the Budget Bot! 💰\n\n"
#                 "✨ Use the commands below to manage your budget:\n\n"
#                 "📝 /input – Log your spendings\n"
#                 "💵 /addamount – Top up the joint account balance\n"
#                 "📊 /view – View spendings for the month\n"
#                 "📅 /monthlyview – View monthly spendings for a selected month\n"
#                 "❌ /cancel – Cancel and return to the main menu\n"
#                 "🗑️ /delete – Remove specific spendings\n\n"
#                 "🚀 Let's keep track of your finances!",
#                 reply_markup=ReplyKeyboardRemove())
#             return ConversationHandler.END

#         await update.message.reply_text(spendings_message)
#     except Exception as e:
#         await update.message.reply_text(f"⚠️ Error occurred while retrieving spendings: {str(e)}")

#     # Now ask the user to specify the details of the entry they want to delete
#     await update.message.reply_text(
#         "🗑️ *Delete an Entry*\n\n"
#         "Please specify the details of the entry you want to remove. Simply enter the index number of the entry you wish to delete."
#     )
#     return DELETE_DETAILS

# Handler to get details of the entry to be deleted
@check_authorized_user
async def delete_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        # Parse the index number from the user's message
        index = int(update.message.text.strip())
        name = context.user_data.get("delete_name")

        # Determine the appropriate sheet based on the user's selection
        if name == "💳 Ryan":
            user_sheet = spreadsheet.worksheet("Ryan")
            user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
            records = user_sheet.get_all_records()
            records2 = user_sheet2.get_all_records()
        elif name == "💳 Chloe":
            user_sheet = spreadsheet.worksheet("Chloe")
            user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
            records = user_sheet.get_all_records()
            records2 = user_sheet2.get_all_records()
        else:
            user_sheet = spreadsheet.worksheet("Ryloe")
            records = user_sheet.get_all_records(expected_headers=["Date", "Category", "Comments" ,"Amount"])
            user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
            records2 = user_sheet2.get_all_records(expected_headers=["Date", "Category", "Comments" ,"Amount"])

        records = records[1:]  # Skip the header row
        
        # Validate the index
        if index < 1 or index > len(records):
            await update.message.reply_text(f"⚠️ Invalid index. Please provide a number between 1 and {len(records)}.")
            return DELETE_DETAILS

        # Retrieve the details of the record to be deleted
        record_to_delete = records[index-1]  # Subtract 1 for zero-based indexing
        date = record_to_delete["Date"]
        category = record_to_delete["Category"]
        amount = record_to_delete["Amount"]

        # Confirm deletion
        context.user_data["delete_index"] = index
        await update.message.reply_text(
            f"You want to delete the following entry:\n"
            f"{index}: {date}: {category} - ${amount}\nIs that correct? (Yes/No)"
        )
        return DELETE_CONFIRM

    except ValueError:
        await update.message.reply_text("⚠️Invalid input. Please provide a valid index number.")
        return DELETE_DETAILS
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error occurred: {str(e)}")
        return ConversationHandler.END

@check_authorized_user
async def delete_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text.strip().lower()
    name = context.user_data.get("delete_name")
    index = context.user_data.get("delete_index")

    if response == "yes":
        try:
            # Fetch details from the selected sheet based on index
            if name == "💳 Ryan":
                user_sheet = spreadsheet.worksheet("Ryan")
                records = user_sheet.get_all_records()
                selected_row = records[index]  # Convert 1-based index to 0-based
                date_part = selected_row["Date"]
                category_part = selected_row["Category"].lower()
                amount_part = selected_row["Amount"]
                
                # Delete the row in "Ryan"
                user_sheet.delete_rows(index+2)  # Add 1 for 1-based index

                # Search and delete in "Ryan Credit Card"
                user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
                records2 = user_sheet2.get_all_records()
                matched = False
                for row_index, row in enumerate(records2):
                    date_column = str(row["Date"]).lower()
                    category_column = str(row["Category"]).lower()
                    try:
                        amount_column_float = round(float(row["Amount"]), 2)
                    except ValueError:
                        continue

                    if date_part.lower() == date_column and category_part == category_column and amount_part == amount_column_float:
                        user_sheet2.delete_rows(row_index + 2)  # +2 for header row
                        matched = True
                        break

                if matched:
                    await update.message.reply_text(f"✅ Record deleted from {name}.\n🗓️ {date_part} | 📌 {category_part} | 💰 {amount_part}")
                else:
                    await update.message.reply_text(f"⚠️ No matching record found in {name} credit card sheet.")

            elif name == "💳 Chloe":
                user_sheet = spreadsheet.worksheet("Chloe")
                records = user_sheet.get_all_records()
                selected_row = records[index]  # Convert 1-based index to 0-based
                date_part = selected_row["Date"]
                category_part = selected_row["Category"].lower()
                amount_part = selected_row["Amount"]
                
                # Delete the row in "Ryan"
                user_sheet.delete_rows(index + 2)  # Add 1 for 1-based index

                user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
                records2 = user_sheet2.get_all_records()
                matched = False
                for row_index, row in enumerate(records2):
                    date_column = str(row["Date"]).lower()
                    category_column = str(row["Category"]).lower()
                    try:
                        amount_column_float = round(float(row["Amount"]), 2)
                    except ValueError:
                        continue

                    if date_part.lower() == date_column and category_part == category_column and amount_part == amount_column_float:
                        user_sheet2.delete_rows(row_index + 2)  # +2 for header row
                        matched = True
                        break

                if matched:
                    await update.message.reply_text(f"✅ Record deleted from {name}.\n🗓️ {date_part} | 📌 {category_part} | 💰 {amount_part}")
                else:
                    await update.message.reply_text(f"⚠️ No matching record found in {name} credit card sheet.")

            elif name == "👫 Ryloe":
                user_sheet = spreadsheet.worksheet("Ryloe")
                records = user_sheet.get_all_records()
                selected_row = records[index]  # Convert 1-based index to 0-based
                date_part = selected_row["Date"]
                category_part = selected_row["Category"].lower()
                amount_part = selected_row["Amount"]
                who_paid = selected_row["Who Paid"].lower()
                
                user_sheet.delete_rows(index + 2)

                if who_paid == "💳 Chloe":
                    user_sheet2 = spreadsheet.worksheet("Chloe Credit Card")
                else:
                    user_sheet2 = spreadsheet.worksheet("Ryan Credit Card")
                records2 = user_sheet2.get_all_records()
                matched = False
                for row_index, row in enumerate(records2):
                    date_column = str(row["Date"]).lower()
                    category_column = str(row["Category"]).lower()
                    try:
                        amount_column_float = round(float(row["Amount"]), 2)
                    except ValueError:
                        continue

                    if date_part.lower() == date_column and category_part == category_column and amount_part == amount_column_float:
                        user_sheet2.delete_rows(row_index + 2)  # +2 for header row
                        matched = True
                        break

                if matched:
                    await update.message.reply_text(f"✅ Record deleted from {name}.\n🗓️ {date_part} | 📌 {category_part} | 💰 {amount_part} | 🏷️ Paid by: {who_paid.capitalize()}")
                else:
                    await update.message.reply_text("⚠️ No matching record found in the corresponding credit card sheet.")

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error occurred: {str(e)}")

    elif response == "no":
        await update.message.reply_text("❌ Deletion process canceled.")
    else:
        await update.message.reply_text("⚠️ Please reply with 'Yes' or 'No'.")
        return DELETE_CONFIRM

    await update.message.reply_text(    
        "💰 Welcome to the Budget Bot! 💰\n\n"
        "✨ Use the commands below to manage your budget:\n\n"
        "📝 /input – Log your spendings\n"
        "💵 /addamount – Top up the joint account balance\n"
        "📊 /view – View spendings for the month\n"
        "📅 /monthlyview – View monthly spendings for a selected month\n"
        "❌ /cancel – Cancel and return to the main menu\n"
        "🗑️ /delete – Remove specific spendings\n\n"
        "🚀 Let's keep track of your finances!",
        reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


conv_handler_input = ConversationHandler(
    entry_points=[CommandHandler("input", input_spending)],
    states = {
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
        CATEGORY: [CallbackQueryHandler(category_handler_callback)],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler)],
        ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount_handler)],
        CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_category_handler)],
        CARD_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, card_selection_handler)],
    },
    fallbacks=[CommandHandler("cancel", cancel_handler)],
)

conv_handler_add = ConversationHandler(
    entry_points=[CommandHandler("addamount", add_amount_start)],
    states={
        ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount_handler)],
    },
    fallbacks=[CommandHandler("cancel", cancel_handler)],
)

conv_handler_delete = ConversationHandler(
    entry_points=[CommandHandler("delete", delete_entry)],
    states = {
        DELETE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user_handler)],
        DELETE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_details_handler)],
        DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm_handler)],
    },
    fallbacks=[CommandHandler("cancel", cancel_handler)],
)

MONTH_YEAR, MONTH_VIEW = range(2)

conv_handler_monthlyview = ConversationHandler(
    entry_points=[CommandHandler('monthlyview', monthly_view_start)],
    states={
        MONTH_YEAR: [MessageHandler(filters.TEXT, handle_month_year_input)],
        MONTH_VIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_selected_month_spending)],
    },
    fallbacks=[],
)

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler_input)
    app.add_handler(conv_handler_delete)
    app.add_handler(conv_handler_add)
    app.add_handler(CommandHandler("view", view_spending))
    app.add_handler(conv_handler_monthlyview)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_view))
    app.add_handler(CommandHandler("cancel", cancel_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
