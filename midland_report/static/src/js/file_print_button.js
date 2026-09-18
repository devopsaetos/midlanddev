/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, onWillStart, useState } from "@odoo/owl";

// Odoo's own form-view "Print" entry only shows inside the cog (Actions)
// menu, not as a standalone button - this widget gives the File form a
// visible "Print" button (matching the old single-report shortcut it
// replaces) whose dropdown lists every report actually bound to the file
// model (binding_type=report), so it never goes stale if reports are
// added/removed/hidden later.
export class FilePrintButton extends Component {
    static template = "midland_report.FilePrintButton";
    static components = { Dropdown, DropdownItem };
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ reports: [] });
        onWillStart(async () => {
            this.state.reports = await this.orm.searchRead(
                "ir.actions.report",
                [
                    ["binding_model_id.model", "=", "file"],
                    ["binding_type", "=", "report"],
                ],
                ["id", "name"],
                { order: "id asc" }
            );
        });
    }

    async onClickReport(report) {
        const resId = this.props.record.resId;
        await this.action.doAction(report.id, {
            additionalContext: {
                active_id: resId,
                active_ids: [resId],
                active_model: "file",
            },
        });
    }
}

registry.category("view_widgets").add("file_print_button", {
    component: FilePrintButton,
});
