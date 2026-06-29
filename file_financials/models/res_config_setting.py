from odoo import api, fields, models, _


class ResCompanyFileAccount(models.Model):
    _inherit = "res.company"

    investment_file_journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ['cash', 'bank'])], readonly=False)
    owner_mobile = fields.Char(string='Owner Mobile #')
    confirmation_adjustment_journal_id = fields.Many2one('account.journal', 'Confirmation Adjustment Journal')
    confirmation_adjustment_account_id = fields.Many2one('account.account', string='Confirmation Adjustment Account')
    commission_adjustment_account_id = fields.Many2one('account.account', string='Commission Adjustment Account')
    mobile_numbers = fields.Many2many('owner.mobile', string="Mobile Numbers")
    file_signature_email = fields.Boolean(string="Send E Signature Email on File Lock ?", default=False)


class ResConfigSettingsFileAccounting(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _get_default_confirmation_adjustment_account_id(self):
        return self.env.company.confirmation_adjustment_account_id

    @api.model
    def _get_default_confirmation_adjustment_journal_id(self):
        return self.env.company.confirmation_adjustment_journal_id

    @api.model
    def _get_default_commission_adjustment_account_id(self):
        return self.env.company.commission_adjustment_account_id

    # @api.model
    # def _get_default_file_signature_email(self):
    #     return self.env.company.file_signature_email

    confirmation_adjustment_account_id = fields.Many2one('account.account', string='Confirmation Adjustment Account', default=_get_default_confirmation_adjustment_account_id,
                                                         help="The account must be reconcilable")
    investment_file_journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ['cash', 'bank'])],
                                                 readonly=False, related='company_id.investment_file_journal_id')
    confirmation_adjustment_journal_id = fields.Many2one('account.journal', 'Confirmation Adjustment Journal', default=_get_default_confirmation_adjustment_journal_id, help="""Default Confirmation Adjustment journal 
            for the current user's company.""")
    commission_adjustment_account_id = fields.Many2one('account.account', 'Commission Adjustment Account', default=_get_default_commission_adjustment_account_id, help="""Default Confirmation 
    Adjustment Account for the current user's company.""")
    file_signature_email = fields.Boolean(string="Send E Signature Email on File Lock ?", related="company_id.file_signature_email", readonly=False)

    def set_values(self):
        super(ResConfigSettingsFileAccounting, self).set_values()
        if self.confirmation_adjustment_account_id:
            self.env.company.sudo().confirmation_adjustment_account_id = self.confirmation_adjustment_account_id
        if self.confirmation_adjustment_journal_id:
            self.env.company.sudo().confirmation_adjustment_journal_id = self.confirmation_adjustment_journal_id
        if self.commission_adjustment_account_id:
            self.env.company.sudo().commission_adjustment_account_id = self.commission_adjustment_account_id
        # if self.file_signature_email:
        #     self.env.company.sudo().file_signature_email = self.file_signature_email


class OwnerMobileNumbers(models.Model):
    _name = 'owner.mobile'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Owner Mobile Numbers'

    name = fields.Char(string='Name', tracking=True)
    number = fields.Char(string='Mobile Number', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)