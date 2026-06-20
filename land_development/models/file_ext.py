from odoo import fields, models, api, _


class FileExt(models.Model):
    _inherit = 'file'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('tracking_id', _('*')) == _('*') and vals.get('type') != 'investor' and self._context.get('current_view') == 'buildings':
                vals['tracking_id'] = self.env['ir.sequence'].next_by_code("file.tracking.building") or _('*')
        return super(FileExt, self).create(vals_list)
