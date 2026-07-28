"""
Centralized owner/page registry.

Single source of truth for every "page"/"owner" value the system
knows about. Before this module existed, the set {"mahabucha",
"muteteam", "muteteam_ceremony"} was duplicated as a hardcoded
tuple/if-elif-chain in several separate places: core/schemas.py's
PAGE_OWNERS, core/clients/facebook_client.py's get_page_token,
core/services/messenger_service.py's process_message routing,
core/services/image_cache_service.py's CACHED_FILES/update_file_list,
core/services/notification_service.py's page-name/tray-count
branching, and core/blueprints/messenger.py's manual-send page
lookup. Adding an owner meant touching all six. Now it means adding
one entry here (plus its env vars in config.py).

(core/clients/line_client.py intentionally keeps its own
owner->env-var-name mapping rather than reading page_token/line
fields from here -- several tests mock.patch.object() its individual
LINE_CHANNEL_ACCESS_TOKEN_* / LINE_GROUP_ID_* module constants
directly, which requires those names to be looked up dynamically at
call time rather than frozen into a registry at import time.)

`style` distinguishes the two existing message-handling flows:
  - "mahabucha": process_ceremony_flow() handles Messenger replies
    directly by owner_key; no tray_count line in print-queue LINE
    notifications.
  - "muteteam": process_muteteam()'s own 12-digit-code flow; includes
    the tray_count line.
New owners that should "work like มหาบูชา" get style="mahabucha".

`page_id`/`page_token` are None for owners with no Facebook page of
their own -- muteteam_ceremony piggybacks on muteteam's FB page
(routed there by message content, not by a separate webhook page_id).
"""
from config import (
    MAHABUCHA_PAGE_ID, MAHABUCHA_TOKEN,
    MUTETEAM_PAGE_ID, MUTETEAM_TOKEN,
    LAOS_PAGE_ID, LAOS_TOKEN,
    RATCHAPRASONG_PAGE_ID, RATCHAPRASONG_TOKEN,
)


class Owner:
    def __init__(self, key, display_name, page_id, page_token, style):
        self.key = key
        self.display_name = display_name
        self.page_id = page_id
        self.page_token = page_token
        self.style = style  # "mahabucha" | "muteteam"


OWNERS = {
    "mahabucha": Owner("mahabucha", "มหาบูชา", MAHABUCHA_PAGE_ID, MAHABUCHA_TOKEN, "mahabucha"),
    "muteteam": Owner("muteteam", "มูเตทีม", MUTETEAM_PAGE_ID, MUTETEAM_TOKEN, "muteteam"),
    "muteteam_ceremony": Owner("muteteam_ceremony", "มูเตทีม (งานพิธี)", None, None, "mahabucha"),
    "laos": Owner("laos", "สยามคเณศ (ลาว)", LAOS_PAGE_ID, LAOS_TOKEN, "mahabucha"),
    "ratchaprasong": Owner("ratchaprasong", "สยามคเณศ (ราชประสงค์)", RATCHAPRASONG_PAGE_ID, RATCHAPRASONG_TOKEN, "mahabucha"),
}

PAGE_OWNERS = tuple(OWNERS.keys())

MAHABUCHA_STYLE_OWNERS = tuple(o.key for o in OWNERS.values() if o.style == "mahabucha")


def find_owner_by_page_id(page_id):
    """Returns the owner key whose Facebook page_id matches, or None."""
    for owner in OWNERS.values():
        if owner.page_id and str(page_id) == str(owner.page_id):
            return owner.key
    return None
