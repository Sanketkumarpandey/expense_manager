"""Reply for the Telegram /report command — sends a chart image with a caption."""

from expense_manager.telegram.services.telegram_service import TelegramService, send_photo
from expense_manager.telegram.utils.helpers import get_telegram_user_id, get_chat_id
from expense_manager.api.reports import generate_chart_png


def handle_report(update: dict[str, object]) -> str | None:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_category_report(telegram_user_id)
	if not result["success"]:
		return result["message"]

	breakdown = result["data"]
	if not breakdown:
		return "No expenses recorded yet."

	chat_id = get_chat_id(update)
	if chat_id is None:
		return "I couldn't deliver your report. Please try again."

	top_rows = breakdown[:10]
	dataset = [{"label": row["category_name"], "value": row["total_amount"]} for row in top_rows]

	caption_lines = ["Your spending by category:"]
	for row in top_rows:
		caption_lines.append(
			f"- {row['category_name']}: {row['total_amount']} ({row['percentage_of_total']}%)"
		)
	caption = "\n".join(caption_lines)

	chart_png = generate_chart_png(dataset, title="Spending by Category")
	send_photo(chat_id, chart_png, caption=caption)
	return None