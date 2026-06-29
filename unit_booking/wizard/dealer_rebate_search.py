from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DealerRebateSearch(models.TransientModel):
    _name = 'dealer.rebate.search'
    _description = 'Dealer Rebate Search'

    # models relational fields
    partner_id = fields.Many2one('res.partner')
    settlement_date = fields.Date()
    search_line_ids = fields.One2many('dealer.rebate.search.line', 'search_id')

    def run(self):
        record_set = self.env['unit.booking.allotment'].search([('state', '=', 'closed'),
                                                                ('rebate_generated', '=', False),
                                                                ('rebate_settlement', '=', 'on_deal_close')])
        if record_set:
            for rec in record_set:
                rec.calculate_rebate()
                self.search_line_ids = [(0, 0, {
                    'partner_id': rec.partner_id.id,
                    'allotment_id': rec.id,
                    'rebate_id': rec.rebate_id.id,
                    'calculated_rebate': rec.rebate_amount,
                })]
        else:
            raise ValidationError(_("No Deal Available For Dealer Rebate"))
        return {
            'name': _('RUN'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def approved_rebate(self):
        for rec in self.search_line_ids.filtered(lambda l: l.select):
            if not rec.allotment_id.rebate_id:
                raise ValidationError(_('Please attach rebate rule first in deal %s' % rec.allotment_id.name))
            if not rec.allotment_id.rebate_on_allotment_ids:
                raise ValidationError(_('Please attach rebate rule details in deal %s' % rec.allotment_id.name))
            rec.allotment_id.separate_rebate = rec.rebate_given
            rec.allotment_id.rebate_amount = rec.rebate_given
            rec.allotment_id.settlement_date = self.settlement_date
            rec.allotment_id.rebate_bill()
            rec.allotment_id.rebate_generated = True


class DealerRebateSearchLine(models.TransientModel):
    _name = 'dealer.rebate.search.line'
    _description = 'Dealer Rebate Search Line'

    partner_id = fields.Many2one('res.partner')
    allotment_id = fields.Many2one('unit.booking.allotment')
    rebate_id = fields.Many2one('dealer.rebate')
    calculated_rebate = fields.Float()
    rebate_given = fields.Float()
    select = fields.Boolean(default=False)
    search_id = fields.Many2one('dealer.rebate.search')
