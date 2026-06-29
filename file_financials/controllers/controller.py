from datetime import datetime, timedelta

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

class Web(http.Controller):

    # @http.route(['/file/verification', '/file/verification/<int:id>'], type='http', auth="none", website=True)
    @http.route(['/file/verification', '/file/verification/<string:encoded_id>'], type='http', auth="none", website=True)
    def file_verification(self, **kw):
        try:
            # Proceed with the file verification
            print("File verification")
            print(kw)

            # Check if it's a plain integer ID
            if kw['encoded_id'] and kw['encoded_id'].isdigit():
                record_id = int(kw['encoded_id'])

                file = request.env['file'].sudo().browse(record_id)
                if file and file.exists():
                    return request.render("file_financials.file_verification_input", {'file': file})
                else:
                    return request.render("file_financials.file_verification_not_found", {'file': file})

            else:
                file = request.env['file'].sudo().search([('qr_hashid' ,'=', kw['encoded_id'])])
                if file and file.exists() and file.company_id.id == 16:
                    return request.render("file_financials.file_verification", {'file': file})
                elif file and file.exists() and file.company_id.id != 16:
                    return request.render("file_financials.file_verification_input", {'file': file})
                else:
                    return request.render("file_financials.file_verification_not_found", {'file': file})

            # if file and file.exists():
            #     # By-Pass verification incase of NCP Lahore
            #     if file.company_id.id == 16:
            #         return request.render("file_financials.file_verification", {'file': file})
            #     else:
            #         return request.render("file_financials.file_verification_input", {'file': file})
            # else:
            #     return request.render("file_financials.file_verification_not_found", {'file': file})
        except Exception:
            return request.render("file_financials.file_verification_not_found")

    @http.route(['/file/verify_details'], type='http', auth="none", website=True, csrf=False)
    def verify_details(self, **post):
        cnic = post.get('cnic')
        # cnic = '34101-3580449-5'
        file_name = post.get('file_name')
        booking_date = post.get('booking_date')
        file_id = post.get('file_id')

        if not cnic or not file_name or not booking_date:
            raise ValidationError("Please fill in all required fields.")

        file = request.env['file'].sudo().search([
            ('id', '=', int(file_id)),
            ('membership_id.cnic', '=', cnic),
            ('name', '=', file_name),
            ('booking_date', '=', booking_date)
        ], limit=1)

        if file and file.exists():
            return request.render("file_financials.file_verification", {'file': file})
        else:
            return request.render("file_financials.file_verification_not_found", {})

    # @http.route(['/payment/verification', '/payment/verification/<int:id>'], type='http', auth="none", website=True)
    @http.route(['/payment/verification', '/payment/verification/<string:encoded_id>'], type='http', auth="none", website=True)
    def payment_verification(self, **kw):
        # print(kw)
        # payment = request.env['account.payment'].sudo().browse(kw['id'])
        # if payment:
        #     return request.render("file_financials.payment_verification", {'payment': payment})
        # else:
        #     return None
        try:
            # Proceed with the file verification

            # Check if it's a plain integer ID
            if kw['encoded_id'] and kw['encoded_id'].isdigit():
                record_id = int(kw['encoded_id'])

                payment = request.env['account.payment'].sudo().browse(record_id)
                if payment and payment.exists():
                    return request.render("file_financials.payment_verification_input", {'payment': payment})
                else:
                    return request.render("file_financials.file_verification_not_found", {'payment': payment})

            else:
                payment = request.env['account.payment'].sudo().search([('qr_hashid' ,'=', kw['encoded_id'])])
                if payment and payment.exists() and payment.company_id.id == 16:
                    return request.render("file_financials.payment_verification", {'payment': payment})
                elif payment and payment.exists() and payment.company_id.id != 16:
                    return request.render("file_financials.payment_verification_input", {'payment': payment})
                else:
                    return request.render("file_financials.file_verification_not_found", {'payment': payment})

            # Proceed with the file verification
            # print("Payment verification")
            # print(kw)
            # payment = request.env['account.payment'].sudo().browse(kw['id'])
            # print(payment)
            # if payment and payment.exists():
            #     return request.render("file_financials.payment_verification_input", {'payment': payment})
            # else:
            #     return request.render("file_financials.file_verification_not_found", {'payment': payment})

        except Exception:
            return request.render("file_financials.file_verification_not_found")

    @http.route(['/payment/verify_details'], type='http', auth="none", website=True, csrf=False)
    def payment_verify_details(self, **post):
        cnic = post.get('cnic')
        # cnic = '34101-3580449-5'
        name = post.get('name')
        date = post.get('date')
        id = post.get('id')

        if not cnic or not name or not date:
            raise ValidationError("Please fill in all required fields.")

        payment = request.env['account.payment'].sudo().search([
            ('id', '=', int(id)),
            ('partner_id.cnic', '=', cnic),
            ('name', '=', name),
            ('payment_date', '=', date)
        ], limit=1)

        if payment and payment.exists():
            return request.render("file_financials.payment_verification", {'payment': payment})
        else:
            return request.render("file_financials.file_verification_not_found", {})
