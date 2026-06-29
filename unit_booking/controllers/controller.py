from datetime import datetime, timedelta

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request
import werkzeug


class Web(http.Controller):

    # @http.route(['/booking/verification','/booking/verification/<int:id>/<string:category>/<string:product>/<string:name>'], type='http', auth="public", website=True)
    # @http.route(['/booking/verification','/booking/verification/<int:id>/<string:name>'], type='http', auth="none", website=True)
    @http.route(['/booking/verification', '/booking/verification/<string:name>'], type='http', auth="none", website=True)
    def file_booking_verification(self, **kw):
        print(kw)
        # unit = request.env["units.booking"].sudo().browse(kw['id'])
        # if unit:
        #     return request.render("unit_booking.booking_verification", {'unit': unit})
        # else:
        # issuance_request = request.env["unit.swapping.request"].sudo().browse(kw['id'])
        issuance_request = request.env["unit.swapping.request"].sudo().search([('name', '=', kw['name'])])
        if issuance_request:
            return request.render("unit_booking.issuance_request_verification", {'issuance_request': issuance_request})
        else:
            return None

    @http.route(['/booking/verification', '/booking/verification/<int:id>/<string:name>'], type='http', auth="none", website=True)
    def file_booking_verification_old(self, **kw):
        print(kw)
        url = f"/booking/verification/{kw['name']}"
        return werkzeug.utils.redirect(url)
