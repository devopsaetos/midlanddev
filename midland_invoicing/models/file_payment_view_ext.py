from odoo import fields, models, tools


class FilePaymentViewExt(models.Model):
    _inherit = 'file.payment.view'

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''CREATE OR REPLACE VIEW %s AS (
            SELECT row_number() OVER () AS id, sub.* FROM (

                SELECT
                    pay.date                                         AS payment_date,
                    pay.amount_residual                              AS payment_amount_residual,
                    f.id                                             AS file_id,
                    pay.id                                           AS payment_id,
                    NULL::varchar                                    AS midland_payment_ref,
                    COALESCE(multi.payment_amount, pay.amount)       AS payment_amount,
                    multi.invoice_id                                 AS move_id,
                    invoice.property_invoice_type                    AS property_invoice_type,
                    invoice.amount_residual                          AS invoice_residual,
                    invoice.amount_total                             AS invoice_amount,
                    invoice.invoice_date                             AS invoice_date
                FROM file f
                INNER JOIN account_payment pay         ON f.id = pay.file_id
                LEFT  JOIN multi_invoice_payment multi ON multi.payment_id = pay.id
                LEFT  JOIN account_move invoice        ON invoice.id = multi.invoice_id
                WHERE invoice.property_invoice_type IN (\'initial_payment\', \'installment\')
                  AND pay.state != \'draft\'

                UNION ALL

                SELECT
                    mp.date                                          AS payment_date,
                    0.0                                              AS payment_amount_residual,
                    mp.file_id                                       AS file_id,
                    NULL::integer                                    AS payment_id,
                    mp.name                                          AS midland_payment_ref,
                    COALESCE(mpl.payment_amount_paid, mpl.payment_amount) AS payment_amount,
                    mp.jv_id                                         AS move_id,
                    mi.property_invoice_type                         AS property_invoice_type,
                    mi.amount_residual                               AS invoice_residual,
                    mi.amount_total                                   AS invoice_amount,
                    mi.invoice_date                                  AS invoice_date
                FROM midland_payment mp
                INNER JOIN midland_payment_line mpl ON mpl.payment_id = mp.id
                INNER JOIN midland_invoice mi       ON mi.id = mpl.invoice_id
                WHERE mp.state = \'confirmed\'
                  AND mp.file_id IS NOT NULL

            ) sub
        )''' % self._table)
