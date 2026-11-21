MODULE = "Store"

ROLES = [
	"Gate Security",
	"Guard",
	"Factory Guard",
	"Gate Entry Editor",
	"Gate Entry Viewer",
	"Store User",
	"Store Manager",
	"Store Auditor",
	"Production Requester",
	"Labelling Requester",
]

LOCATION_TYPES = (
	"storage",
	"rejected",
	"quarantine",
	"dispatch",
	"receiving",
)

ARRIVAL_TYPES = (
	"PO",
	"Invoice",
	"LOCAL",
	"RETURN",
	"COURIER",
)

LOT_STATUSES = (
	"pending_putaway",
	"pending_qc",
	"putaway",
	"partial",
	"consumed",
	"rejected",
	"damaged",
)

QC_PENDING_STATUSES = ("pending_qc",)
HELD_LOT_STATUSES = ("rejected", "damaged")
FROZEN_LOT_STATUSES = HELD_LOT_STATUSES + QC_PENDING_STATUSES
OPENING_LOT_PREFIXES = ("LOT-OPEN-", "LOT-OS-")

# Lot status → warehouses Store Putaway may write to.
PUTAWAY_LOCATION_TYPES = {
	"pending_putaway": ("storage",),
	"pending_qc": ("quarantine",),
	"rejected": ("rejected",),
	"damaged": ("rejected",),
}

RETURNABLE_LOCATION_TYPES = ("storage", "rejected")

MISMATCH_TYPES = (
	"none",
	"damaged",
	"decreased",
	"increased",
	"short_and_damaged",
)

ITEM_CATEGORIES = (
	"ingredient",
	"box_type",
	"cap_type",
	"container",
	"flavour",
	"label_artwork",
	"packaging",
	"other",
)

DEFAULT_EPSILON = 0.0001
DEFAULT_AUTO_APPROVE_PERCENT = 5
DEFAULT_AUTO_APPROVE_QTY = 2
