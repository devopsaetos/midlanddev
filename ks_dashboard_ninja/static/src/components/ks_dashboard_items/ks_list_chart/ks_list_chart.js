import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import {
    splitAggregate, ksFormatter, setupPopoverActions, itemStandardProps, itemStandardDefaultProps
} from "@ks_dashboard_ninja/components/ks_dashboard_items/item_util";

export class KsListChart extends Component {

    static template = "ks_dashboard_ninja.ks_list_chart"
    static props = {
        ...itemStandardProps,
        callbacks: { type: Object, optional: true },
    }
    static defaultProps = { ...itemStandardDefaultProps, callbacks: {} }

    setup() {
        this.currentOffset = 0;
        this.doingJob = false;
        this.rootRef = useRef("rootRef")
        this.tableRef = useRef("tableRef")
        this.dataFetching = this.props.callbacks.dataFetching ?? (() => {})

        this.popoverAction = setupPopoverActions({
            getDataCb: () => this.props.data, toDisable: {}, refToPopover: this.tableRef,
            callbacks: {dataFetching: this.dataFetching.bind(this), resetSettings: this.resetSettings.bind(this)}
        });
    }

    get pagination() {
        return this.props.data.model_data.ks_pagination;
    }

    get totalGroupbyValues() {
        return this.props.data.sources.reduce((sum, src) => sum + src.groupby_values.length, 0)
    }

    get maxTotalLength() {
        return this.props.data.sources.reduce((max, src) => Math.max(max, src.total_length || 0), 0)
    }

    getSequencedAggregateValue(sequencedAggregate, groupby_data){
        const groupbyValue = groupby_data['__groupby_value']
        const formattedSourceRecord = this.props.data.formatted_groupby_record_mapped_data[groupbyValue]

        return formattedSourceRecord[sequencedAggregate]
    }

    getHeaderCell(sequencedAggregate, source){
        const aggregate = splitAggregate(sequencedAggregate)
        return source.aggregates_data[aggregate].field_description
    }

    getRowCell(sequencedAggregate, groupby_data, source){
        let cellValue = this.getSequencedAggregateValue(sequencedAggregate, groupby_data)

        if(cellValue === undefined)   return '-'

        cellValue = ksFormatter({
            valueStr: cellValue, numberFormattingData: this.props.data.model_data.number_formatting_data,
            aggregatesData: source.aggregates_data, sequencedAggregate, fieldsData: source.fields_data
        })
        
        return cellValue
    }

    resetSettings(){
        this.doingJob = false
        this.currentOffset = 0
    }

    async onPageUpdate(direction) {
        if (this.doingJob) return;

        this.doingJob = true
        const limit = this.pagination;
        const total = this.maxTotalLength
        let offset = this.currentOffset + limit * direction

        if(offset >= total){
            offset = 0;
        } else if (offset < 0) {
            offset = total - (total % limit || limit)
        }

        this.currentOffset = offset
        if (this.props.callbacks?.dataFetching) {
            const kwargs = this.popoverAction.kwargs?.() ?? {}
            await this.props.callbacks.dataFetching?.({ kwargs: {...kwargs, offset} })
        }
        this.doingJob = false
    }

    get totalPagesCount(){
        return Math.ceil(this.maxTotalLength/this.pagination)
    }

    get currentPageCount(){
        return Math.floor(this.currentOffset/this.pagination) + 1
    }

    openDrillDownPopover(ev, sequencedAggregate, groupby_data, source){
        if (this.props.toDisable.drillDownPopover) return

        const groupbyValue = groupby_data['__groupby_value']
        let cellValue = this.getSequencedAggregateValue(sequencedAggregate, groupby_data)
        if(cellValue === undefined)   return

        const formattedSourceRecord = this.props.data.formatted_groupby_record_mapped_data[groupbyValue]
        this.popoverAction.openDrillDownPopover({pointerEvent: ev, formattedSourceRecord, source})
    }

};

const listChartInfo = {
    component: KsListChart,
}

registry.category("ks_dashboard_ninja.dashboard_items").add('grouped_list', listChartInfo)
