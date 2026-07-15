from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ValidityIncrease(models.TransientModel):
    _name = 'validity.increase'
    _description = "Validity Increase"

    current_date = fields.Date(string='Current Date', readonly=True)
    valid_up_to_date = fields.Date(string="Valid Up To Date")


    def increase_validity_date(self):
        active_id = self._context.get('active_id', False)
        active_model = self._context.get('active_model', False)
        if active_model == 'token.money' and active_id:
            token = self.env['token.money'].browse(active_id)
            if self.current_date < self.valid_up_to_date and self.valid_up_to_date >= fields.Date.today():
                token.date = self.valid_up_to_date
                token.validity_expire = False
                token.token_line_ids[0].inventory_id.state = 'investor' if token.party_type == 'investor' else 'reserved'
            else:
                raise ValidationError(_('Valid Up To Date Passed, Select Up Coming Date'))