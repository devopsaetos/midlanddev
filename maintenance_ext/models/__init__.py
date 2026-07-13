# -*- coding: utf-8 -*-

from . import tool_allocation
# Odoo 19 migration note: 'issue_requistion' (the module providing the 'issue.requistion'
# base model this file inherits) is not available in this Odoo 19 project - importing it
# would fail immediately at load time since the base model it _inherit's would not exist.
# Left un-imported (module stays inert/dead) rather than deleted - see
# models/issue_requistion.py and __manifest__.py for details.
# from . import issue_requistion
from . import maintenance_request
from . import helpdesk_ticket
from . import purchase_requisition
