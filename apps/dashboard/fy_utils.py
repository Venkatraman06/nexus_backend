"""Indian financial year helpers (Apr 1 → Mar 31)."""

from datetime import date


def current_fy_start(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 4 else today.year - 1


def fy_label(fy_start_year: int) -> str:
    return f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}"


def fy_bounds(fy_start_year: int) -> tuple[date, date]:
    return date(fy_start_year, 4, 1), date(fy_start_year + 1, 3, 31)


def fy_effective_end(fy_start_year: int, today: date | None = None) -> date:
    """End of FY range capped at today — no future dates."""
    today = today or date.today()
    _, fy_end = fy_bounds(fy_start_year)
    if fy_start_year > current_fy_start(today):
        raise ValueError("Future financial year is not available.")
    if fy_start_year == current_fy_start(today):
        return min(fy_end, today)
    return fy_end


def fy_date_range(fy_start_year: int, today: date | None = None) -> tuple[date, date]:
    start, _ = fy_bounds(fy_start_year)
    end = fy_effective_end(fy_start_year, today)
    return start, end


def available_fy_years(today: date | None = None, min_year: int | None = None) -> list[int]:
    today = today or date.today()
    current = current_fy_start(today)
    floor = min_year or (current - 5)
    return list(range(current, floor - 1, -1))


def iter_fy_months(fy_start_year: int, today: date | None = None) -> list[tuple[int, int, str]]:
    """Yield (year, month, label) for each month in FY up to today."""
    today = today or date.today()
    start, end = fy_date_range(fy_start_year, today)
    months: list[tuple[int, int, str]] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        dt = date(y, m, 1)
        if dt > end:
            break
        months.append((y, m, dt.strftime("%b %Y")))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return months
