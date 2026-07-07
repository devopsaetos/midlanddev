from odoo import api, SUPERUSER_ID


def post_init_hook(env):
    """Customer Invoice report صرف out_invoice پر دکھے"""
    invoice_report = env.ref(
        'western_custom_reports.action_report_invoice_report_custom',
        raise_if_not_found=False
    )
    if invoice_report:
        env.cr.execute(
            "UPDATE ir_act_report_xml SET binding_domain = %s WHERE id = %s",
            ("[('move_type', 'in', ['out_invoice', 'out_refund'])]", invoice_report.id)
        )

    # Vendor Bill report صرف in_invoice پر دکھے
    bill_report = env.ref(
        'western_custom_reports.action_report_vendor_bill_custom',  # اپنا id یہاں لکھیں
        raise_if_not_found=False
    )
    if bill_report:
        env.cr.execute(
            "UPDATE ir_act_report_xml SET binding_domain = %s WHERE id = %s",
            ("[('move_type', 'in', ['in_invoice', 'in_refund'])]", bill_report.id)
        )