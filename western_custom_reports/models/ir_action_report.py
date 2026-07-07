# -*- coding: utf-8 -*-
import base64

from odoo import models
from odoo.tools.image import image_data_uri


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def get_barcode_data_uri(self, barcode_type, value, **kwargs):
        """Generate a barcode image and return it as a ready-to-use
        base64 data URI (e.g. 'data:image/png;base64,....').

        This exists because QWeb report templates render in a sandboxed
        context that does not expose the `base64` module, so the raw PNG
        bytes returned by `barcode()` cannot be encoded from within the
        template itself. This method does the encoding in Python and
        hands back a string the template can drop straight into an
        <img t-att-src="..."/> attribute.
        """
        barcode_png = self.barcode(barcode_type, value, **kwargs)
        return image_data_uri(base64.b64encode(barcode_png))