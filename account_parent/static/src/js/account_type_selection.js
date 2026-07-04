/** @odoo-module **/

import { AccountTypeSelection } from "@account/components/account_type_selection/account_type_selection";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
//    const patchMixin = require("web.patchMixin");
//    const PatchableAttachment = patchMixin(Attachment);

//const {QWeb, Context} = owl;
patch(AccountTypeSelection.prototype, {
    setup() {
        super.setup();
        const viewChoices = this.choices.filter(x => x.value === 'view');
        if (viewChoices.length) {
            const otherGroup = this.groups.find(g => g.label === _t('Other'));
            if (otherGroup && !otherGroup.choices.find(c => c.value === 'view')) {
                otherGroup.choices.push(...viewChoices);
            }
        }
    }
});



