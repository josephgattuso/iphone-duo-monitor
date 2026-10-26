import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

PRODUCT_URL = os.getenv(
    "APPLE_PRODUCT_URL",
    "https://www.apple.com/uk/shop/buy-iphone/iphone-duo",
)

POSTCODE = os.getenv("APPLE_POSTCODE", "").strip()
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()

PREFERRED_COLOUR = os.getenv("PREFERRED_COLOUR", "Night Sky").strip()
PREFERRED_STORAGE = os.getenv("PREFERRED_STORAGE", "512GB").strip()

CHECK_ALTERNATIVES = (
    os.getenv("CHECK_ALTERNATIVES", "true").strip().lower() == "true"
)
HEADLESS = os.getenv("HEADLESS", "true").strip().lower() != "false"

COLOURS = ("Night Sky", "Star White")
STORAGE_OPTIONS = ("256GB", "512GB", "1TB", "2TB")

AVAILABLE_PATTERNS = (
    r"\bavailable today\b",
    r"\bavailable tomorrow\b",
    r"\bavailable for pickup\b",
    r"\bpick up today\b",
    r"\bpick up tomorrow\b",
    r"\bready for pickup\b",
    r"\bavailable at\b",
)

UNAVAILABLE_PATTERNS = (
    r"\bcurrently unavailable\b",
    r"\bnot available\b",
    r"\bunavailable for pickup\b",
    r"\bnot eligible for pickup\b",
    r"\bno pickup options\b",
)


@dataclass(frozen=True)
class Variant:
    colour: str
    storage: str

    @property
    def is_preferred(self) -> bool:
        return (
            self.colour.casefold() == PREFERRED_COLOUR.casefold()
            and self.storage.casefold() == PREFERRED_STORAGE.casefold()
        )

    @property
    def label(self) -> str:
        return f"{self.storage} in {self.colour}"


@dataclass(frozen=True)
class StoreAvailability:
    store: str
    status: str
    details: str


