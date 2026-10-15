/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const PERIODS = [
    ["month", _t("This Month")],
    ["quarter", _t("This Quarter")],
    ["year", _t("This Year")],
    ["all", _t("All Time")],
];

const STATE_BADGE = {
    draft: "text-bg-secondary",
    request: "text-bg-info",
    confirm: "text-bg-info",
    payment: "text-bg-warning",
    approve: "text-bg-success",
    done: "text-bg-success",
    reject: "text-bg-danger",
    cancel: "text-bg-danger",
};

export class PettyCashDashboard extends Component {
    static template = "dev_petty_cash.PettyCashDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.periods = PERIODS;
        this.stateBadge = STATE_BADGE;
        this.state = useState({ loading: true, period: "year", journalId: false, data: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("petty.cash.dashboard", "get_dashboard_data", [], {
            period: this.state.period,
            journal_id: this.state.journalId,
        });
        this.state.loading = false;
    }

    get data() {
        return this.state.data;
    }

    // ── formatting ──────────────────────────────────────────────────────────

    fmt(value) {
        return formatMonetary(value || 0, { currencyId: this.data.currency_id });
    }

    pct(value, max) {
        return max ? Math.max(2, Math.round((100 * value) / max)) : 0;
    }

    spentShare(row) {
        return row.funded ? Math.min(100, Math.round((100 * row.spent) / row.funded)) : 0;
    }

    get monthlyMax() {
        return Math.max(0, ...this.data.monthly.map((m) => Math.max(m.funded, m.spent)));
    }

    get headsMax() {
        return Math.max(0, ...this.data.heads.map((h) => h.amount));
    }

    get employeesMax() {
        return Math.max(0, ...this.data.employees.map((e) => e.funded));
    }

    get utilisationStyle() {
        const pct = Math.min(100, this.data.kpi.utilisation);
        return `background: conic-gradient(#E4685D 0 ${pct}%, #e9ecef ${pct}% 100%);`;
    }

    // ── toolbar ─────────────────────────────────────────────────────────────

    async setPeriod(period) {
        this.state.period = period;
        await this.load();
    }

    async onJournalChange(ev) {
        this.state.journalId = parseInt(ev.target.value) || false;
        await this.load();
    }

    // ── navigation ──────────────────────────────────────────────────────────

    periodDomain() {
        const domain = [];
        if (this.state.journalId) {
            domain.push(["petty_journal_id", "=", this.state.journalId]);
        }
        return domain;
    }

    openList(model, name, domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            domain: [...this.periodDomain(), ...domain],
            target: "current",
        });
    }

    openReport() {
        this.action.doAction("dev_petty_cash.action_petty_cash_report", {
            additionalContext: this.state.journalId ? { default_journal_ids: [this.state.journalId] } : {},
        });
    }

    openRecord(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    newDocument(model, journalId) {
        const context = {};
        if (journalId || this.state.journalId) {
            context.default_petty_journal_id = journalId || this.state.journalId;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "form"]],
            context,
            target: "current",
        }, { onClose: () => this.load() });
    }

    openJournalEntries(journalId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Petty Cash Journal Items"),
            res_model: "account.move.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["journal_id", "=", journalId], ["parent_state", "=", "posted"]],
            target: "current",
        });
    }

    async approve(request) {
        await this.orm.call("petty.cash.request", "action_approve", [[request.id]]);
        this.notification.add(_t("%s approved and paid into petty cash.", request.name), { type: "success" });
        await this.load();
    }
}

registry.category("actions").add("dev_petty_cash.dashboard", PettyCashDashboard);
