import { useBus } from "@web/core/utils/hooks";
import { useComponent, reactive, onWillStart, useState } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";
import { DropdownPopover } from "@web/core/dropdown/_behaviours/dropdown_popover";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { formatCurrency } from "@web/core/currency";
import { humanNumber, insertThousandsSep, roundDecimals } from "@web/core/utils/numbers";
import { localization } from "@web/core/l10n/localization";
import { getCurrency } from "@web/core/currency";
import { formatFloat } from "@web/views/fields/formatters";
import { nbsp } from "@web/core/utils/strings";
import { useService } from "@web/core/utils/hooks";
import { Domain } from "@web/core/domain";

export const NUMERIC_TYPE_FIELDS = ['int', 'float', 'monetary']

export const itemStandardProps = {
    data: { type: Object, validate: (v) => Object.keys(v).includes("sources") },
    toDisable: {type: Object},
    dashboardData: { type: Object, optional: true },
    filters: { type: Object, optional: true },
    options: { type: Object, optional: true }, // Extra Data
}
export const itemStandardDefaultProps = { options: {}, filters: {}, dashboardData: {} }

export function splitAggregate(sequenced_aggregate){
    return sequenced_aggregate.split(".")[1]
}

export function splitFieldName(aggregate){
    return aggregate.split(":")[0]
}

/**
 * @param {Object} params - params to be used for setup lazy data fetching
 * params are { id, bus, dataFetchCallback, eventPrefix }
 */
export function setupLazyDataFetching(params){
    let component = useComponent() // todo: remove this (maybe unnecessary)

    useBus(params.bus, `${params.eventPrefix}${params.id}`, ({ detail }) => {
        if(detail.isForced || component.allowItemFetching){
            params.dataFetchCallback({ isForced: detail.isForced || false })
        }
        if(detail.allowItemFetching){
            component.allowItemFetching = true
        }

    })
}

// todo: view can also be open in various target like new, current through popover selection
export function ksOpenModelView(data, source, formattedSourceRecord, actionService){
    const parentSourceSequence = source.parent_drill_down_source_sequence
    const sourceRecordDomain = formattedSourceRecord[`${source.model_data.sequence}.__extra_domain`]
    const drillDownData = data.drill_down_data.parent_sources_data[parentSourceSequence]
    const action = {
        name: _t(source.model_data.name),
        type: 'ir.actions.act_window',
        res_model: source.model_data.model_name,
        domain: Domain.and([sourceRecordDomain, source.domain]).toList(),
        views: [[false, 'list'], [false, 'form']],
        view_mode: 'list, form',
        target: 'current',
        context: {
            form_view_ref: drillDownData.form_view_id,
            list_view_ref: drillDownData.list_view_id,
            'group_by': source.groupby_name || false
        }
    }
    actionService.doAction(action, {})
}

export function ksFormatter({valueStr, numberFormattingData, aggregatesData, fieldsData, sequencedAggregate}){
    const aggregate = splitAggregate(sequencedAggregate)
    const fieldName = splitFieldName(aggregate)
    const humanReadable = numberFormattingData.number_format_lines?.length ? true : false
    let numericValue = parseFloat(valueStr)

    if(!NUMERIC_TYPE_FIELDS.includes(fieldsData[fieldName]?.type)){
        return valueStr
    }

    const showCurrency = aggregatesData[aggregate].show_currency
    const { min_integral_digits, precision_digits, enable_number_formatting } = numberFormattingData

    let options = enable_number_formatting ? {
        minDigits: min_integral_digits, decimals: precision_digits, numberFormattingData, humanReadable
    } : {}

    if (showCurrency) {
        valueStr = ksFormatCurrency(numericValue, options)
    }
    else if(enable_number_formatting && humanReadable){
        valueStr = ksHumanNumber(numericValue, options)
    }

    return valueStr
}

