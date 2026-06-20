from odoo import fields, models, api
from odoo.exceptions import UserError


class InstallmentInvoiceWizard(models.TransientModel):
    _name = 'installment.invoice.wizard'
    _description = 'Installment Invoice Wizard'

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase')
    sector_id = fields.Many2one('sector')
    file_id = fields.Many2one('file')
    from_file = fields.Boolean()
    payment_id = fields.Many2one('account.payment')
    from_payment = fields.Boolean()
    till_date = fields.Date(required=True)

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
            }
        }

    def _get_product_income_account_id(self, product):
        account = product.property_account_income_id
        if not account:
            account = product.categ_id.property_account_income_categ_id
        if not account:
            account = self.env['account.account'].search(
                [('account_type', 'in', ('income', 'income_other')),
                 ('company_ids', 'in', self.env.company.ids)], limit=1)
        return account.id

    def generate_installment_invoices(self):
        # --------------------------------------
        date = self.till_date
        # -----------------------------------------
        count = 0
        payment_terms = False
        installment_invoices = []
        if self.file_id and self.from_file:
            file = self.file_id
        else:
            if self.file_id and self.from_payment:
                file = self.file_id
            else:
                domain = [('society_id', '=', self.society_id.id), ('phase_id', '=', self.phase_id.id), ('overall_status', '=', 'open')]
                if self.sector_id:
                    domain.append(('sector_id', '=', self.sector_id.id))
                files = self.env['file'].search(domain)

                # filtering those files with due installments.
                file = files.installment_plan_ids.search(
                    [('invoice_created', '=', False),
                     ('file_id.society_id.company_id', '=', self.env.company.id),
                     ('date', '<=', date),
                     ('file_id.state', '=', 'available'),
                     ('file_id.file_status', '=', 'approve'),
                     ('file_id.payment_type', '=', 'installments')]).mapped('file_id')

        for rec in file:
            if rec.installment_tax_ids:
                tax_ids = rec.installment_tax_ids.ids
            else:
                tax_ids = rec.env.company.installment_tax_ids.ids
            if rec.payment_type == 'installments':
                payment_terms = rec.env.company.payment_terms_installment_id
            no_of_installment = []
            if rec.installment_plan_ids \
                    and rec.create_manually == False \
                    and rec.state not in ['cancel', 'refund'] \
                    and rec.society_id.company_id == self.env.company:
                print("FILE:>>>>>>", rec)
                for installment in rec.installment_plan_ids:
                    # date = fields.Date.today()

                    # if till_date:
                    #     date = fields.Date.today() if fields.Date.today() > till_date else  till_date

                    if installment.date <= date and not installment.invoice_created and installment.installment_type != 'down':
                        try:
                            prod = []

                            if self.env.company.ownership_percentage and rec.membership_id.company_type == 'aop':
                                for member in rec.membership_id.cnic_line_ids:
                                    if installment.installment_type == 'final':
                                        prod.append((0, 0, {
                                            'product_id': self.env.ref('real_estate.final_product').id,
                                            'name': member.member_name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.final_product')),
                                            'price_unit': (installment.amount * member.ownership) / 100,
                                            'tax_ids': tax_ids,
                                        }))
                                    elif installment.installment_type == 'installment':
                                        prod.append((0, 0, {
                                            'product_id': self.env.ref('real_estate.installment_product').id,
                                            'name': member.member_name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.installment_product')),
                                            'price_unit': (installment.amount * member.ownership) / 100,
                                            'tax_ids': tax_ids,
                                        }))
                                    elif installment.installment_type == 'balloon':
                                        prod.append((0, 0, {
                                            'product_id': self.env.ref('real_estate.balloon_payment').id,
                                            'name': member.member_name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.balloon_payment')),
                                            'price_unit': (installment.amount * member.ownership) / 100
                                        }))
                                    elif installment.installment_type == 'possession_amount':
                                        prod = [(0, 0, {
                                            'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                            'name': self.env.ref('real_estate.possession_amount_product').name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.possession_amount_product')),
                                            'price_unit': installment.amount
                                        })]

                                    elif installment.installment_type == 'confirmation_amount':
                                        prod = [(0, 0, {
                                            'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                            'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.confirmation_amount_product')),
                                            'price_unit': installment.amount
                                        })]

                                    elif installment.installment_type == 'balloting_amount':
                                        prod = [(0, 0, {
                                            'product_id': self.env.ref('real_estate.balloting_product').id,
                                            'name': self.env.ref('real_estate.balloting_product').name,
                                            'account_id': self._get_product_income_account_id(self.env.ref('real_estate.balloting_product')),
                                            'price_unit': installment.amount
                                        })]
                            else:
                                if installment.installment_type == 'final':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.final_product').id,
                                        'name': self.env.ref('real_estate.final_product').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.final_product')),
                                        'price_unit': installment.amount,
                                        'tax_ids': tax_ids,
                                    })]
                                elif installment.installment_type == 'installment':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.installment_product').id,
                                        'name': self.env.ref('real_estate.installment_product').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.installment_product')),
                                        'price_unit': installment.amount,
                                        'tax_ids': tax_ids,
                                    })]
                                elif installment.installment_type == 'balloon':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.balloon_payment').id,
                                        'name': self.env.ref('real_estate.balloon_payment').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.balloon_payment')),
                                        'price_unit': installment.amount
                                    })]

                                elif installment.installment_type == 'possession_amount':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                        'name': self.env.ref('real_estate.possession_amount_product').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.possession_amount_product')),
                                        'price_unit': installment.amount
                                    })]

                                elif installment.installment_type == 'confirmation_amount':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                        'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.confirmation_amount_product')),
                                        'price_unit': installment.amount
                                    })]

                                elif installment.installment_type == 'balloting_amount':
                                    prod = [(0, 0, {
                                        'product_id': self.env.ref('real_estate.balloting_product').id,
                                        'name': self.env.ref('real_estate.balloting_product').name,
                                        'account_id': self._get_product_income_account_id(self.env.ref('real_estate.balloting_product')),
                                        'price_unit': installment.amount
                                    })]

                                else:
                                    prod = []

                            done_installment = len(rec.installment_plan_ids.search([
                                ('file_id', '=', rec.id),
                                ('invoice_id', '!=', False)
                            ]))

                            invoice = self.env['account.move'].create({
                                'partner_id': rec.membership_id.partner_id.id,
                                'move_type': 'out_invoice',
                                'journal_id': (
                                    self.env.company.account_journal_id.id
                                    or self.env['account.journal'].search(
                                        [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1
                                    ).id
                                ),
                                'property_invoice_type': installment.installment_type if installment.installment_type else 'installment',
                                'user_id': rec.user_id.id,
                                'date': installment.date,
                                'invoice_date': installment.date,
                                'invoice_payment_term_id': rec.env.company.payment_terms_final_id.id if installment.installment_type == 'final' else payment_terms.id,
                            })
                            invoice.file_ids = rec.id
                            invoice.invoice_line_ids = prod

                            invoice.action_post()
                            count += 1
                            print("INVOICE COUNT:>>>>>>>>>>", count)

                            rec.file_payment_history_id.create({
                                'invoice_id': invoice.id,
                                'file_id': rec.id
                            })

                            installment.invoice_id = invoice.id
                            print("INVOICE ID:>>>>>>>", invoice.id)

                            installment.invoice_created = True
                            installment_invoices.append(invoice.id)
                        except Exception as e:
                            raise UserError('There is some error: %s in auto invoice creation for installment' % (e))

                    no_of_installment.append(installment.invoice_created)
            else:
                no_of_installment.append(False)

            if all(no_of_installment):
                rec.payment_states = 'close'

        if self.from_payment and installment_invoices and self.file_id and self.payment_id:
            for inv in self.env['account.move'].search([('id', 'in', installment_invoices)]):
                new_inv_line = self.env['multi.invoice.payment'].create(
                    {'invoice_id': inv.id,
                     'payment_id': self.payment_id.id,
                     'payment_due': inv.amount_residual,
                     'payment_amount': inv.amount_residual,
                     'discount_amount': (inv.amount_residual * self.payment_id.discount_policy_id.percentage) / 100 if
                     self.payment_id.discount_policy_id else False
                     })
                self.payment_id.multi_invoice_ids = [(4, new_inv_line.id)]
                new_inv_line._compute_payment_amount()
                self.payment_id.amount = sum(self.payment_id.multi_invoice_ids.mapped('payment_amount'))
