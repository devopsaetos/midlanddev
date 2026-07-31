import { Component, useEffect, useRef, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { AmChartBuilder } from "@ks_dashboard_ninja/components/ks_dashboard_items/amchart_util";
import {
    setupPopoverActions, itemStandardProps, itemStandardDefaultProps
} from "@ks_dashboard_ninja/components/ks_dashboard_items/item_util";

export class KsAmChart extends Component {

    static template = "ks_dashboard_ninja.ks_am_chart"
    static props = {
        ...itemStandardProps,
        callbacks: { type: Object, optional: true },
    }
    static defaultProps = { ...itemStandardDefaultProps, callbacks: {} }

    setup() {
        this.rootRef = useRef("rootRef");
        this.chartRef = useRef("chartRef");
        this.amChartBuilder = false;
        this.activeChartActions = false
        this.dataFetching = this.props.callbacks.dataFetching ?? (() => {})

        this.popoverAction = setupPopoverActions({
            getDataCb: () => this.props.data, callbacks: {dataFetching: this.dataFetching.bind(this)}, toDisable: {},
            refToPopover: this.chartRef
        })

        useEffect(() => this.buildChart(), () => [this.props.data]);
        
        onWillUnmount(() => {
            if (this.amChartBuilder && this.amChartBuilder.root) {
                this.amChartBuilder.root.dispose();
                this.amChartBuilder = false;
            }
        });
    }

    buildChart() {
        if (this.amChartBuilder) this.amChartBuilder.root.dispose();
        if (!this.chartRef.el) return;

        delete this.amChartBuilder;
        let openDrillDownPopoverCb = (amEvent) => {
            if (this.props.toDisable.drillDownPopover) return

            const userData = amEvent.target.dataItem.component.get("userData");
            this.popoverAction.openDrillDownPopover({
                pointerEvent: amEvent.originalEvent,
                formattedSourceRecord: amEvent.target.dataItem.dataContext,
                source: userData.sourceData
            });
        };

        this.amChartBuilder = new AmChartBuilder({
            element: this.chartRef.el, data: this.props.data, callbacks: { openDrillDownPopoverCb },
            toDisable: this.props.toDisable
        });
        this.amChartBuilder.build();
    }
};

const xyChartInfo = {
    component: KsAmChart,
}

registry.category("ks_dashboard_ninja.dashboard_items").add('xy_chart', xyChartInfo)


