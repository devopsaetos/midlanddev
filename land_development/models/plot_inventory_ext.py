# -*- coding: utf-8 -*-
import base64
import io

import xlsxwriter

from odoo import models, _
from odoo.exceptions import UserError


class PlotInventoryExt(models.Model):
    _inherit = 'plot.inventory'

    def action_export_units_xlsx(self):
        if not self:
            raise UserError(_("Please select at least one unit to export."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Units')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9'})

        headers = [
            'Serial Number', 'Unit Number', 'Project', 'Building', 'Floor',
            'Category', 'Product', 'Size', 'Type',
            'Net Area', 'Balcony Area', 'Total Area (sft)', 'Actual Area',
            'State', 'Possession Status',
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, header_format)

        state_labels = dict(self._fields['state'].selection)
        possession_labels = dict(self._fields['possession_status'].selection)

        for row, unit in enumerate(self, start=1):
            sheet.write(row, 0, unit.serial_number or '')
            sheet.write(row, 1, unit.name or '')
            sheet.write(row, 2, unit.society_id.name or '')
            sheet.write(row, 3, unit.phase_id.name or '')
            sheet.write(row, 4, unit.sector_id.name or '')
            sheet.write(row, 5, unit.category_id.name or '')
            sheet.write(row, 6, unit.unit_category_type_id.name or '')
            sheet.write(row, 7, unit.size_id.name or '')
            sheet.write(row, 8, unit.unit_class_id.name or '')
            sheet.write(row, 9, unit.net_area)
            sheet.write(row, 10, unit.balcony_area)
            sheet.write(row, 11, unit.standard_area)
            sheet.write(row, 12, unit.actual_area)
            sheet.write(row, 13, state_labels.get(unit.state, unit.state or ''))
            sheet.write(row, 14, possession_labels.get(unit.possession_status, unit.possession_status or ''))

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Units Export.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
