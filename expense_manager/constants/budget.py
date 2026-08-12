from enum import Enum


class BudgetPeriod(str, Enum):
	WEEKLY = "Weekly"
	MONTHLY = "Monthly"
	QUARTERLY = "Quarterly"
	YEARLY = "Yearly"
