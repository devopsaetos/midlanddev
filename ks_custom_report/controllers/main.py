from odoo import http
from odoo.http import request


class GoogleCalendarController(http.Controller):
    @http.route('/ks_custom_report/get_model_name', type='json', auth='user')
    def get_model_domain(self, model, **kw):
        ks_custom_report = request.env['ks_custom_report.ks_report']

        ks_report_record = ks_custom_report.sudo().search([('ks_cr_model_id.model', '=', model)])

        if not ks_report_record:
            return False

        # Use the base model (ks_model_id) for the action since domain conversion targets it
        # Fallback to report model if base model is not available
        if not ks_report_record.ks_model_id or not ks_report_record.ks_model_id.model:
            return False
        
        ks_model = ks_report_record.ks_model_id.model
        
        domains = kw.get('domain')
        ks_domain = []
        # Check if the target model has company_id field
        model_has_company_id = False
        try:
            model_class = request.env[ks_model]
            model_has_company_id = 'company_id' in model_class._fields
        except:
            pass
        if domains:
            if ks_report_record.ks_cr_query_type != 'custom_query':
                # Process domains and track which ones to keep
                valid_domains = []
                for domain in domains:
                    if type(domain).__name__ == 'list':
                        field = domain[0]
                        if field == 'x_name':
                            domain[0] = 'id'
                            valid_domains.append(domain)
                        elif field == 'x_company_id':
                            if model_has_company_id:
                                domain[0] = 'company_id'
                                valid_domains.append(domain)
                            # Skip this domain condition if model doesn't have company_id
                        elif field == 'id':
                            # Skip id conditions
                            pass
                        else:
                            ks_column = request.env['ir.model.fields'].sudo().search(
                                [('name', '=', field), ('model', '=', model)])
                            if ks_column:
                                ks_column.ensure_one()
                                ks_column_field = ks_report_record.ks_cr_column_ids.search([('ks_cr_field_id', '=', ks_column.id)])
                                if ks_column_field:
                                    domain[0] = ks_column_field.ks_model_field_chan
                            valid_domains.append(domain)
                    else:
                        # Keep operators - we'll validate them later
                        valid_domains.append(domain)
                
                # Clean up domain: ensure operators have enough operands
                # Odoo uses prefix notation, so operators come before operands
                if valid_domains:
                    condition_count = sum(1 for d in valid_domains if d not in ['&', '|', '!'])
                    operator_count = sum(1 for d in valid_domains if d in ['&', '|'])
                    
                    # For prefix notation with N conditions, we need exactly N-1 binary operators
                    # If we don't have enough conditions for the operators, remove operators
                    if condition_count == 0:
                        ks_domain = []
                    elif operator_count >= condition_count:
                        # Too many operators, keep only conditions
                        ks_domain = [d for d in valid_domains if d not in ['&', '|', '!']]
                    else:
                        # Domain structure should be valid, but remove trailing operators just in case
                        ks_domain = valid_domains[:]
                        while ks_domain and ks_domain[-1] in ['&', '|', '!']:
                            ks_domain.pop()
                else:
                    ks_domain = []
            else:
                for domain in domains:
                    if type(domain).__name__ == 'list':
                        field = domain[0]
                        if field.startswith("x_"):
                            field = field[2:]
                        domain[0] = field
                    ks_domain.append(domain)

        # Get display name from the model
        display_name = ks_report_record.ks_model_id.display_name if ks_report_record.ks_model_id else (ks_report_record.ks_cr_model_id.name if ks_report_record.ks_cr_model_id else '')
        
        return {
            'name': display_name,
            'context': request.env.context,
            'view_type': 'list',
            'view_mode': 'list',
            'domain': ks_domain,
            'views': [[False, 'list'], [False, 'form']],
            'res_model': ks_model,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
