from odoo import fields, models, api, tools


class FileExt(models.Model):
    _inherit = 'file'

    type = fields.Selection(selection_add=[('booking_file', 'Booking File')])
    unit_batch_id = fields.Many2one('unit.batch.generation')
    unit_booking_id = fields.Many2one('units.booking')
    booking_agent_id = fields.Many2one('res.partner', 'Dealer')
    booking_sub_agent_id = fields.Many2one('res.partner', 'Sub-dealer')
    other_agent_id = fields.Many2one('res.partner', string="Other Dealer")
    other_sub_agent_id = fields.Many2one('res.partner', string='Other Sub Dealer')
    other_main_sub_agent_id = fields.Many2one('res.partner', string='Other Sub Dealer')
    free_lance_detail = fields.Char(string='Free Lancer')
    processed_by = fields.Selection([('main_agent', 'Main Dealer'),
                                     ('main_other_sub_agent', 'Main Dealer And Other Sub Dealer'),
                                     ('other_agent', 'Other Dealer'),
                                     ('other_sub_agent', 'Other Dealer And Sub Dealer'),
                                     ('free_lancer', 'Free Lancer')], default='main_agent')