function ksFormatFixedDecimals(value, decimals) {
    const rounded = roundDecimals(value, decimals);
    const [intPart, decPart = ""] = rounded.toString().split(".");
    const paddedDecimals = decPart.padEnd(decimals, "0").slice(0, decimals);
    return decimals === 0 ? intPart : `${intPart}.${paddedDecimals}`;
}

export function ksFormatCurrency(amount, options = {}) {
    const currency = getCurrency(user.activeCompany.currency_id)
    const digits = options.digits || (currency && currency.digits);

    let formattedAmount;
    if (options.humanReadable) {
        formattedAmount = ksHumanNumber(amount, {
            decimals: digits ? digits[1] : 2,
            minDigits: options.minDigits,
            numberFormattingData: options.numberFormattingData,
        });
    } else {
        formattedAmount = formatFloat(amount, { digits, trailingZeros: options.trailingZeros });
    }

    if (!currency || options.noSymbol) {
        return formattedAmount;
    }
    const formatted = [currency.symbol, formattedAmount];
    if (currency.position === "after") {
        formatted.reverse();
    }
    return formatted.join(nbsp);
}

/**
 * Format number with dynamic number system support
 * Similar to humanNumber but supports custom number_format_lines
 */
export function ksHumanNumber(number, { decimals, minDigits, numberFormattingData }) {

    const numberFormatLines = numberFormattingData.number_format_lines;

    const d2 = Math.pow(10, decimals);
    const numberMagnitude = +number.toExponential().split("e+")[1];
    number = Math.round(number * d2) / d2;

    // Handle very large numbers with scientific notation
    if (numberMagnitude >= 21) {
        number = Math.round(number * Math.pow(10, decimals - numberMagnitude)) / d2;
        return `${number}e+${numberMagnitude}`;
    }
    
    const sign = Math.sign(number);
    number = Math.abs(number);
    let symbol = "";
    
    for (const line of numberFormatLines) {
        const s = line.number;
        if (s <= number / Math.pow(10, minDigits - 1)) {
            number = Math.round((number * d2) / s) / d2;
            symbol = line.suffix || "";
            break;
        }
    }
    
    const { decimalPoint, grouping, thousandsSep } = localization;
    const decimalsToKeep = number >= 1000 ? 0 : decimals;
    number = sign * number;
    const [integerPart, decimalPart] = ksFormatFixedDecimals(number, decimalsToKeep).split(".");
    const int = insertThousandsSep(integerPart, thousandsSep, grouping);
    
    if (!decimalPart) {
        return int + symbol;
    }
    return int + decimalPoint + decimalPart + symbol;
}

