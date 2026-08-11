def dependent_after_insert(doc, method=None):
	"""A new dependent starts with an empty allowed_categories child table.

	An empty allowed_categories table means the dependent may use all of the
	guardian's active (shared, guardian-owned) categories until the guardian
	explicitly customizes the list. The guardian's own default categories are
	seeded by the guardian-level path (install.py / doctype/user/hooks.py),
	so no per-dependent seeding happens here.
	"""
	pass
