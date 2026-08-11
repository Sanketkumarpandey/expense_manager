from enum import Enum


class ExpenseSource(str, Enum):
	TELEGRAM = "Telegram"
	WEB = "Web"
	API = "API"
	MANUAL = "Manual"


class PaymentMethod(str, Enum):
	CASH = "Cash"
	UPI = "UPI"
	CREDIT_CARD = "Credit Card"
	DEBIT_CARD = "Debit Card"
	NET_BANKING = "Net Banking"
	WALLET = "Wallet"
	OTHER = "Other"
