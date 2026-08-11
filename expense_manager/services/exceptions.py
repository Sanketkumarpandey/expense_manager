class ExpenseManagerError(Exception):
	"""Base exception for all Expense Manager business errors."""


class ValidationError(ExpenseManagerError):
	"""Raised when business validation fails."""


class CategoryError(ExpenseManagerError):
	"""Base exception for category-related errors."""


class CategoryAlreadyExistsError(CategoryError):
	"""Raised when attempting to create a duplicate category."""


class CategoryNotFoundError(CategoryError):
	"""Raised when the requested category does not exist."""


class CategoryInUseError(CategoryError):
	"""Raised when a category cannot be deleted because it is in use."""


class CategoryInactiveError(CategoryError):
	"""Raised when an inactive category is used."""


class CategoryNotAllowedError(CategoryError):
	"""Raised when an expense is created for a dependent in a category the
	dependent's allowed-categories list does not permit."""


class BudgetError(ExpenseManagerError):
	"""Base exception for budget-related errors."""


class BudgetAlreadyExistsError(BudgetError):
	"""Raised when a budget already exists."""


class BudgetNotFoundError(BudgetError):
	"""Raised when the requested budget does not exist."""


class BudgetExceededError(BudgetError):
	"""Raised when spending exceeds the allocated budget."""


class InvalidBudgetPeriodError(BudgetError):
	"""Raised when an invalid budget period is supplied."""


class InvalidBudgetAmountError(BudgetError):
	"""Raised when an invalid allocated amount is supplied."""


class InvalidBudgetDateRangeError(BudgetError):
	"""Raised when the budget's end date is before its start date."""


class InvalidAlertThresholdError(BudgetError):
	"""Raised when an invalid alert threshold percentage is supplied."""


class ExpenseError(ExpenseManagerError):
	"""Base exception for expense-related errors."""


class ExpenseNotFoundError(ExpenseError):
	"""Raised when the requested expense does not exist."""


class InvalidExpenseAmountError(ExpenseError):
	"""Raised when an invalid expense amount is supplied."""


class InvalidExpenseSourceError(ExpenseError):
	"""Raised when an invalid expense source is supplied."""


class InvalidExpenseDateError(ExpenseError):
	"""Raised when an invalid expense date is supplied."""


class ExpenseModificationError(ExpenseError):
	"""Raised when an expense cannot be modified."""


class ExpenseDeletionError(ExpenseError):
	"""Raised when an expense cannot be deleted."""


class DependentError(ExpenseManagerError):
	"""Base exception for dependent-related errors."""


class DependentAlreadyExistsError(DependentError):
	"""Raised when a dependent already exists."""


class DependentNotFoundError(DependentError):
	"""Raised when the requested dependent does not exist."""


class DependentInactiveError(DependentError):
	"""Raised when an inactive dependent is used."""


class DependentInUseError(DependentError):
	"""Raised when a dependent cannot be deleted because it is referenced elsewhere."""


class InvalidRelationshipError(DependentError):
	"""Raised when an invalid relationship value is supplied."""


class InvalidAllowanceError(DependentError):
	"""Raised when an invalid monthly allowance is supplied."""


class PocketMoneyError(ExpenseManagerError):
	"""Base exception for pocket money-related errors."""


class PocketMoneyNotAllocatedError(PocketMoneyError):
	"""Raised when no pocket money allocation exists."""


class PocketMoneyExceededError(PocketMoneyError):
	"""Raised when an expense exceeds the available pocket money."""


class InsufficientBalanceError(PocketMoneyError):
	"""Raised when insufficient balance is available."""


class SavingsRolloverError(PocketMoneyError):
	"""Raised when savings rollover cannot be completed."""


class PocketMoneyAllocationNotFoundError(PocketMoneyError):
	"""Raised when the requested pocket money allocation does not exist."""


class PocketMoneyAllocationAlreadyExistsError(PocketMoneyError):
	"""Raised when an active allocation already exists for a dependent."""


class InvalidAllocationAmountError(PocketMoneyError):
	"""Raised when an invalid allocated amount is supplied."""


class InvalidAllocationPeriodError(PocketMoneyError):
	"""Raised when an invalid allocation period is supplied."""


class InvalidAllocationDateError(PocketMoneyError):
	"""Raised when an invalid allocation date is supplied."""


class InvalidCarryForwardAmountError(PocketMoneyError):
	"""Raised when an invalid carry forward amount is supplied."""


class TelegramError(ExpenseManagerError):
	"""Base exception for Telegram-related errors."""


class TelegramLinkRequiredError(TelegramError):
	"""Raised when an active Telegram link is required."""


class TelegramAlreadyLinkedError(TelegramError):
	"""Raised when a Telegram account is already linked."""


class TelegramNotLinkedError(TelegramError):
	"""Raised when no Telegram account is linked."""


class InvalidTelegramLinkCodeError(TelegramError):
	"""Raised when the Telegram link code is invalid."""


class ExpiredTelegramLinkCodeError(TelegramError):
	"""Raised when the Telegram link code has expired."""


class TelegramUserNotFoundError(TelegramError):
	"""Raised when linking is attempted against a non-existent Frappe user."""


class ReportError(ExpenseManagerError):
	"""Base exception for report-related errors."""


class InvalidReportDateRangeError(ReportError):
	"""Raised when a report's end date is before its start date."""


class TelegramServiceError(ExpenseManagerError):
	"""Base exception for TelegramService orchestration errors."""


class UnauthorizedTelegramActionError(TelegramServiceError):
	"""Raised when a linked Telegram account attempts an action outside its persona's permissions."""
