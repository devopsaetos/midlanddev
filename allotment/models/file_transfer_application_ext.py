from odoo import fields, models, api


class FileTransferApplicationExt(models.Model):
    _inherit = 'transfer.application'

    def file_transfer(self):

        res = super(FileTransferApplicationExt, self).file_transfer()

        # Creating File Print Request
        print_queue = self.env['print.queue'].create({
            'document_type': 'file',
            'allotment': 'transfer',
            'transaction_ref': self.name,
            'transfer_application_id': self.id,
            'member_ids': [(6, 0, self.membership_id.ids)],
            'files_ids': [(6, 0, self.file_id.ids)]

        })

        return res
