from odoo import fields, models, api, _


class FileExt(models.Model):
    _inherit = 'file'

    @api.model_create_multi
    def create(self, vals_list):
        # tracking_id and name are now handled in base File.create() based on project_type
        return super(FileExt, self).create(vals_list)
