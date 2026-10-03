import calendar
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

import msgspec
from typing_extensions import Annotated

from script.misc.op import random_normal_distribution_int


class ServerUpdateCondition(msgspec.Struct):
    # 1 for the first day of month
    monthday: Annotated[Optional[int], msgspec.Meta(ge=1, le=31)] = None
    # 1 for monday, ..., 7 for sunday
    # weekday is 1-based, 1 for monday, ..., 7 for sunday, this is different to the weekday in datetime
    weekday: Annotated[Optional[int], msgspec.Meta(ge=1, le=7)] = None
    # hour=4,minute=0 means server updates at 04:00 everyday
    hour: Annotated[Optional[int], msgspec.Meta(ge=0, le=23)] = None
    minute: Annotated[Optional[int], msgspec.Meta(ge=0, le=59)] = None


TYPE_TIMEZONE_INPUT = Union[str, int, timedelta, timezone]
TYPE_SERVER_UPDATE_INPUT = Union[str, int, List[str], ServerUpdateCondition, List[ServerUpdateCondition]]


def parse_timezone(tz: TYPE_TIMEZONE_INPUT) -> timezone:
    """
    Convert to timezone as possible

    Args:
        tz: Timezone input

    Returns:
        timezone: Timezone object
    """
    if isinstance(tz, timezone):
        return tz
    if isinstance(tz, timedelta):
        # may raise ValueError:
        # offset must be a timedelta strictly between -timedelta(hours=24) and timedelta(hours=24), not ...
        return timezone(tz)
    if isinstance(tz, int):
        # -7 for timedelta(hours=-7)
        if not -23 <= tz <= 23:
            raise ValueError(f'Timezone hour must within -23~23, got {tz}')
        return timezone(timedelta(hours=tz))
    if isinstance(tz, str):
        if ':' in tz:
            h, _, m = tz.partition(':')
            # "09:30" for timedelta(hours=9, minutes=30)
            try:
                h = int(h)
                m = int(m)
            except (ValueError, TypeError):
                raise ValueError(f'Failed to parse timezone as HH:MM, got {tz}') from None
            if not -23 <= h <= 23:
                raise ValueError(f'Timezone hour must within -23~23, got {tz}')
            if not 0 <= m <= 59:
                raise ValueError(f'Timezone hour must within 0~59, got {tz}')
            return timezone(timedelta(hours=h, minutes=m))
        else:
            # "8" for timedelta(hours=8)
            try:
                h = int(tz)
            except (ValueError, TypeError):
                raise ValueError(f'Failed to parse timezone as hour, got {tz}') from None
            if not -23 <= h <= 23:
                raise ValueError(f'Timezone hour must within -23~23, got {tz}')
            return timezone(timedelta(hours=h))

    raise ValueError(f'Invalid timezone input: {tz}')