def validate_configuration() -> None:
    missing = []

    if not POSTCODE:
        missing.append("APPLE_POSTCODE")

    if not NTFY_TOPIC:
        missing.append("NTFY_TOPIC")

    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment configuration: {names}. "
            "Configure these as GitHub Actions secrets."
        )


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def contains_pattern(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def variant_order() -> list[Variant]:
    preferred = Variant(PREFERRED_COLOUR, PREFERRED_STORAGE)

    if not CHECK_ALTERNATIVES:
        return [preferred]

    variants = [
        Variant(colour, storage)
        for colour in COLOURS
        for storage in STORAGE_OPTIONS
    ]

    if preferred not in variants:
        variants.append(preferred)

    variants.sort(
        key=lambda variant: (
            0
            if variant.is_preferred
            else 1
            if variant.colour.casefold() == PREFERRED_COLOUR.casefold()
            else 2
            if variant.storage.casefold() == PREFERRED_STORAGE.casefold()
            else 3,
            STORAGE_OPTIONS.index(variant.storage)
            if variant.storage in STORAGE_OPTIONS
            else len(STORAGE_OPTIONS),
            COLOURS.index(variant.colour)
            if variant.colour in COLOURS
            else len(COLOURS),
        )
    )

    return variants


def click_first_visible(locator: Locator, timeout: int = 4_000) -> bool:
    for index in range(locator.count()):
        candidate = locator.nth(index)

        try:
            if candidate.is_visible():
                candidate.click(timeout=timeout)
                return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return False


def accept_cookies(page: Page) -> None:
    for label in ("Accept All", "Accept all", "Allow All", "Continue"):
        button = page.get_by_role(
            "button",
            name=re.compile(rf"^{re.escape(label)}$", re.IGNORECASE),
        )

        if click_first_visible(button, timeout=2_000):
            page.wait_for_timeout(500)
            return


def select_option(page: Page, value: str) -> bool:
    candidates = (
        page.get_by_text(value, exact=True),
        page.get_by_label(re.compile(re.escape(value), re.IGNORECASE)),
        page.get_by_role(
            "button",
            name=re.compile(re.escape(value), re.IGNORECASE),
        ),
        page.get_by_role(
            "radio",
            name=re.compile(re.escape(value), re.IGNORECASE),
        ),
    )

    for candidate in candidates:
        if click_first_visible(candidate):
            page.wait_for_timeout(1_000)
            return True

    return False


def open_pickup_search(page: Page) -> bool:
    name_pattern = re.compile(
        r"check availability|pick up from store|pickup",
        re.IGNORECASE,
    )

    controls = (
        page.get_by_role("button", name=name_pattern),
        page.get_by_role("link", name=name_pattern),
        page.get_by_text(name_pattern),
    )

    for control in controls:
        if click_first_visible(control, timeout=6_000):
            page.wait_for_timeout(2_000)
            return True

    return False


def enter_postcode(page: Page) -> bool:
    postcode_fields = (
        page.get_by_label(
            re.compile(r"postcode|postal code|location", re.IGNORECASE)
        ),
        page.get_by_placeholder(
            re.compile(r"postcode|postal code|location", re.IGNORECASE)
        ),
        page.locator('input[name*="postal" i]'),
        page.locator('input[name*="postcode" i]'),
        page.locator('input[autocomplete="postal-code"]'),
    )

    for fields in postcode_fields:
        for index in range(fields.count()):
            field = fields.nth(index)

            try:
                if not field.is_visible():
                    continue

                field.fill(POSTCODE, timeout=5_000)
                field.press("Enter")
                page.wait_for_timeout(5_000)
                return True
            except Exception:
                continue

    return False


def visible_store_containers(page: Page) -> list[Locator]:
    """Return visible page elements that appear to contain store stock data."""
    locator_candidates = (
        page.locator(
            '[data-autom*="store" i], '
            '[data-testid*="store" i], '
            '[class*="store-card" i], '
            '[class*="storeitem" i], '
            '[class*="store-item" i]'
        ),
        page.get_by_role("listitem"),
        page.locator("article"),
    )

    for locator in locator_candidates:
        visible: list[Locator] = []

        for index in range(locator.count()):
            item = locator.nth(index)

            try:
                text = normalise(item.inner_text(timeout=2_000))

                if not item.is_visible() or not text:
                    continue

                availability_language = (
                    contains_pattern(text, AVAILABLE_PATTERNS)
                    or contains_pattern(text, UNAVAILABLE_PATTERNS)
                    or re.search(r"\bpickup\b", text, re.IGNORECASE)
                )

                if availability_language:
                    visible.append(item)
            except Exception:
                continue

        if visible:
            return visible

    return []


def infer_store_name(container: Locator, full_text: str) -> str:
    headings = container.get_by_role("heading")

    for index in range(headings.count()):
        try:
            name = normalise(headings.nth(index).inner_text(timeout=1_500))
            if name:
                return name
        except Exception:
            continue

    lines = [normalise(line) for line in full_text.splitlines() if normalise(line)]
    ignored = re.compile(
        r"available|unavailable|pickup|directions|details|today|tomorrow",
        re.IGNORECASE,
    )

    for line in lines:
        if len(line) <= 100 and not ignored.search(line):
            return line

    return "Nearby Apple Store"


def parse_store_results(page: Page) -> list[StoreAvailability]:
    stores: list[StoreAvailability] = []

    for container in visible_store_containers(page):
        try:
            raw_text = container.inner_text(timeout=3_000)
        except Exception:
            continue

        text = normalise(raw_text)
        unavailable = contains_pattern(text, UNAVAILABLE_PATTERNS)
        available = contains_pattern(text, AVAILABLE_PATTERNS) and not unavailable

        if not available:
            continue

        stores.append(
            StoreAvailability(
                store=infer_store_name(container, raw_text),
                status="available",
                details=text[:500],
            )
        )

    unique: dict[str, StoreAvailability] = {}

    for store in stores:
        unique[store.store.casefold()] = store

    return list(unique.values())


def check_variant(page: Page, variant: Variant) -> list[StoreAvailability]:
    page.goto(
        PRODUCT_URL,
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    page.wait_for_timeout(2_000)
    accept_cookies(page)

    colour_selected = select_option(page, variant.colour)
    storage_selected = select_option(page, variant.storage)

    if not colour_selected or not storage_selected:
        return []

    if not open_pickup_search(page):
        return []

    if not enter_postcode(page):
        return []

    return parse_store_results(page)


def send_notification(
    variant: Variant,
    stores: list[StoreAvailability],
) -> None:
    match_type = "PREFERRED MATCH" if variant.is_preferred else "ALTERNATIVE"

    store_lines = "\n".join(
        f"• {store.store}: {store.details}" for store in stores
    )

    message = (
        f"{match_type}\n"
        f"iPhone Duo {variant.label} appears available for pickup.\n\n"
        f"{store_lines}\n\n"
        "Open Apple to confirm availability and place the order."
    )

    request = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": f"iPhone Duo pickup: {match_type}",
            "Priority": "max" if variant.is_preferred else "high",
            "Tags": "iphone,shopping,white_check_mark",
            "Click": PRODUCT_URL,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main() -> int:
    validate_configuration()
    matches: list[tuple[Variant, list[StoreAvailability]]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            locale="en-GB",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()

        for variant in variant_order():
            try:
                stores = check_variant(page, variant)
                if stores:
                    matches.append((variant, stores))
            except Exception:
                # Avoid exposing postcode or nearby-store details in public logs.
                continue

        browser.close()

    for variant, stores in matches:
        send_notification(variant, stores)

    if matches:
        print("Stock check completed. Private notification sent.")
    else:
        print("Stock check completed. No matching pickup stock detected.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Do not print environment values or page content.
        print(f"Monitor failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
