/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

export class ComparativeStatementAction extends Component {
    static template = "purchase_requisitions.Main";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const context = this.props.action.context || {};
        this.rfq_id = context.rfq_id;
        this.rfq_code = context.rfq_code;
        this.rfq_date = context.rfq_date;
        this.cs_state = context.state;
        this.comparative_statement_id = context.comparative_statement_id;

        this.state = useState({
            rendered: false,
            header1: [],
            header2: [],
            herder_data: [],
            lines_data: [],
            vendor_citeria: [],
            total_values_qouatations: {},
            rfq_code: this.rfq_code,
            rfq_date: this.rfq_date,
            cs_state: this.cs_state,
        });

        onMounted(() => this._loadData());
    }

    async _loadData() {
        if (!this.rfq_id) {
            window.history.back();
            return;
        }

        try {
            const rawData = await this.orm.call(
                "comparative.statement",
                "show_comparative_statement",
                [this.rfq_id]
            );

            const data = JSON.parse(rawData);
            const header = Object.keys(data[0]);

            this.state.header1 = header.slice(0, 4);
            this.state.header2 = header.slice(4);
            this.state.herder_data = this.state.header2.map(h => Object.assign({}, h.split(",")));

            const linesRaw = await this.orm.call(
                "comparative.statement",
                "prepare_lines_data",
                [rawData]
            );
            this.state.lines_data = JSON.parse(linesRaw);

            const criteriaRaw = await this.orm.call(
                "comparative.statement",
                "prepare_vendor_citreia_lines",
                [JSON.stringify(this.state.herder_data)]
            );
            this.state.vendor_citeria = criteriaRaw.length ? JSON.parse(criteriaRaw) : [];

            const totalRaw = await this.orm.call(
                "comparative.statement",
                "prepare_total_qoutations",
                [JSON.stringify(this.state.herder_data)]
            );
            this.state.total_values_qouatations = JSON.parse(totalRaw);
            this.state.rendered = true;
        } catch (e) {
            console.error("Comparative statement load error:", e);
        }
    }

    async onViewQuotation(ev) {
        ev.preventDefault();
        const id = parseInt(ev.currentTarget.dataset.moveId) || false;
        if (!id) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            view_mode: "form",
            res_model: "quotation.order",
            views: [[false, "form"]],
            res_id: id,
            target: "current",
        });
        this.notification.add("Window has been redirected", { title: "Redirected", type: "info" });
    }

    async onApproveQuotation(ev) {
        const id = parseInt(ev.currentTarget.dataset.moveId) || false;
        if (!id) return;
        try {
            await this.orm.call(
                "comparative.statement",
                "approve_quotation",
                [id, this.comparative_statement_id]
            );
            const btns = document.querySelectorAll(".approve-qoutation-li");
            btns.forEach(btn => (btn.style.display = "none"));
        } catch (e) {
            console.error("Approve quotation error:", e);
        }
    }
}

registry.category("actions").add("comparative_statement_view", ComparativeStatementAction);