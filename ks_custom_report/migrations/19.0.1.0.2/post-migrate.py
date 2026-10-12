# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Report models made before: label their hidden x_name field "Record Name" (it was "Name",
    the same as a report column called Name, which gave a warning on every server start)."""
    cr.execute("""
        UPDATE ir_model_fields f
           SET field_description = f.field_description || '{"en_US": "Record Name"}'::jsonb
          FROM ir_model m
         WHERE f.model_id = m.id
           AND m.ks_is_custom_model
           AND f.name = 'x_name'
    """)
