"""Workday & work-hour helpers. Mon-Fri, excluding CN public holidays, 09:30-19:00."""
from datetime import date, datetime, time

WORK_START = time(9, 30)
WORK_END = time(19, 0)
LUNCH_HOURS: frozenset[int] = frozenset({12, 13})  # skip reminders during lunch


def is_public_holiday(d: date) -> bool:
    """Return True if d is a Chinese public holiday. Falls back to False if the
    holidays package is missing so the check degrades gracefully."""
    try:
        import holidays
    except ImportError:
        return False
    cn = holidays.country_holidays("CN", years=[d.year])
    return d in cn


def is_workday(d: date) -> bool:
    if d.weekday() >= 5:  # Saturday, Sunday
        return False
    if is_public_holiday(d):
        return False
    return True


def is_within_work_hours(t: time) -> bool:
    return WORK_START <= t <= WORK_END


def now_is_work_time(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return is_workday(now.date()) and is_within_work_hours(now.time())


def is_lunch_hour(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return now.hour in LUNCH_HOURS
