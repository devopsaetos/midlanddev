from odoo import models, fields, api

_INVOICE_TYPE_SELECTION = [
    ('initial_payment', 'Initial Payment'),
    ('adv_and_securities', 'Advances and Securities'),
    ('installment', 'Installment'),
    ('initial_payment_plus_installment', 'Initial Payment + Installment'),
    ('transfer_application', 'Transfer Application'),
    ('rent', 'Rent'),
    ('others', 'Others'),
    ('token', 'Token'),
    ('investment', 'Investment'),
    ('investment_installment', 'Investment Installment'),
    ('maintenance', 'Maintenance Charges'),
    ('map_fee', 'Mapping Fee'),
    ('tax', 'PRA-Tax'),
    ('236k_sale', '236k-Sale'),
    ('demarcation', 'Demarcation'),
    ('merger_adjustment', 'Merger Adjustment'),
    ('down', 'Booking'),
    ('confirmation_amount', 'Confirmation'),
    ('balloon', 'Balloon'),
    ('balloting_amount', 'Balloting'),
    ('possession_amount', 'Possession'),
    ('final', 'Final Payment'),
    ('merger_fee', 'Merger Fee'),
    ('booking_allotment', 'Booking Allotment'),
    ('allotment_installment', 'Allotment Installment'),
]


class FileInstallmentPaymentExt(models.Model):
    _inherit = 'file.installment.payment'

    midland_payment_line_id = fields.Many2one(
        'midland.payment.line', string='Midland Payment Line',
        ondelete='cascade', index=True,
    )
    midland_invoice_ref = fields.Char(string='Invoice #', readonly=True)

    # Override related fields to support midland payments (no account.move/account.payment)
    invoice_date = fields.Date(
        string='Invoice Date',
        compute='_compute_midland_display', store=True, readonly=False,
    )
    payment_date = fields.Date(
        string='Payment Date',
        compute='_compute_midland_display', store=True, readonly=False,
    )
    property_invoice_type = fields.Selection(
        selection=_INVOICE_TYPE_SELECTION,
        string='Invoice Type',
        compute='_compute_midland_display', store=True, readonly=False,
    )

    @api.depends(
        'midland_payment_line_id.invoice_date',
        'midland_payment_line_id.payment_date',
        'midland_payment_line_id.invoice_id.property_invoice_type',
        'multi_invoice_line_id.invoice_id.invoice_date',
        'multi_invoice_line_id.invoice_id.property_invoice_type',
        'payment_id.date',
    )
    def _compute_midland_display(self):
        for rec in self:
            mpl = rec.midland_payment_line_id
            if mpl:
                rec.invoice_date = mpl.invoice_date
                rec.payment_date = mpl.payment_date
                rec.property_invoice_type = (
                    mpl.invoice_id.property_invoice_type if mpl.invoice_id else False
                )
            else:
                # Standard account.payment flow — traverse chain directly (avoid related field in compute)
                inv = rec.multi_invoice_line_id.invoice_id if rec.multi_invoice_line_id else False
                rec.invoice_date = inv.invoice_date if inv else False
                rec.payment_date = rec.payment_id.date if rec.payment_id else False
                rec.property_invoice_type = inv.property_invoice_type if inv else False
