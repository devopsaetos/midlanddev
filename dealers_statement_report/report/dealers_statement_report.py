# -*- coding: utf-8 -*-
from odoo import models, api, fields


class DealerStatementReport(models.AbstractModel):
    _name = 'report.dealers_statement_report.dealer_statement'
    _description = 'Dealer Statement Report'

    def _advance_payment_lines(self, invoice):
        """multi.invoice.payment rows settling `invoice` through an advance payment.

        Odoo 13's account.move._get_reconciled_info_JSON_values() override (which
        this report used to call from QWeb) doesn't exist in this Odoo 19 code
        base - payment/invoice matching here goes through the project's own
        multi.invoice.payment bridge instead, so the lookup is done in Python.
        """
        return self.env['multi.invoice.payment'].sudo().search([
            ('invoice_id', '=', invoice.id),
            ('payment_id.is_advance_payment', '=', True),
        ])

    def _midland_invoices_for(self, plan_lines, fk_field):
        """{plan_line.id: midland.invoice recordset}, non-cancelled, linked
        through `fk_field` (investment_installment_id on investment.plan /
        installment_id on installment.plan).

        This project has two invoicing pipelines writing to the same
        investment.plan/installment.plan lines: the old account.move one
        (invoice_id + multi.invoice.payment, still used by some investors)
        and midland_invoicing (midland.invoice/midland.payment). The new one
        defaults to posting with no journal entry, so it never sets
        invoice_id or the old net_receivable/net_payment fields on the plan
        line - the real amount/paid data only exists on midland.invoice.
        Every amount below has to check here first and fall back to the old
        fields only when a line has no midland.invoice.

        sudo(): midland.invoice's multi-company rule filters on its own
        company_id (the deal's top-level company), while investment/
        investor.file filter on society_id.company_id (the branch/project
        company) - on a deal whose branch is a child of that top-level
        company, those are two different companies. A user with only the
        branch checked in the company switcher would see the investor/
        inventory data above but have every invoice here silently filtered
        to nothing. The wizard's own domain already scopes this report to
        one explicit company, so re-applying the rule here only breaks that
        scoping in exactly this branch/parent split - it doesn't add safety.
        """
        if not plan_lines:
            return {}
        invoices = self.env['midland.invoice'].sudo().search([
            (fk_field, 'in', plan_lines.ids),
            ('state', '!=', 'cancelled'),
        ])
        mapping = {}
        for inv in invoices:
            key = inv[fk_field].id
            mapping[key] = mapping.get(key, self.env['midland.invoice'].sudo()) | inv
        return mapping

    def _midland_cash_paid(self, invoices):
        """Real cash collected against `invoices`, from midland.payment.line.payment_amount.

        Not midland.invoice.amount_paid / payment_line.payment_amount_paid -
        those bake the dealer/marketing rebate into the FIRST payment against
        a booking-rebate invoice (MidlandPayment._confirm_no_entry()), so
        amount_paid ends up rebate-inflated and later payments' real cash can
        get capped down once the invoice already reads as "fully paid". That
        makes them wrong for a dealer-facing cash statement - payment_amount
        is the actual amount collected, matching what the Payments list shows.
        """
        lines = invoices.payment_line_ids.filtered(lambda l: l.payment_id.state == 'confirmed')
        return sum(lines.mapped('payment_amount'))

    # investor.file states from "File Created" onwards - the unit has left the
    # dealer's stock and been turned into a customer file. 'open', 'selected'
    # and 'in_process' files are still the dealer's to sell.
    _SOLD_FILE_STATES = ('issued', 'file_printed', 'delivered', 'received')

    def _inventory_rows(self, investments, files):
        """([{'category', 'assigned', 'sold', 'available'}, ...], totals dict)
        for the Inventory Status block, one row per unit category actually
        present - not a hardcoded list of sizes (which silently dropped any
        category it didn't know about, e.g. '3 Marla' wasn't in it at all
        here) filtered with `'5 Marla' in name`, a substring check that also
        matches '3.5 Marla' and double-counts it into the '5 Marla' bucket.
        Both bugs were in the original template's inline t-set expressions.

        Assigned = the units on the deal itself (the Deal form's Inventory
        count): plot.inventory reserved to it for unit reservations, plus
        investment.line.no_of_units for bulk ones - not investor.file, which
        only exists for the files already requested/created out of them
        (8 files on a 49-unit deal).
        Sold = the deal's files that have reached "File Created" or later.
        Available = whatever's still unsold.
        """
        assigned = {}
        for unit in self.env['plot.inventory'].sudo().search([('investment_id', 'in', investments.ids)]):
            assigned[unit.unit_category_type_id] = assigned.get(unit.unit_category_type_id, 0) + 1
        for line in investments.sudo().investment_line_ids.filtered(lambda l: not l.inventory_id):
            assigned[line.unit_category_type_id] = assigned.get(line.unit_category_type_id, 0) + line.no_of_units

        sold = {}
        for f in files.filtered(lambda f: f.state in self._SOLD_FILE_STATES):
            sold[f.unit_category_type_id] = sold.get(f.unit_category_type_id, 0) + 1

        # A file's category can't exceed what the deal was assigned; if
        # files somehow outnumber the deal's units (units swapped/edited
        # after the fact), still show them rather than a negative Available.
        rows = []
        for category in sorted(set(assigned) | set(sold), key=lambda c: c.name or ''):
            total = max(assigned.get(category, 0), sold.get(category, 0))
            rows.append({
                'category': category.name or '',
                'assigned': total,
                'sold': sold.get(category, 0),
                'available': total - sold.get(category, 0),
            })
        totals = {key: sum(r[key] for r in rows) for key in ('assigned', 'sold', 'available')}
        return rows, totals

    def _summarize_lines(self, plan_lines, fk_field):
        """(amount, paid, rebate, due, midland_invoices_map) for `plan_lines`
        (investment.plan or installment.plan rows already filtered to one
        installment_type) - midland.invoice data where a line has it, the
        old net_receivable/net_payment/rebate_adjustment fields otherwise.

        due = the plan line's own "Amount Due" (residual) - the same figure
        the Deal form's Installment Plan tab shows, so the report agrees with
        it. Not derived from amount/rebate/cash here: that disagreed with the
        system on deals where the marketing rebate also settles part of an
        invoice.
        """
        invoices_map = self._midland_invoices_for(plan_lines, fk_field)
        amount = paid = rebate = due = 0.0
        for plan_line in plan_lines:
            invs = invoices_map.get(plan_line.id)
            if invs:
                amount += sum(invs.mapped('amount_total'))
                paid += self._midland_cash_paid(invs)
                rebate += sum(invs.mapped('rebate_total'))
                due += plan_line.residual
            else:
                amount += plan_line.net_receivable
                paid += plan_line.net_payment
                rebate += plan_line.rebate_adjustment
                due += plan_line.residual
        return amount, paid, rebate, due, invoices_map

    def _deal_payment_row(self, investment, plan_lines):
        """One Payment Details row for a whole deal.

        total    = the deal's total amount.
        paid     = sum of every plan line's Amount Paid, i.e. what the Deal
                   form's Installment Plan tab totals to - it counts what the
                   rebates settled as well as cash.
        due      = sum of every plan line's Amount Due, same tab's total.
        of which paid: dealer rebate / marketing rebate applied against the
        deal's invoices, and the cash actually collected (midland.payment
        lines; old-pipeline lines fall back to rebate_adjustment / net_payment).
        """
        invoices_map = self._midland_invoices_for(plan_lines, 'investment_installment_id')
        dealer_rebate = marketing_rebate = cash = 0.0
        for plan_line in plan_lines:
            invs = invoices_map.get(plan_line.id)
            if invs:
                dealer_rebate += sum(invs.mapped('rebate_total'))
                marketing_rebate += sum(invs.mapped('marketing_rebate_total'))
                cash += self._midland_cash_paid(invs)
            else:
                dealer_rebate += plan_line.rebate_adjustment
                cash += plan_line.net_payment
        return {
            'label': investment.name,
            'total': investment.total_amount,
            'paid': sum(plan_lines.mapped('amount_paid')),
            'dealer_rebate': dealer_rebate,
            'marketing_rebate': marketing_rebate,
            'cash': cash,
            'due': sum(plan_lines.mapped('residual')),
        }

    def _booking_lines(self, investments_booking_lines, midland_invoices_map):
        lines = []
        for plan_line in investments_booking_lines:
            invs = midland_invoices_map.get(plan_line.id)
            if invs:
                for mi in invs:
                    for mpl in mi.payment_line_ids.filtered(lambda l: l.payment_id.state == 'confirmed'):
                        lines.append({
                            'invoice_number': mpl.payment_id.name,
                            'investment_name': plan_line.investment_id.name,
                            'payment_type': mi.name,
                            'date': mpl.payment_date,
                            'amount_paid': mpl.payment_amount,
                            # midland.payment has no cheque/bank reference fields
                            'cheque_no': '',
                            'bank_ref': '',
                        })
            elif plan_line.invoice_id:
                for mp in self._advance_payment_lines(plan_line.invoice_id):
                    lines.append({
                        'invoice_number': mp.payment_id.name,
                        'investment_name': plan_line.investment_id.name,
                        'payment_type': plan_line.invoice_id.name,
                        'date': mp.payment_id.date,
                        'amount_paid': mp.payment_amount,
                        'cheque_no': mp.payment_id.cheque_no,
                        'bank_ref': mp.payment_id.bank_ref,
                    })
        return lines

    def _confirmation_lines(self, files_confirmation_lines, midland_invoices_map):
        lines = []
        serial = 0
        for plan_line in files_confirmation_lines:
            invs = midland_invoices_map.get(plan_line.id)
            if invs:
                for mi in invs:
                    for mpl in mi.payment_line_ids.filtered(lambda l: l.payment_id.state == 'confirmed'):
                        serial += 1
                        lines.append({
                            'serial': serial,
                            'investment_name': plan_line.investor_file_id.investment_id.name,
                            'file_name': plan_line.investor_file_id.name,
                            # midland_invoicing has no advance-payment concept
                            'advance_name': '',
                            'payment_name': mpl.payment_id.name,
                            'date': mpl.payment_date,
                            'payment_amount': mpl.payment_amount,
                            # rebate for these is counted once via
                            # midland.invoice.rebate_total in _get_report_values,
                            # not per payment - avoid double counting it here.
                            'payment_difference': 0.0,
                            'cheque_no': '',
                            'bank_ref': '',
                        })
            elif plan_line.invoice_id:
                for mp in self._advance_payment_lines(plan_line.invoice_id):
                    serial += 1
                    advance = mp.payment_id.advance_payment_id
                    lines.append({
                        'serial': serial,
                        'investment_name': plan_line.investor_file_id.investment_id.name,
                        'file_name': plan_line.investor_file_id.name,
                        'advance_name': advance.name,
                        'payment_name': mp.payment_id.name,
                        'date': mp.payment_id.date,
                        'payment_amount': mp.payment_amount,
                        'payment_difference': mp.payment_difference,
                        'cheque_no': advance.cheque_no,
                        'bank_ref': advance.bank_ref,
                    })
        return lines

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        # Odoo's report-layout preview (e.g. editing header/footer/paperformat
        # in Studio) renders this report against a generic base.document.layout
        # placeholder instead of the real wizard record - fall back to an
        # unfiltered/empty report rather than crashing on missing wizard fields.
        if model != 'dealer.statement.wizard':
            return {
                'doc_ids': docids,
                'doc_model': 'dealer.statement.wizard',
                'docs': self.env['dealer.statement.wizard'],
                'data': [],
                'printed_by': self.env.user.name,
                'print_date': fields.Date.context_today(self).strftime('%d-%m-%Y'),
            }
        # sudo(): the template reads o.investor_id/o.investment_ids straight
        # off this wizard record to echo back the user's own filter
        # selections - res.investor and investment carry the same
        # company-hierarchy rule split as above, so without this a viewer
        # whose active company is the "wrong" half of that split gets an
        # AccessError just from the report trying to redisplay what they
        # themselves picked in the wizard.
        docs = self.env[model].sudo().browse(self.env.context.get('active_id'))

        # A deal's own company_id is its top-level/parent company (matches
        # investment.plan/midland.invoice's company_id); its branch/project
        # company - what's actually on the letterhead - is society_id.
        # company_id instead (same field investor.file's rule uses). Which
        # one equals self.env.company.id depends entirely on whether the
        # printing user's *active* company in the switcher happens to be the
        # parent or the branch - matching only one of the two leaves the
        # report blank whenever it's the other. env.companies (every company
        # currently allowed, not just the active one) OR'd across both
        # fields covers both without caring which one is primary.
        allowed = self.env.companies.ids
        domain = ['|', ('company_id', 'in', allowed), ('society_id.company_id', 'in', allowed)]
        if docs.investment_ids:
            domain.append(('id', 'in', docs.investment_ids.ids))
        if docs.investor_id:
            domain.append(('partner_id', '=', docs.investor_id.id))
        if docs.date_from:
            domain.append(('booking_date', '>=', docs.date_from))
        if docs.date_to:
            domain.append(('booking_date', '<=', docs.date_to))

        # sudo(): investment/investor.file's multi-company rule checks
        # society_id.company_id (the branch/project company), while
        # investment.plan/midland.invoice below check their own direct
        # company_id (the deal's top-level company) - on a branch deal those
        # differ, so a user with only one of the two checked in the company
        # switcher would otherwise have half this report silently filtered
        # out. The domain above already scopes everything to one explicit
        # company, so this doesn't widen what the report can show.
        investments = self.env['investment'].sudo().search(domain)
        investors = investments.mapped('partner_id')
        data = []
        for investor in investors:
            files = self.env['investor.file'].sudo().search([
                ('investor_id', '=', investor.id),
                ('investment_id', 'in', investments.ids),
                ('state', '!=', 'cancel'),
            ])

            investor_investments = investments.filtered(lambda x, investor=investor: x.partner_id == investor)
            inventory_rows, inventory_totals = self._inventory_rows(investor_investments, files)
            investments_lines = self.env['investment.plan'].sudo().search([
                ('investment_id', 'in', investor_investments.ids),
            ])

            # 'down' (Booking) and 'down_payment' (Down Payment) are
            # independent plan lines a deal's plan can create at booking time
            # (see Investment._create_installment_plan_for_group()) - a given
            # deal uses one or the other (occasionally both), never neither.
            # They're two distinct fields on the Deal form itself ("Booking
            # Payment" vs "Down Payment"), so they get their own row here too
            # instead of being merged under one label.
            booking_lines_src = investments_lines.filtered(lambda l: l.installment_type == 'down')
            booking_amount, booking_amount_paid, booking_rebate, booking_amount_due, booking_invoices = \
                self._summarize_lines(booking_lines_src, 'investment_installment_id')

            down_payment_lines_src = investments_lines.filtered(lambda l: l.installment_type == 'down_payment')
            down_payment_amount, down_payment_amount_paid, down_payment_rebate, down_payment_amount_due, down_payment_invoices = \
                self._summarize_lines(down_payment_lines_src, 'investment_installment_id')

            # Not _summarize_lines(): unlike booking/down payment, confirmation's
            # rebate has never come from rebate_adjustment for old-pipeline
            # lines - it's derived below from payment_difference on the actual
            # payment rows instead, so the per-line loop here deliberately
            # leaves rebate out to avoid double-counting it.
            files_confirmation_lines = files.mapped('installment_plan_ids').filtered(
                lambda l: l.installment_type == 'confirmation_amount')
            confirmation_invoices = self._midland_invoices_for(files_confirmation_lines, 'installment_id')
            confirmation_amount = 0.0
            confirmation_amount_paid = 0.0
            confirmation_rebate = 0.0
            for plan_line in files_confirmation_lines:
                invs = confirmation_invoices.get(plan_line.id)
                if invs:
                    confirmation_amount += sum(invs.mapped('amount_total'))
                    confirmation_amount_paid += self._midland_cash_paid(invs)
                    confirmation_rebate += sum(invs.mapped('rebate_total'))
                else:
                    confirmation_amount += plan_line.net_receivable
                    confirmation_amount_paid += plan_line.net_payment
            confirmation_amount_due = confirmation_amount - confirmation_amount_paid

            confirmation_lines = self._confirmation_lines(files_confirmation_lines, confirmation_invoices)
            confirmation_rebate += sum(l['payment_difference'] for l in confirmation_lines)

            # Payment Details: one row per deal (Booking/Confirmation
            # breakdowns stay hidden per client request, see the template).
            payment_rows = [
                self._deal_payment_row(inv, investments_lines.filtered(lambda l, inv=inv: l.investment_id == inv))
                for inv in investor_investments
            ]
            payment_totals = {
                key: sum(r[key] for r in payment_rows)
                for key in ('total', 'paid', 'dealer_rebate', 'marketing_rebate', 'cash', 'due')
            }

            data.append({
                'investor': investor,
                'files': files,
                'inventory_rows': inventory_rows,
                'inventory_totals': inventory_totals,
                'booking_amount': booking_amount,
                'booking_amount_paid': booking_amount_paid,
                'booking_amount_due': booking_amount_due,
                'booking_rebate': booking_rebate,
                'down_payment_amount': down_payment_amount,
                'down_payment_amount_paid': down_payment_amount_paid,
                'down_payment_amount_due': down_payment_amount_due,
                'payment_rows': payment_rows,
                'payment_totals': payment_totals,
                'down_payment_rebate': down_payment_rebate,
                'confirmation_amount': confirmation_amount,
                'confirmation_amount_paid': confirmation_amount_paid,
                'confirmation_amount_due': confirmation_amount_due,
                'confirmation_rebate': confirmation_rebate,
                'booking_lines': self._booking_lines(booking_lines_src, booking_invoices),
                'down_payment_lines': self._booking_lines(down_payment_lines_src, down_payment_invoices),
                'confirmation_lines': confirmation_lines,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'dealer.statement.wizard',
            'docs': docs,
            'data': data,
            'printed_by': self.env.user.name,
            'print_date': fields.Date.context_today(self).strftime('%d-%m-%Y'),
        }
