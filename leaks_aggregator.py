import aiohttp
import hashlib
from datetime import datetime
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field
import re
from config import settings
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class CheckItem(BaseModel):
    value: str = Field(...)
    type: Union[
        Literal["Email"], Literal["Password_or_login"], Literal["Number"], None
    ] = Field(...)


class LeakInfo(BaseModel):
    site: Optional[str] = None
    breach_date: Optional[datetime] = None


EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_REGEX = re.compile(r"^\+?[0-9]{7,15}$")


def build_check_item(value: str) -> CheckItem:
    s = value.strip()

    if EMAIL_REGEX.match(s):
        return CheckItem(value=s, type="Email")
    if PHONE_REGEX.match(s):
        return CheckItem(value=s, type="Number")
    return CheckItem(value=s, type="Password_or_login")


_PWNED_SESSION: aiohttp.ClientSession | None = None
_XON_SESSION: aiohttp.ClientSession | None = None
_LEAKLOOKUP_SESSION: aiohttp.ClientSession | None = None


# ================================
# SETUP / EXIT: Pwned Passwords
# ================================
async def setup_pwned_session():
    global _PWNED_SESSION
    if _PWNED_SESSION is None:
        _PWNED_SESSION = aiohttp.ClientSession()


async def exit_pwned_session():
    global _PWNED_SESSION
    if _PWNED_SESSION:
        await _PWNED_SESSION.close()
        _PWNED_SESSION = None
        logging.info("Pwned API client closed.")


# ================================
# SETUP / EXIT: XposedOrNot
# ================================
async def setup_xon_session():
    global _XON_SESSION
    if _XON_SESSION is None:
        _XON_SESSION = aiohttp.ClientSession()


async def exit_xon_session():
    global _XON_SESSION
    if _XON_SESSION:
        await _XON_SESSION.close()
        _XON_SESSION = None
        logging.info("XposedOrNot API client closed.")


# ================================
# SETUP / EXIT: Leak-Lookup
# ================================
async def setup_leaklookup_session():
    global _LEAKLOOKUP_SESSION
    if _LEAKLOOKUP_SESSION is None:
        _LEAKLOOKUP_SESSION = aiohttp.ClientSession()


async def exit_leaklookup_session():
    global _LEAKLOOKUP_SESSION
    if _LEAKLOOKUP_SESSION:
        await _LEAKLOOKUP_SESSION.close()
        _LEAKLOOKUP_SESSION = None
        logging.info("Leak-Lookup API client closed.")


# ================================
# CHECK: Pwned Passwords
# ================================
async def check_pwned_password(password: str) -> List[LeakInfo]:
    await setup_pwned_session()
    if _PWNED_SESSION is None:
        return []

    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    url = f"https://api.pwnedpasswords.com/range/{prefix}"

    async with _PWNED_SESSION.get(url) as resp:
        if resp.status != 200:
            return []
        text = await resp.text()

    for line in text.splitlines():
        hash_suffix, count = line.split(":")
        if hash_suffix == suffix:
            return [LeakInfo(site=None, breach_date=None)]
    return []


# ================================
# CHECK: XposedOrNot
# ================================
async def check_xposedornot(email: str) -> List[LeakInfo]:
    await setup_xon_session()
    if _XON_SESSION is None:
        return []

    url = f"https://api.xposedornot.com/v1/check-email/{email}"
    async with _XON_SESSION.get(url) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()

    leaks: List[LeakInfo] = []

    for breach in data.get("breaches", []):
        leaks.append(
            LeakInfo(
                site=breach.get("name", None),
                breach_date=(
                    datetime.fromisoformat(breach["date"])
                    if breach.get("date")
                    else None
                ),
            )
        )

    return leaks


# ================================
# CHECK: Leak-Lookup
# ================================
async def check_leaklookup(query: str) -> List[LeakInfo]:
    await setup_leaklookup_session()
    if _LEAKLOOKUP_SESSION is None:
        return []

    url = "https://leak-lookup.com/api/search"
    payload = {"key": settings.LEAKLOOKUP_PUBLIC_KEY, "query": query}

    async with _LEAKLOOKUP_SESSION.post(url, json=payload) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()

    leaks: List[LeakInfo] = []

    for name in data.get("found", []):
        leaks.append(LeakInfo(site=name))

    return leaks


async def search_leaks(item: CheckItem | str) -> List[LeakInfo]:
    results: List[LeakInfo] = []

    if isinstance(item, str):
        item = build_check_item(item)

    if item.type == "Password_or_login":
        results += await check_pwned_password(item.value)

    if item.type == "Email":
        results += await check_xposedornot(item.value)
        results += await check_leaklookup(item.value)

    if item.type in ("Password_or_login", "Number"):
        results += await check_leaklookup(item.value)

    return results


async def shutdown_all_clients():
    await exit_pwned_session()
    await exit_xon_session()
    await exit_leaklookup_session()
