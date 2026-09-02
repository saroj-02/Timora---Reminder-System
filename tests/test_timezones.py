"""
Timezone Architecture Tests:
- IANA timezone handling via zoneinfo
- UTC conversion accuracy across key global timezones:
  * Asia/Kolkata (+05:30)
  * America/New_York (EDT/EST, UTC-4/UTC-5)
  * America/Los_Angeles (PDT/PST, UTC-7/UTC-8)
  * Europe/London (BST/GMT, UTC+1/UTC+0)
  * Asia/Tokyo (JST, UTC+9)
  * Australia/Sydney (AEDT/AEST, UTC+11/UTC+10)
- Daylight Saving Time (DST) transitions
- Midnight boundaries
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from app.utils.timezone import (
    format_local,
    get_timezones_for_country,
    is_valid_timezone,
    list_countries,
    local_to_utc,
    utc_to_local,
)

def test_timezone_validation():
    assert is_valid_timezone("Asia/Kolkata") is True
    assert is_valid_timezone("America/New_York") is True
    assert is_valid_timezone("Europe/London") is True
    assert is_valid_timezone("Asia/Tokyo") is True
    assert is_valid_timezone("Australia/Sydney") is True
    assert is_valid_timezone("Invalid/Timezone_Name") is False

def test_country_mapping():
    countries = list_countries()
    assert "India" in countries
    assert "United States" in countries
    assert "United Kingdom" in countries
    assert "Japan" in countries
    assert "Australia" in countries

    india_tzs = get_timezones_for_country("India")
    assert "Asia/Kolkata" in india_tzs

    us_tzs = get_timezones_for_country("United States")
    assert "America/New_York" in us_tzs
    assert "America/Los_Angeles" in us_tzs

def test_asia_kolkata_conversion():
    # 2026-09-10 20:30:00 IST -> 2026-09-10 15:00:00 UTC (IST is UTC+5:30)
    local_dt = datetime(2026, 9, 10, 20, 30, 0)
    utc_dt = local_to_utc(local_dt, "Asia/Kolkata")

    assert utc_dt.year == 2026
    assert utc_dt.month == 9
    assert utc_dt.day == 10
    assert utc_dt.hour == 15
    assert utc_dt.minute == 0
    assert utc_dt.second == 0
    assert utc_dt.tzinfo == ZoneInfo("UTC")

    # Back to local
    back_local = utc_to_local(utc_dt, "Asia/Kolkata")
    assert back_local.hour == 20
    assert back_local.minute == 30

def test_america_new_york_dst():
    # Summer (EDT is UTC-4): July 15, 2026 at 10:00 AM EDT -> 2:00 PM UTC
    summer_local = datetime(2026, 7, 15, 10, 0, 0)
    summer_utc = local_to_utc(summer_local, "America/New_York")
    assert summer_utc.hour == 14

    # Winter (EST is UTC-5): Dec 15, 2026 at 10:00 AM EST -> 3:00 PM UTC
    winter_local = datetime(2026, 12, 15, 10, 0, 0)
    winter_utc = local_to_utc(winter_local, "America/New_York")
    assert winter_utc.hour == 15

def test_london_dst():
    # Summer (BST is UTC+1): June 1, 2026 at 12:00 PM -> 11:00 AM UTC
    summer_local = datetime(2026, 6, 1, 12, 0, 0)
    summer_utc = local_to_utc(summer_local, "Europe/London")
    assert summer_utc.hour == 11

    # Winter (GMT is UTC+0): January 1, 2026 at 12:00 PM -> 12:00 PM UTC
    winter_local = datetime(2026, 1, 1, 12, 0, 0)
    winter_utc = local_to_utc(winter_local, "Europe/London")
    assert winter_utc.hour == 12

def test_tokyo_no_dst():
    # Tokyo is always UTC+9
    local_dt = datetime(2026, 5, 20, 9, 0, 0)
    utc_dt = local_to_utc(local_dt, "Asia/Tokyo")
    assert utc_dt.hour == 0

def test_sydney_dst():
    # Sydney summer (AEDT is UTC+11): January 15 at 11:00 AM -> 00:00 UTC
    summer_local = datetime(2026, 1, 15, 11, 0, 0)
    summer_utc = local_to_utc(summer_local, "Australia/Sydney")
    assert summer_utc.hour == 0

    # Sydney winter (AEST is UTC+10): July 15 at 10:00 AM -> 00:00 UTC
    winter_local = datetime(2026, 7, 15, 10, 0, 0)
    winter_utc = local_to_utc(winter_local, "Australia/Sydney")
    assert winter_utc.hour == 0

def test_midnight_boundary_crossing():
    # 2026-09-10 02:00:00 in Tokyo (UTC+9) -> 2026-09-09 17:00:00 UTC (Previous day)
    local_dt = datetime(2026, 9, 10, 2, 0, 0)
    utc_dt = local_to_utc(local_dt, "Asia/Tokyo")
    assert utc_dt.day == 9
    assert utc_dt.hour == 17
