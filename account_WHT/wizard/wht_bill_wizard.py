from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class WHTBillWizard(models.TransientModel):
    _name = 'wht.bill.wizard'
    _description = 'WHT Bill Wizard'

    date_from = fields.Date(string="Start Date", help="Start date to search invoices by invoice date")
    date_to = fields.Date(string="End Date", help="End date to search invoices by invoice date")
    payment_state = fields.Selection([
        ('not_paid', 'Open'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('both', 'Both'),
    ], string="Payment Status", default='paid', help="Filter invoices based on payment status")
    partner_id = fields.Many2one('res.partner', string="Vendor", help="Vendor for whom the bill is being generated")
    check_all = fields.Boolean(string="Select All", help="Check to select all fetched invoices")

    wht_bill_line_ids = fields.One2many('wht.bill.wizard.lines', 'wht_bill_id', string="Invoice Lines")

    @api.onchange('check_all')
    def _onchange_check_all(self):
        """Auto-check or uncheck all bill lines based on the check_all flag."""
        for rec in self.wht_bill_line_ids:
            rec.check = self.check_all

    def search_records(self):
        """Search and populate invoice lines based on filters."""
        self.wht_bill_line_ids = [(5,)]
        
        # Search for move lines with WHT taxes
        line_domain = []
        if self.partner_id:
            line_domain.append(('partner_id', '=', self.partner_id.id))
            
        wht_lines = self.env['account.move.line'].search(line_domain).filtered(lambda l: l.wht_tax_ids)
        wht_invoice = wht_lines.mapped('move_id')

        if wht_invoice:
            # Filter invoices by date, state, and billing status
            domain_filter = lambda l: l.state == 'posted' and \
                                      (not self.date_from or l.invoice_date >= self.date_from) and \
                                      (not self.date_to or l.invoice_date <= self.date_to) and \
                                      not l.wht_bill_created
            
            invoices = wht_invoice.filtered(domain_filter)
            
            # Apply payment status filter
            if self.payment_state and self.payment_state != 'both':
                if self.payment_state == 'paid':
                    invoices = invoices.filtered(lambda l: l.payment_state in ('paid', 'in_payment'))
                else:
                    invoices = invoices.filtered(lambda l: l.payment_state == self.payment_state)
            elif not self.payment_state or self.payment_state == 'both':
                # If "Both" is selected, we still might want to exclude "not_paid" if the user implied "Paid" is the main goal
                # but usually "Both" means everything. However, let's stick to strict selection.
                pass

            lines_vals = []
            for rec in invoices:

                lines_vals.append((0, 0, {
                    'check': self.check_all,
                    'move_id': rec.id,
                    'amount_untaxed': rec.amount_untaxed,
                    'amount_total': rec.amount_total,
                    'payment_state': rec.payment_state,
                    'tax_ids': rec.invoice_line_ids.mapped('tax_ids').ids,
                    'wht_ids': rec.invoice_line_ids.mapped('wht_tax_ids').ids,
                    'wht_bill_id': self.id
                }))
            
            if lines_vals:
                self.wht_bill_line_ids = lines_vals

        return {

            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def create_bills(self):
        """Create a vendor bill for selected invoices' WHT grouped by authority."""
        if not self.wht_bill_line_ids:
            raise ValidationError('No record found!')

        checked_lines = self.wht_bill_line_ids.filtered(lambda l: l.check)
        if not checked_lines:
            raise ValidationError('Please mark lines to create bills.')

        partner_prod = {}
        for rec in checked_lines.move_id.taxes_line_ids:
            # Group by bill_to partner defined in WHT tax, fallback to wizard partner
            partner = rec.wht_tax_id.bill_to or self.partner_id
            if not partner:
                raise ValidationError(_("No authority (Bill To) defined for WHT tax '%s' and no default vendor selected in wizard.") % rec.wht_tax_id.name)
            
            if partner.id not in partner_prod:
                partner_prod[partner.id] = []
                
            partner_prod[partner.id].append((0, 0, {
                'name': rec.move_id.name,
                'account_id': rec.wht_tax_id.account_id.id,
                'price_unit': rec.amount,
                'quantity': 1,
                'wht_invoice_ref_id': rec.move_id.id,
            }))
            rec.move_id.wht_bill_created = True

        for partner_id, lines in partner_prod.items():
            self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': partner_id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': lines
            })


        return {
            'effect': {
                'type': 'rainbow_man',
                'fadeout': 'slow',
                'message': _("Vendor Bills Generated Successfully!"),
            }
        }


class WHTBillWizardLines(models.TransientModel):
    _name = 'wht.bill.wizard.lines'
    _description = 'WHT Bill Wizard Lines'

    check = fields.Boolean(string="Select", help="Enable this to include the invoice in WHT bill creation.")
    move_id = fields.Many2one('account.move', string="Invoice", help="The invoice linked to this line.")
    date = fields.Date(related='move_id.invoice_date', string="Invoice Date", store=True)
    partner_id = fields.Many2one('res.partner', related='move_id.partner_id', string="Vendor", store=True)
    amount_untaxed = fields.Float(string="Untaxed Amount", help="Total amount before taxes.")
    amount_total = fields.Float(string="Total Amount", help="Total invoice amount.")
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
    ], string="Payment Status", help="Payment state of the invoice.")
    tax_ids = fields.Many2many('account.tax', string="Taxes", help="Taxes applied on the invoice.")
    wht_ids = fields.Many2many('account.wht', string="WHT", help="Withholding Taxes applied on the invoice.")
    wht_bill_id = fields.Many2one('wht.bill.wizard', string="Wizard Reference", help="Reference to the parent WHT Bill Wizard.")