def parse_server_update(update):
    """
    Parse user input ServerUpdate
    note that: weekday is 1-based, 1 for monday, ..., 7 for sunday, this is different to the weekday in datetime

    "12:34" to ServerUpdateCondition(hour=12, minute=34)
    "18" to ServerUpdateCondition(hour=18)
    18 to ServerUpdateCondition(hour=18)
    "weekday1-04:00" to ServerUpdateCondition(weekday=1, hour=4, minute=0)
    "monthday1-04:00" to ServerUpdateCondition(monthday=1, hour=4, minute=0)

    Args:
        update (str | int | ServerUpdateCondition): Server update input

    Returns:
        ServerUpdateCondition | None: Parsed condition
    """
    if isinstance(update, int):
        if not 0 <= update <= 23:
            raise ValueError(f'ServerUpdate hour must within 0~23, got {update}')
        return ServerUpdateCondition(hour=update, minute=0)

    if isinstance(update, str):
        update = update.strip().replace(' ', '')
        if not update:
            raise ValueError('Empty server_update')
        weekday = None
        monthday = None
        hour = None
        minute = None
        for part in update.split('-'):
            if part.startswith('weekday'):
                try:
                    weekday = int(part[7:])
                except ValueError:
                    raise ValueError(f'Failed to parse weekday, got {part}') from None
                if not 1 <= weekday <= 7:
                    raise ValueError(f'Weekday must within 1~7, got {weekday}')
            elif part.startswith('monthday'):
                try:
                    monthday = int(part[8:])
                except ValueError:
                    raise ValueError(f'Failed to parse monthday, got {part}') from None
                if not 1 <= monthday <= 31:
                    raise ValueError(f'Monthday must within 1~31, got {monthday}')
            else:
                try:
                    if ':' in part:
                        hour, minute = part.split(':')
                    else:
                        hour, minute = part, 0
                    hour = int(hour)
                    minute = int(minute)
                except ValueError:
                    raise ValueError(f'Failed to parse time, got {part}') from None
                if not 0 <= hour <= 23:
                    raise ValueError(f'Hour must within 0~23, got {hour}')
                if not 0 <= minute <= 59:
                    raise ValueError(f'Minute must within 0~59, got {minute}')
        if weekday is None and monthday is None and hour is None and minute is None:
            raise ValueError(f'Empty condition in server_update input: {update}')
        if weekday is not None and monthday is not None:
            raise ValueError(f'Cannot have both weekday and monthday, got {update}')
        if weekday is not None and (hour is None or minute is None):
            raise ValueError(f'Hour and minute must be set when weekday is set, got {update}')
        if monthday is not None and (hour is None or minute is None):
            raise ValueError(f'Hour and minute must be set when monthday is set, got {update}')
        return ServerUpdateCondition(weekday=weekday, monthday=monthday, hour=hour, minute=minute)

    if isinstance(update, ServerUpdateCondition):
        return update
    raise ValueError(f'Invalid server_update input: {update}')


def parse_server_update_list(updates):
    """
    Parse user input to sorted [ServerUpdateCondition, ...]
    This method will not return empty list

    Args:
        updates (str | int | list[str] | ServerUpdateCondition): Server update inputs

    Returns:
        list[ServerUpdateCondition]: Sorted list of conditions
    """
    if isinstance(updates, int):
        updates = [updates]
    elif isinstance(updates, str):
        updates = [u.strip() for u in updates.split(',') if u.strip()]

    if isinstance(updates, list):
        out = []
        for update in updates:
            update = parse_server_update(update)
            if update is None:
                raise ValueError(f'Empty server_update input: {updates}')
            out.append(update)
        if not out:
            raise ValueError(f'Empty server_update input: {updates}')
        return sorted(out, key=lambda x: (x.monthday or 0, x.weekday or 0, x.hour or 0, x.minute or 0))

    if isinstance(updates, ServerUpdateCondition):
        return [updates]
    raise ValueError(f'Invalid server_update input: {updates}')


def nearest_future(futures, threshold=0):
    """
    Finds the earliest datetime, and if a threshold is provided,
    returns the latest datetime that falls within that window.

    Args:
        futures (list[datetime]): List of datetimes
        threshold (int): in seconds. Defaults to 0.

    Returns:
        datetime: Nearest future datetime
    """
    if not futures:
        raise ValueError(f'Empty future list')

    # 1. Sort the list to find the earliest datetime
    sorted_dates = sorted(futures)
    earliest = sorted_dates[0]

    # 2. If no threshold, just return the smallest
    if threshold <= 0:
        return earliest

    # 3. Calculate the cut-off point
    limit = earliest + timedelta(seconds=threshold)

    # 4. Find the last date that is within the threshold of the earliest
    # Since it's sorted, we can just iterate and keep the last valid one
    last_within_threshold = earliest
    for dt in sorted_dates[1:]:
        if dt <= limit:
            last_within_threshold = dt
        else:
            # Since the list is sorted, we can stop searching early
            break

    return last_within_threshold


