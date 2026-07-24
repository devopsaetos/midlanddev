from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # token.money.create() never wrote back res.member.token_id for members it
    # auto-created (the token_id key was commented out), so token_generated -
    # a field related through token_id - stayed False for every member created
    # this way. That silently broke the Member Name picker's domain on the
    # token form (token_generated=True, file_line_ids=False), which relies on
    # token_id being set. Backfill it here for existing data; new members get
    # it set going forward by the now-uncommented line in create().
    env = api.Environment(cr, SUPERUSER_ID, {})
    tokens = env['token.money'].search([
        ('party_type', '=', 'member'),
        ('partner_id', '!=', False),
        ('token_generated', '=', True),
    ], order='id asc')
    for token in tokens:
        token.partner_id.token_id = token.id