export function setupPopoverActions({ getDataCb, callbacks, refToPopover, toDisable }){
    let component = useComponent()
    component.actionService = useService("action")
    const dataFetching = callbacks.dataFetching ?? (() => {})
    const editItem = callbacks.editItem ?? (() => {})
    const deleteItem = callbacks.deleteItem ?? (() => {})
    component.lastPointerEvent = false
    component.drillDownState = useState({ drillDowns: []})

    const onPositioned = (popoverEl, solution) => {
        const direction = solution.direction ?? "right"
        popoverEl.style.top = `${component.lastPointerEvent.clientY - 10}px`

        if(direction === "right") popoverEl.style.left = `${component.lastPointerEvent.clientX + 20}px`
        else popoverEl.style.left = `${component.lastPointerEvent.clientX - popoverEl.offsetWidth - 20 }px`

        popoverEl.style.maxHeight = `${window.innerHeight - component.lastPointerEvent.clientY}px`;
    }

    const options = {
        animation: false, position: "right-start", onPositioned,
        popoverClass: "ks-dropdown-menu ks-popover-scrollable"
    }
    component.popoverRefresher = reactive({ token: 0 })
    component.popover = usePopover(DropdownPopover, options)

    const maxDrillDownLength = () => {
        let data = getDataCb()
        const parentSourcesData = data.drill_down_data.parent_sources_data ?? {}
        return Object.values(parentSourcesData).reduce((max, source) => {
            return Math.max(max, source.model_data_sources.length || 0)
        }, 0)
    }

    const resetSettings = () => {
        component.popover.close()
        callbacks.resetSettings ? callbacks.resetSettings() : false
    }

    const kwargs = () => {
        const drillDowns = component.drillDownState.drillDowns
        return drillDowns.length ? { drill_down_data: drillDowns[drillDowns.length - 1] } : {}
    }

    const drillDown = ({source, formattedSourceRecord}) => {
        component.popover.close()
        let data = getDataCb()

        if(component.drillDownState.drillDowns.length >= maxDrillDownLength()){
            ksOpenModelView(data, source, formattedSourceRecord, component.actionService)
            return
        }

        let drillToLevel = component.drillDownState.drillDowns.length + 1
        let currentSourcesData = {}

        data.sources.forEach(source => {
            const parentSourceSequence = source.parent_drill_down_source_sequence
            const parentSourceData = data.drill_down_data.parent_sources_data[parentSourceSequence]
            const condition1 = parentSourceData.model_data_sources.length >= drillToLevel
            const condition2 = source.groupby_values.includes(formattedSourceRecord['__groupby_value'])

            if(condition1 && condition2){
                const sequence = source.model_data.sequence
                const modelData = parentSourceData.model_data_sources[drillToLevel - 1]
                const domainKey = `${sequence}.__extra_domain`
                currentSourcesData[modelData.sequence] = {
                    id: modelData.id,
                    domain: Domain.and([formattedSourceRecord[domainKey], source.domain]).toList()
                }
            }
        })

        component.drillDownState.drillDowns.push({
            ...data.drill_down_data, level: drillToLevel, current_sources_data: currentSourcesData
        })
        dataFetching({ kwargs: kwargs() })
    }

    const drillUp = ({drillDownData}) => {
        resetSettings()
        component.drillDownState.drillDowns.splice(drillDownData.level)
        dataFetching({ kwargs: kwargs() })
    }

    const oneLevelUp = () => {
        resetSettings()
        component.drillDownState.drillDowns.pop()
        dataFetching({ kwargs: kwargs() })
    }

    const drillToTop = () => {
        resetSettings()
        component.drillDownState.drillDowns = []
        dataFetching({ kwargs: kwargs() })
    }

    const open = (pointerEvent, props) => {
        if (component.popover.isOpen) component.popover.close()
        if (!refToPopover.el) return

        component.lastPointerEvent = pointerEvent
        component.popover.open(refToPopover.el, props)
    }

    const openDrillDownPopover = ({pointerEvent, source, formattedSourceRecord}) => {
        let data = getDataCb()

        let items = [{
            label: "Open View",
            onSelected: () => ksOpenModelView(data, source, formattedSourceRecord, component.actionService)
        }]

        if(!toDisable.drillDown){
            items.push(
                {label: "Drill To Top", onSelected: drillToTop},
                {label: "Drill Down", onSelected: () => drillDown({source, formattedSourceRecord})}
            )
            component.drillDownState.drillDowns.forEach((drillDownData) => {
                items.push({label: `Drill To Level-${drillDownData.level}`, onSelected: () => drillUp({drillDownData})})
            })
        }

        const props = { items, refresher: component.popoverRefresher, slots: {} }
        open(pointerEvent, props)
    }

    const openItemPopover = ({pointerEvent}) => {
        let items = [
            {label: "Edit Item", onSelected: () => editItem()},
            {label: "Delete Item", onSelected: () => deleteItem()}
        ]
        const props = { items, refresher: component.popoverRefresher, slots: {} }
        open(pointerEvent, props)
    }

    return {
        openDrillDownPopover, openItemPopover, oneLevelUp, popover: component.popover, kwargs
    }
}