def parse_second(second):
    """
    Args:
        second (int | float | str | tuple | list):
            3, 0.5, "3", "0.1~0.2", (1.5, 2.5), [1, 4], "10~30", "10, 30", "10-30"
            second must >= 0

    Returns:
        tuple[int | float, int | float]: (low, high) bounds
    """
    if isinstance(second, (tuple, list)):
        try:
            low, high = second
        except ValueError:
            raise ValueError(f'Expect format (low, high), got {second}') from None
    elif isinstance(second, str):
        second = second.strip().replace(' ', '')
        if ',' in second:
            low, _, high = second.partition(',')
        elif '~' in second:
            low, _, high = second.partition('~')
        elif '-' in second and not second.startswith('-'):
            # check startswith('-'), second might be negative value like "-10"
            low, _, high = second.partition('-')
        else:
            if '.' in second:
                try:
                    second = float(second)
                except (ValueError, TypeError):
                    raise ValueError(f'Expect second numeric, got "{second}"') from None
            else:
                try:
                    second = int(second)
                except (ValueError, TypeError):
                    raise ValueError(f'Expect second numeric, got "{second}"') from None
            if second < 0:
                raise ValueError(f'Second must >=0 , got {second}')
            return second, second
    elif isinstance(second, (int, float)):
        if second < 0:
            raise ValueError(f'Second must >=0 , got {second}')
        return second, second
    else:
        raise ValueError(f'Invalid second input, got {second}')

    if isinstance(low, str):
        if '.' in low:
            try:
                low = float(low)
            except (ValueError, TypeError):
                raise ValueError(f'Low bound and high bound must be numeric, got {second}') from None
        else:
            try:
                low = int(low)
            except (ValueError, TypeError):
                raise ValueError(f'Low bound and high bound must be numeric, got {second}') from None
    if isinstance(high, str):
        if '.' in high:
            try:
                high = float(high)
            except (ValueError, TypeError):
                raise ValueError(f'Low bound and high bound must be numeric, got {second}') from None
        else:
            try:
                high = int(high)
            except (ValueError, TypeError):
                raise ValueError(f'Low bound and high bound must be numeric, got {second}') from None
    if low > high:
        raise ValueError(f'High bound must >= lower bound, got {second}')
    if low < 0 or high < 0:
        raise ValueError(f'Low bound and high bound must >= 0, got {second}')
    return low, high


def random_time(second, n=3, precision=3):
    """
    Args:
        second (int | float | str | tuple | list):
            3, 0.5, "3", "0.1~0.2", (1.5, 2.5), [1, 4], "10~30", "10, 30", "10-30"
            second >= 0
        n (int): The amount of numbers in simulation. Default to 3.
        precision (int): Decimals.

    Returns:
        float:
    """
    low, high = parse_second(second)
    if low < high:
        multiply = 10 ** precision
        value = random_normal_distribution_int(low * multiply, high * multiply, n) / multiply
        return round(value, precision)
    else:
        return round(float(low), precision)


