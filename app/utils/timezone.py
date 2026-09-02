"""
Timora – Timezone Utilities

Central timezone utilities for the application.

Architecture:
- Store reminder timestamps in UTC.
- Store the user's preferred IANA timezone.
- Convert UTC <-> local timezone only at the UI/service boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones


# ============================================================
# Constants
# ============================================================

DEFAULT_TIMEZONE = "UTC"

# Timezone namespaces that are not useful for normal users.
EXCLUDED_PREFIXES = (
    "Etc/",
    "posix/",
    "right/",
)

# Common country list used by the profile/timezone setup page.
# This is intentionally kept independent from timezone selection.
COUNTRIES: tuple[str, ...] = (
    "Afghanistan",
    "Albania",
    "Algeria",
    "Andorra",
    "Angola",
    "Antigua and Barbuda",
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahamas",
    "Bahrain",
    "Bangladesh",
    "Barbados",
    "Belarus",
    "Belgium",
    "Belize",
    "Benin",
    "Bhutan",
    "Bolivia",
    "Bosnia and Herzegovina",
    "Botswana",
    "Brazil",
    "Brunei",
    "Bulgaria",
    "Burkina Faso",
    "Burundi",
    "Cabo Verde",
    "Cambodia",
    "Cameroon",
    "Canada",
    "Central African Republic",
    "Chad",
    "Chile",
    "China",
    "Colombia",
    "Comoros",
    "Congo",
    "Costa Rica",
    "Croatia",
    "Cuba",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Djibouti",
    "Dominica",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Equatorial Guinea",
    "Eritrea",
    "Estonia",
    "Eswatini",
    "Ethiopia",
    "Fiji",
    "Finland",
    "France",
    "Gabon",
    "Gambia",
    "Georgia",
    "Germany",
    "Ghana",
    "Greece",
    "Grenada",
    "Guatemala",
    "Guinea",
    "Guinea-Bissau",
    "Guyana",
    "Haiti",
    "Honduras",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iran",
    "Iraq",
    "Ireland",
    "Israel",
    "Italy",
    "Jamaica",
    "Japan",
    "Jordan",
    "Kazakhstan",
    "Kenya",
    "Kiribati",
    "Kuwait",
    "Kyrgyzstan",
    "Laos",
    "Latvia",
    "Lebanon",
    "Lesotho",
    "Liberia",
    "Libya",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Madagascar",
    "Malawi",
    "Malaysia",
    "Maldives",
    "Mali",
    "Malta",
    "Marshall Islands",
    "Mauritania",
    "Mauritius",
    "Mexico",
    "Micronesia",
    "Moldova",
    "Monaco",
    "Mongolia",
    "Montenegro",
    "Morocco",
    "Mozambique",
    "Myanmar",
    "Namibia",
    "Nauru",
    "Nepal",
    "Netherlands",
    "New Zealand",
    "Nicaragua",
    "Niger",
    "Nigeria",
    "North Korea",
    "North Macedonia",
    "Norway",
    "Oman",
    "Pakistan",
    "Palau",
    "Palestine",
    "Panama",
    "Papua New Guinea",
    "Paraguay",
    "Peru",
    "Philippines",
    "Poland",
    "Portugal",
    "Qatar",
    "Romania",
    "Russia",
    "Rwanda",
    "Saint Kitts and Nevis",
    "Saint Lucia",
    "Saint Vincent and the Grenadines",
    "Samoa",
    "San Marino",
    "Sao Tome and Principe",
    "Saudi Arabia",
    "Senegal",
    "Serbia",
    "Seychelles",
    "Sierra Leone",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "Solomon Islands",
    "Somalia",
    "South Africa",
    "South Korea",
    "South Sudan",
    "Spain",
    "Sri Lanka",
    "Sudan",
    "Suriname",
    "Sweden",
    "Switzerland",
    "Syria",
    "Taiwan",
    "Tajikistan",
    "Tanzania",
    "Thailand",
    "Timor-Leste",
    "Togo",
    "Tonga",
    "Trinidad and Tobago",
    "Tunisia",
    "Turkey",
    "Turkmenistan",
    "Tuvalu",
    "Uganda",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Uruguay",
    "Uzbekistan",
    "Vanuatu",
    "Vatican City",
    "Venezuela",
    "Vietnam",
    "Yemen",
    "Zambia",
    "Zimbabwe",
)


# ============================================================
# Country utilities
# ============================================================


def list_countries() -> list[str]:
    """
    Return all supported countries.

    The country is profile information and does not restrict
    the available timezone list.
    """

    return list(COUNTRIES)


# ============================================================
# Timezone utilities
# ============================================================


def list_timezones() -> list[str]:
    """
    Return all useful IANA timezones available in the
    installed Python timezone database.

    This is dynamic and therefore avoids maintaining a
    manually hardcoded timezone list.
    """

    zones: set[str] = set()

    for zone in available_timezones():

        if zone.startswith(EXCLUDED_PREFIXES):
            continue

        zones.add(zone)

    # Always guarantee UTC exists.
    zones.add(DEFAULT_TIMEZONE)

    return sorted(zones)


def is_valid_timezone(timezone_name: str) -> bool:
    """
    Check whether a timezone is a valid IANA timezone.
    """

    if not isinstance(timezone_name, str):
        return False

    if not timezone_name:
        return False

    if timezone_name == DEFAULT_TIMEZONE:
        return True

    try:
        ZoneInfo(timezone_name)
        return True

    except Exception:
        return False


def ensure_timezone(
    timezone_name: str | None,
) -> str:
    """
    Return a valid timezone.

    Invalid or missing values fall back to UTC.
    """

    if timezone_name and is_valid_timezone(
        timezone_name
    ):
        return timezone_name

    return DEFAULT_TIMEZONE


# ============================================================
# Current time utilities
# ============================================================


def now_utc() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(timezone.utc)


def now_local(
    timezone_name: str | None,
) -> datetime:
    """
    Return the current local datetime for the given timezone.
    """

    safe_timezone = ensure_timezone(
        timezone_name
    )

    return datetime.now(
        ZoneInfo(safe_timezone)
    )


# ============================================================
# UTC <-> Local conversion
# ============================================================


def local_to_utc(
    local_datetime: datetime,
    timezone_name: str | None,
) -> datetime:
    """
    Convert a local timezone-aware or naive datetime
    into UTC.

    Naive datetimes are interpreted as belonging to the
    supplied timezone.
    """

    safe_timezone = ensure_timezone(
        timezone_name
    )

    local_zone = ZoneInfo(
        safe_timezone
    )

    if local_datetime.tzinfo is None:
        local_datetime = local_datetime.replace(
            tzinfo=local_zone
        )
    else:
        local_datetime = local_datetime.astimezone(
            local_zone
        )

    return local_datetime.astimezone(
        timezone.utc
    )


def utc_to_local(
    utc_datetime: datetime,
    timezone_name: str | None,
) -> datetime:
    """
    Convert a UTC datetime into the user's local timezone.
    """

    safe_timezone = ensure_timezone(
        timezone_name
    )

    local_zone = ZoneInfo(
        safe_timezone
    )

    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(
            tzinfo=timezone.utc
        )
    else:
        utc_datetime = utc_datetime.astimezone(
            timezone.utc
        )

    return utc_datetime.astimezone(
        local_zone
    )


# ============================================================
# Formatting utilities
# ============================================================


def format_local(
    utc_datetime: datetime,
    timezone_name: str | None,
    fmt: str = "%Y-%m-%d %H:%M",
) -> str:
    """
    Convert UTC datetime to local timezone and format it.
    """

    local_datetime = utc_to_local(
        utc_datetime,
        timezone_name,
    )

    return local_datetime.strftime(
        fmt
    )


def get_timezone_offset(
    timezone_name: str | None,
    at_datetime: datetime | None = None,
) -> str:
    """
    Return the current UTC offset for a timezone.

    Examples:
        +05:30
        +00:00
        -04:00
    """

    safe_timezone = ensure_timezone(
        timezone_name
    )

    zone = ZoneInfo(
        safe_timezone
    )

    if at_datetime is None:
        at_datetime = datetime.now(
            zone
        )
    elif at_datetime.tzinfo is None:
        at_datetime = at_datetime.replace(
            tzinfo=zone
        )
    else:
        at_datetime = at_datetime.astimezone(
            zone
        )

    offset = at_datetime.utcoffset()

    if offset is None:
        return "+00:00"

    total_seconds = int(
        offset.total_seconds()
    )

    sign = "+" if total_seconds >= 0 else "-"

    total_seconds = abs(
        total_seconds
    )

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    return (
        f"{sign}"
        f"{hours:02d}:"
        f"{minutes:02d}"
    )


def get_timezone_display_name(
    timezone_name: str | None,
) -> str:
    """
    Return a friendly timezone display string.

    Example:
        Asia/Kolkata (UTC +05:30)
    """

    safe_timezone = ensure_timezone(
        timezone_name
    )

    offset = get_timezone_offset(
        safe_timezone
    )

    return (
        f"{safe_timezone} "
        f"(UTC {offset})"
    )


# ============================================================
# Backward compatibility
# ============================================================


def get_timezones_for_country(
    country: str | None,
) -> list[str]:
    """
    Backward-compatible helper.

    IMPORTANT:
    Timezones are no longer restricted by country.

    This function intentionally returns the complete global
    timezone list so older parts of the application do not
    break while the UI is migrated to list_timezones().
    """

    _ = country

    return list_timezones()