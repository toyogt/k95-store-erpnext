from k95_store import schema


def after_install():
	schema.run()


def before_migrate():
	from k95_store.store.migrate import snapshot_gate_photos

	snapshot_gate_photos()


def after_migrate():
	from k95_store.store.migrate import backfill_gate_links, clear_gate_photo_snapshot, restore_gate_photos

	restore_gate_photos()
	schema.run()
	backfill_gate_links()
	clear_gate_photo_snapshot()
