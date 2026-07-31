import { Component, useState, onWillStart } from "@odoo/owl";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { KsItem } from "@ks_dashboard_ninja/components/ks_dashboard_items/ks_item";
import { registry } from "@web/core/registry";
import { deepCopy } from "@web/core/utils/objects";

export class ItemPreview extends Component {

    static template = 'ks_dashboard_ninja.ks_item_preview'
    static components = { KsItem }

    setup(){
        this.state = useState({frontendData: false, render: 0})
        this.orm = useService("orm")

        onWillStart(async () => {
            if(this.props.record.resId && this.props.record.data[this.props.clearFrontendDataField]){
                await this.orm.call("ks_dashboard_ninja.item", "compute_frontend_data", [this.props.record.resId], {})
                await this.props.record.model.load()
            }
            this.props.record.update({
                [this.props.triggerComputeField]: this.props.record.data[this.props.triggerComputeField] + 1
            })
        })

        useRecordObserver(this.recordObserver.bind(this))
    }

    recordObserver(record){
        if(this.props.record.data[this.props.clearFrontendDataField])   return
        this.state.frontendData = deepCopy(record.data[this.props.name])
        this.state.render += 1
    }

    get componentProps() {
        const interactiveFeatures = ['pagination', 'drillDownPopover', 'itemPopover', 'xyChartExporting']

        return {
            data: this.state.frontendData,
            toDisable: {
                lazyDataFetching: true,
                ...Object.fromEntries(interactiveFeatures.map(feature => [feature, true]))
            },
            filters: {}
        };
    }

}

export const ItemPreviewWidget = {
    component: ItemPreview,
    supportedTypes: ["json"],
    supportedOptions: [
        { name: "type_field", type: "field", availableTypes: ["char"] }
    ],
    extractProps: ({ attrs, options }) => ({
        itemType: options.type_field,
        triggerComputeField: options.trigger_frontend_data_compute,
        clearFrontendDataField: options.clear_frontend_data_field,
    }),
}

registry.category("fields").add("dn_item_preview", ItemPreviewWidget)