from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # Member shadow partners used to be tagged with the member's own company_id,
    # which made Odoo's base multi-company rule on res.partner block access to
    # that Contact from every other company. Members are invoiced/paid from
    # multiple companies, so their shadow partner must stay company-agnostic.
    env = api.Environment(cr, SUPERUSER_ID, {})
    partners = env['res.member'].search([('partner_id', '!=', False)]).mapped('partner_id')
    partners.filtered(lambda p: p.company_id).write({'company_id': False})
