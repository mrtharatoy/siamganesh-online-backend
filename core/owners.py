"""
Centralized owner/page registry.

Single source of truth for every "page"/"owner" value the system
knows about. Before this module existed, the set {"mahabucha",
"muteteam", "muteteam_ceremony"} was duplicated as a hardcoded
tuple/if-elif-chain in several separate places: core/schemas.py's
PAGE_OWNERS, core/services/image_cache_service.py's CACHED_FILES/update_file_list,
core/services/notification_service.py's page-name/tray-count
branching. Adding an owner now means adding one entry here.

(core/clients/line_client.py intentionally keeps its own
owner->env-var-name mapping rather than reading LINE fields from here
-- several tests mock.patch.object() its individual
LINE_CHANNEL_ACCESS_TOKEN_* / LINE_GROUP_ID_* module constants
directly, which requires those names to be looked up dynamically at
call time rather than frozen into a registry at import time.)

`style` distinguishes owners for print-queue LINE notifications:
  - "mahabucha": no tray_count line.
  - "muteteam": includes the tray_count line.

"""
class Owner:
    def __init__(self, key, display_name, style):
        self.key = key
        self.display_name = display_name
        self.style = style  # "mahabucha" | "muteteam"


OWNERS = {
    "mahabucha": Owner("mahabucha", "มหาบูชา", "mahabucha"),
    "muteteam": Owner("muteteam", "มูเตทีม (รายวัน)", "muteteam"),
    "muteteam_ceremony": Owner("muteteam_ceremony", "มูเตทีม (งานพิธี)", "mahabucha"),
    "laos": Owner("laos", "สยามคเณศ (ลาว)", "mahabucha"),
    "ratchaprasong": Owner("ratchaprasong", "สยามคเณศ (ราชประสงค์)", "mahabucha"),
}

PAGE_OWNERS = tuple(OWNERS.keys())

MAHABUCHA_STYLE_OWNERS = tuple(o.key for o in OWNERS.values() if o.style == "mahabucha")
