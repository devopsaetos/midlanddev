# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):
        """
        Block non-'View Users' group members from loading the form view of
        res.users — prevents direct URL access such as:
            #action=74&model=res.users&view_type=form&id=131

        Only 'form' is blocked here. Odoo 13 has no 'list' view type — it is
        'tree'. Blocking 'tree' caused a JS crash:
            TypeError: Cannot read properties of undefined (reading 'list')
        because when the action loads view_mode='tree,form', the tree view
        load failure left the JS action manager with undefined view data.

        Tree views (user selection dialogs, groups form, etc.) are intentionally
        left unrestricted here — access to the Users list is controlled via
        menu and action group restrictions in res_users.xml.

        The context key 'my_profile' (set on base.action_res_users_my) is the
        only exception: it lets every user open their own Preferences form.
        """
        if view_type == 'form':
            # env.su = True only for the internal ORM super-user; skip check.
            if not self.env.su:
                is_my_profile = self.env.context.get('my_profile', False)
                if not is_my_profile:
                    if not self.env.user.has_group('real_estate.group_view_users'):
                        raise AccessError(_(
                            'You do not have the required access rights to view '
                            'Users.\nPlease contact your system administrator.'
                        ))
        return super(ResUsers, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
