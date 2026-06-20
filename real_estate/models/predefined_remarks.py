from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PredefineRemarks(models.Model):
    _name = 'predefine.remarks'
    _description = "Predefine Remarks"
    _rec_name = 'external_notes'

    external_notes = fields.Text('External Notes')
