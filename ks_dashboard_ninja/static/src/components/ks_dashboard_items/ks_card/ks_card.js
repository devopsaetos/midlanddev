import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import {
    ksFormatter, splitAggregate, setupPopoverActions, itemStandardProps, itemStandardDefaultProps
} from "@ks_dashboard_ninja/components/ks_dashboard_items/item_util";

export class KsCard extends Component {

    static template = "ks_dashboard_ninja.ks_card"
    static props = {
        ...itemStandardProps,
        callbacks: { type: Object, optional: true },
    }
    static defaultProps = { ...itemStandardDefaultProps, callbacks: {} }

    setup(){
        this.rootRef = useRef("rootRef")
        this.sectionsRef = useRef("sectionsRef")
        this.dataFetching = this.props.callbacks.dataFetching ?? (() => {})

        this.popoverAction = setupPopoverActions({
            getDataCb: () => this.props.data, callbacks: {dataFetching: this.dataFetching.bind(this)},
            refToPopover: this.sectionsRef, toDisable: {drillDown: true}
        })
    }

    getSectionName(source, sequencedAggregate){
        const aggregate = splitAggregate(sequencedAggregate)
        return source.aggregates_data[aggregate].field_description
    }

    getSequencedAggregateValue(sequencedAggregate){
        const formattedRecordData = this.props.data.formatted_groupby_record_mapped_data['__all']
        return formattedRecordData[sequencedAggregate] ?? '-'
    }

    formatter(source, sequencedAggregate){
        const aggregate = splitAggregate(sequencedAggregate)
        let value = this.getSequencedAggregateValue(sequencedAggregate)

        value = ksFormatter({
            valueStr: value, numberFormattingData: this.props.data.model_data.number_formatting_data,
            aggregatesData: source.aggregates_data, sequencedAggregate, fieldsData: source.fields_data
        })

        return value
    }

    openDrillDownPopover(ev, source){
        if (this.props.toDisable.drillDownPopover) return

        this.popoverAction.openDrillDownPopover({
            pointerEvent: ev, source: source,
            formattedSourceRecord: this.props.data.formatted_groupby_record_mapped_data['__all'],
        })
    }
};

const cardInfo = {
    component: KsCard,
}

registry.category("ks_dashboard_ninja.dashboard_items").add('card', cardInfo)
