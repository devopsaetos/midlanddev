# -*- coding: utf-8 -*-
import base64
from odoo.exceptions import AccessError, ValidationError
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _


class MaintenanceElectricityInvoicesWizard(models.TransientModel):
    _name = 'maintenance.electricity.invoices.wizard'
    _description = 'Maintenance Electricity Invoices Wizard'

    till_date = fields.Date(string="Till Date")
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('society_id.id','=',society_id)]")
    sector_ids = fields.Many2many('sector', domain="[('society_id.id', '=', society_id), ('phase_id.id', '=', phase_id)]")
    category_id = fields.Many2one('plot.category', 'Category')
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product')
    unit_class_id = fields.Many2one('unit.class')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    street_id = fields.Many2one('street', string='Street', domain="[('sector_id', 'in', sector_ids)]")
    house_id = fields.Many2one('plot.inventory', string='House',
                               domain="[('society_id', '=', society_id), ('phase_id', '=', phase_id), ('street_id', '=?', street_id)]")
    file_ids = fields.Many2many('file', string='Files')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def generate_invoices(self):
        charges_model = self.env['maintenance.charges']
        maintenance_product = charges_model._get_maintenance_charges_product_id()
        society_product = charges_model._get_society_charges_product_id()
        if not maintenance_product or not society_product:
            raise ValidationError(_(
                'Set the Maintenance Charges Product and the Service Charges Product first '
                '(Maintenance Charges > Configuration > Settings).'))
        if not self.env.company.account_journal_id:
            raise ValidationError(_(
                'Set the Maintenance Invoice Journal for %s first '
                '(Maintenance Charges > Configuration > Settings).') % self.env.company.name)
        created = self.env['account.move']
        skipped_existing, no_rule = [], []
        for rec in self:
            if rec.product_id not in (maintenance_product, society_product):
                raise ValidationError(_('Charge Type must be "%s" or "%s".') % (
                    maintenance_product.display_name, society_product.display_name))
            invoice_type = 'maintenance_charges' if rec.product_id == maintenance_product else 'society_charges'
            month_first_day = rec.till_date.replace(day=1)
            month_last_day = month_first_day + relativedelta(months=1, days=-1)
            if rec.file_ids or rec.house_id:
                # explicitly picked files / house are billed even when the file is still Draft
                picked = rec.file_ids | (rec.house_id._get_maintenance_file() if rec.house_id else self.env['file'])
                domain = [('id', 'in', picked.ids)]
            else:
                domain = [('society_id', '=', rec.society_id.id),
                          ('phase_id', '=', rec.phase_id.id),
                          ('category_id', '=', rec.category_id.id),
                          ('unit_class_id', '=', rec.unit_class_id.id),
                          ('membership_id', '!=', False)]
                if rec.sector_ids:
                    domain.append(('sector_id', 'in', rec.sector_ids.ids))
                if rec.street_id:
                    domain.append(('street_id', '=', rec.street_id.id))
                draft_files = self.env['file'].search_count(domain + [('file_status', '=', 'draft')])
                domain.append(('file_status', '!=', 'draft'))
            files = self.env['file'].search(domain)
            if not files:
                msg = _('No files match these filters.')
                if not (rec.file_ids or rec.house_id) and draft_files:
                    msg += ' ' + _('%s matching file(s) are still in Draft status and are skipped; '
                                   'pick them in "Files" to bill them anyway.') % draft_files
                raise ValidationError(msg)
            charge_lines = self.env['maintenance.charges.line'].sudo().search(
                [('category_id', '=', rec.category_id.id),
                 ('unit_class_id', '=', rec.unit_class_id.id),
                 ('maintenance_charges_id.society_id.company_id', '=', self.env.company.id)])
            for file_rec in files:
                already = self.env['account.move.line'].search_count([
                    ('product_id', '=', rec.product_id.id),
                    ('move_id.partner_id', '=', file_rec.membership_id.partner_id.id),
                    ('move_id.state', '=', 'posted'),
                    ('move_id.date', '>=', month_first_day),
                    ('move_id.date', '<=', month_last_day),
                    ('move_id.file_ids', '=', file_rec.id)
                ])
                if already:
                    skipped_existing.append(file_rec.display_name)
                    continue
                marla = round(file_rec.unit_category_type_id.area_marla)
                in_range = charge_lines.filtered(lambda l: l.from_no <= marla <= l.to_no)
                charge_line = (in_range.filtered(
                    lambda l: l.maintenance_charges_id.society_id == file_rec.society_id) or in_range)[:1]
                rule = charge_line.maintenance_charges_type_id.maintenance_charges_type_line_ids.filtered(
                    lambda l: l.product_id == rec.product_id)[:1]
                if not rule:
                    no_rule.append('%s (%s marla)' % (file_rec.display_name, marla))
                    continue
                # exemption that is active in the billed month
                exemption = self.env['maintenance.exemption.history'].search(
                    [('file_id', '=', file_rec.id), ('exemption_state', '=', 'active'),
                     ('product_id', '=', rec.product_id.id),
                     ('from_date', '<=', month_last_day), ('to_date', '>=', month_first_day)], limit=1)
                amount = rule.amount
                if exemption:
                    if exemption.exemption_nature == 'full':
                        continue
                    if exemption.exemption_type == 'percentage' and exemption.exemption_percent:
                        amount = rule.amount / 100 * (100 - exemption.exemption_percent)
                    elif exemption.exemption_type == 'fixed_amount' and exemption.exemption_amount:
                        amount = rule.amount - exemption.exemption_amount
                installment_number = file_rec.maintenance_history_ids[
                                         -1].installment_number + 1 if file_rec.maintenance_history_ids else 1
                invoice = self.env['account.move'].create({
                    'partner_id': file_rec.membership_id.partner_id.id,
                    'move_type': 'out_invoice',
                    'maintenance_charges_id': charge_line.maintenance_charges_id.id,
                    'invoice_date': month_first_day,
                    'journal_id': self.env.company.account_journal_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': rec.product_id.id,
                        'name': rec.product_id.name,
                        'account_id': rec.product_id.property_account_income_id.id,
                        'price_unit': amount,
                        # the charge type amount is the bill amount (same as Monthly Bills): no sales tax
                        'tax_ids': [(6, 0, [])],
                    })],
                    'property_invoice_type': invoice_type,
                })
                # real_estate's create() drops file_ids, so set it afterwards
                invoice.file_ids = file_rec.id
                invoice.action_post()
                file_rec.maintenance_history_ids.create({
                    'date': month_first_day,
                    'installment_number': installment_number,
                    'amount': invoice.amount_total,
                    'invoice_created': True,
                    'invoice_id': invoice.id,
                    'amount_paid': invoice.amount_total - invoice.amount_residual,
                    'residual': invoice.amount_residual,
                    'payment_status': invoice.payment_state,
                    'file_id': file_rec.id,
                    'charge_type': 'utility' if invoice_type == 'maintenance_charges' else 'electricity',
                })
                created |= invoice
        if not created:
            reasons = []
            if skipped_existing:
                reasons.append(_('already billed this month: %s') % ', '.join(skipped_existing[:10]))
            if no_rule:
                reasons.append(_('no Maintenance Charges rule for: %s') % ', '.join(no_rule[:10]))
            raise ValidationError(_('No invoice was created.') + ('\n' + '\n'.join(reasons) if reasons else ''))
        message = _('%s invoice(s) created and posted.') % len(created)
        if skipped_existing:
            message += ' ' + _('%s file(s) skipped (already billed this month).') % len(skipped_existing)
        if no_rule:
            message += ' ' + _('%s file(s) skipped (no matching rule).') % len(no_rule)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invoices generated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Generated Invoices'),
                    'res_model': 'account.move',
                    'view_mode': 'list,form',
                    'views': [(False, 'list'), (False, 'form')],
                    'domain': [('id', 'in', created.ids)],
                },
            },
        }