class ServerTime:
    def __init__(self, tz):
        """
        Args:
            tz (str | int | timedelta | timezone): -7 for timedelta(hours=-7)
                "8" for timedelta(hours=8)
                "09:30" for timedelta(hours=9, minutes=30)
        """
        self.tz = parse_timezone(tz)

    def now(self):
        """
        datetime.now in server timezone

        Returns:
            datetime: Current time in server timezone
        """
        # getnow(self.tz)
        return datetime.now(self.tz).replace(microsecond=0)

    @staticmethod
    def _is_valid_date(y, month, d):
        """
        Args:
            y (int): Year
            month (int): Month
            d (int): Day

        Returns:
            bool: True if valid
        """
        # Check if the date is valid for the given month (handles Feb 30th etc.)
        if not 1 <= month <= 12:
            return False

        last_day = calendar.monthrange(y, month)[1]
        return 1 <= d <= last_day

    def _get_occurrence(self, cond, now, direction=1):
        """
        Calculates the next (direction=1) or last (direction=-1) occurrence of a single condition.

        Check order: monthday → weekday → hour → minute → None.

        Args:
            cond (ServerUpdateCondition): Condition to check
            now (datetime): Base datetime in the server timezone
            direction (int): 1 for next occurrence, -1 for last occurrence. Defaults to 1.

        Returns:
            datetime | None: The calculated occurrence time, or None if the condition is empty
        """
        # 1. 每月更新
        if cond.monthday is not None:
            h, m = cond.hour or 0, cond.minute or 0
            curr_y, curr_m = now.year, now.month
            for i in range(12):
                target_m = curr_m + i * direction
                adj_y = curr_y + (target_m - 1) // 12
                adj_m = (target_m - 1) % 12 + 1
                if self._is_valid_date(adj_y, adj_m, cond.monthday):
                    dt = datetime(adj_y, adj_m, cond.monthday, h, m, tzinfo=self.tz)
                    if direction == 1 and dt > now:
                        return dt
                    if direction == -1 and dt < now:
                        return dt
            raise ValueError(f"Invalid monthday setting: {cond.monthday}")

        # 2. 每周更新
        if cond.weekday is not None:
            h, m = cond.hour or 0, cond.minute or 0
            current_wkday = now.isoweekday()
            if direction == 1:
                days_diff = (cond.weekday - current_wkday) % 7
            else:
                days_diff = -((current_wkday - cond.weekday) % 7)
            dt = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=days_diff)
            # Note that we use `dt > now` to find occurrence in the future, and `dt <= now` for the past
            # Since now() removed microseconds, the real time is likely to passed `now`
            # so `now` is included in the past, and not included in the future
            if direction == 1 and dt <= now:
                dt += timedelta(days=7)
            elif direction == -1 and dt > now:
                dt -= timedelta(days=7)
            return dt

        # 3. 每日更新 (at a specific hour)
        if cond.hour is not None:
            h, m = cond.hour, cond.minute or 0
            dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if direction == 1 and dt <= now:
                dt += timedelta(days=1)
            elif direction == -1 and dt > now:
                dt -= timedelta(days=1)
            return dt

        # 4. Every hour at this minute (hour=None, minute is set)
        if cond.minute is not None:
            m = cond.minute
            dt = now.replace(minute=m, second=0, microsecond=0)
            if direction == 1 and dt <= now:
                dt += timedelta(hours=1)
            elif direction == -1 and dt > now:
                dt -= timedelta(hours=1)
            return dt

        # 5. Empty condition — nothing to compute
        return None

    def get_next_update(self, server_updates: TYPE_SERVER_UPDATE_INPUT):
        """
        Args:
            server_updates: Server update inputs

        Returns:
            datetime: Next update time
        """
        now = self.now()
        updates = parse_server_update_list(server_updates)

        # Calculate the next occurrence for all configurations and take the minimum
        candidates = [self._get_occurrence(cond, now, direction=1) for cond in updates]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            raise ValueError('No valid candidates from server update conditions')

        return min(candidates).astimezone()

    def get_last_update(self, server_updates: TYPE_SERVER_UPDATE_INPUT):
        """
        Args:
            server_updates: Server update inputs

        Returns:
            datetime: Last update time
        """
        now = self.now()
        updates = parse_server_update_list(server_updates)

        # Calculate the last occurrence for all configurations and take the maximum
        candidates = [self._get_occurrence(cond, now, direction=-1) for cond in updates]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            raise ValueError('No valid candidates from server update conditions')

        return max(candidates).astimezone()

    def get_delta_to_update(self, server_updates):
        """
        Returns the timedelta to the nearest server update (before or after now).

        Args:
            server_updates: Server update inputs

        Returns:
            timedelta: Time delta to the nearest update.
                Positive if the nearest update is after now,
                negative if before now.

        Raises:
            ValueError: If no valid update conditions produce a candidate.
        """
        now = self.now()
        updates = parse_server_update_list(server_updates)

        # Collect both next and last occurrences for each condition
        candidates = []
        for cond in updates:
            next_oc = self._get_occurrence(cond, now, direction=1)
            if next_oc is not None:
                candidates.append(next_oc)
            last_oc = self._get_occurrence(cond, now, direction=-1)
            if last_oc is not None:
                candidates.append(last_oc)

        if not candidates:
            raise ValueError('No valid candidates from server update conditions')

        # Pick the datetime closest to now
        nearest = min(candidates, key=lambda dt: abs((dt - now).total_seconds()))
        return nearest - now
