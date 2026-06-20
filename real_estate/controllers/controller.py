from datetime import datetime, timedelta

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

class Web(http.Controller):

    @http.route(['/file/verification','/file/verification/<int:id>'], type='http', auth="none", website=True)
    def file_verification(self, **kw):
        print(kw)
        file = request.env['file'].sudo().browse(kw['id'])
        if file:
            return request.render("real_estate.file_verification", {'file': file})
        else:
            return None