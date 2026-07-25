from __future__ import annotations

from enum import Enum


class AllocationPeriod(str, Enum):
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"