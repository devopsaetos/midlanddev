/** @odoo-module */

//
import { patch } from "@web/core/utils/patch";
import { SwitchCompanyMenu } from "@web/webclient/switch_company_menu/switch_company_menu";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";



patch(SwitchCompanyMenu.prototype, {
    setup() {
        super.setup();
        this.user = user;
        debugger;
        var companyId = this.user.activeCompanies

        this.rpc = rpc
        const orm = useService("orm");
        orm.call(
            'ks_custom_report.ks_report',
            'ks_get_company_wise_data',
            [companyId],
        );
    }
});
