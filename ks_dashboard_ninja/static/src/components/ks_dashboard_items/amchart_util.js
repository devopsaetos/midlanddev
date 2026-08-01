import { getCurrency } from "@web/core/currency";
import { user } from "@web/core/user";
import { splitAggregate } from "@ks_dashboard_ninja/components/ks_dashboard_items/item_util";
import { deepCopy } from "@web/core/utils/objects";
import { localization } from "@web/core/l10n/localization";

export class AmChartBuilder {
    constructor({element, data, callbacks, toDisable}) {
        this.data = deepCopy(data)  // data is reactive
        this.isHorizontal = this.data.model_data.is_horizontal || false
        this.chartType = this.data.model_data.type
        this.chartName = this.data.model_data.name
        this.numberFormattingData = this.data.model_data.number_formatting_data || {}
        this.theme = this.data.model_data.theme
        this.formattedGroupbyRecordMappedData = this.data.formatted_groupby_record_mapped_data;
        this.openDrillDownPopoverCb = callbacks.openDrillDownPopoverCb ?? (() => {});
        this.editItemCb = callbacks.editItemCb ?? (() => {});
        this.currencyId = getCurrency(user.activeCompany.currency_id);
        this.groupbyName = '__groupby_value';
        this.element = element
        this.toDisable = toDisable
        this.isRtl = localization.direction === "rtl" ? true : false
    }

    build() {
        this.root = am5.Root.new(this.element)
        this.setupTheme()


        const availableCharts = {
            xy_chart: this.setupXyChart.bind(this)
        }
        availableCharts[this.chartType]()
    }

    setupXyChart(){
        const availableSeries = {
            line: this.setupLineSeries.bind(this), bar: this.setupColumnSeries.bind(this)
        }

        this.rendererOversizedBehaviour = this.data.model_data.renderer_oversized_behaviour
        this.isLegend = this.data.model_data.is_legend
        this.setupNumberFormatter()

        const zoomAxisLabel = this.isHorizontal ? "zoomY" : "zoomX";
        this.chart = this.root.container.children.push(
            am5xy.XYChart.new(this.root, {
                panX: true, panY: true, wheelX: "panX", wheelY: zoomAxisLabel, layout: this.root.verticalLayout,
                paddingLeft: 10, maxTooltipDistance: -1, pinchZoomX: true, paddingRight: 20, paddingBottom: 30
            })
        )
        this.setupScrollbar()
        this.setupCursor()
        this.setupYAxis()
        this.setupXAxis()

        if (this.isHorizontal) {
            this.yAxis.data.setAll(this.data.groupby_data_values);
        } else {
            this.xAxis.data.setAll(this.data.groupby_data_values);
        }


        // Process regular sources
        for (let i = 0; i < this.data.sources.length; i++) {
            let sourceData = this.data.sources[i];
            let seriesCb = availableSeries[sourceData.model_data.xy_type]

            for (let j = 0; j < sourceData.sequenced_aggregates.length; j++) {
                let sequencedAggregate = sourceData.sequenced_aggregates[j];
                const aggregate = splitAggregate(sequencedAggregate)
                const name = sourceData.aggregates_data[aggregate]?.field_description
                seriesCb({ sourceData, sequencedAggregate, name, toDisable: {} })
            }
        }

        // Process formula sources
        for (let i = 0; i < this.data.formula_sources.length; i++) {
            let formulaData = this.data.formula_sources[i];
            let seriesCb = availableSeries[formulaData.model_data.xy_type]

            for (let j = 0; j < formulaData.sequenced_aggregates.length; j++) {
                let sequencedAggregate = formulaData.sequenced_aggregates[j];
                seriesCb({
                    sourceData: formulaData, sequencedAggregate, name: formulaData.model_data.name,
                    toDisable: { seriesClickEvent: true }
                })
            }
        }

        if(this.isLegend)   this.setupLegend()
        this.chart.appear(1000, 100)

        let timeout;
        const exporting = () => {
            if (timeout) clearTimeout(timeout)
            timeout = setTimeout(() => {
                this.setupExporting()
                this.root.events.off("frameended", exporting)
            }, 100)
        };

        if(!this.toDisable.xyChartExporting) this.root.events.on("frameended", exporting)
    }

    // ==================== Configuration & Setup ====================

    setupTheme() {
        switch (this.theme) {
            case "dark":
                this.root.setThemes([am5themes_Dataviz.new(this.root)]);
                break;
            case "material":
                this.root.setThemes([am5themes_Material.new(this.root)]);
                break;
            case "moonrise":
                this.root.setThemes([am5themes_Moonrise.new(this.root)]);
                break;
            default:
                this.root.setThemes([am5themes_Animated.new(this.root)]);
        }
    }

    setupNumberFormatter() {
        if (!this.numberFormattingData.enable_number_formatting) return;

        const precisionDigits = this.numberFormattingData.precision_digits || 0;

        let setting = {
            numberFormat: "#,###." + "0".repeat(precisionDigits)
        }

        if (this.numberFormattingData.number_format_lines && this.numberFormattingData.number_format_lines.length) {
            setting.numberFormat += 'a';
            setting.bigNumberPrefixes = this.numberFormattingData.number_format_lines;
        }
        
        this.root.numberFormatter.setAll(setting)
    }

    // ==================== UI Components ====================

    getLabel(labelSettings) {
        return am5.Label.new(this.root, {
            centerX: am5.p50, centerY: am5.p50, populateText: true, ...labelSettings
        });
    }

    getBulletLabelSprite(amSeries) {
        return this.getLabel({ text: "{valueY}" });
    }

    addCircularSpriteBullet(amSeries, sourceData, toDisable) {
        const openDrillDownPopoverCb = this.openDrillDownPopoverCb.bind(this)

        amSeries.bullets.push(function(root) {
            const isBullets = sourceData.model_data.is_bullets
            let sprite = am5.Circle.new(root, {
                radius: 5, fill: amSeries.get("fill"), cursorOverStyle: "pointer", fillOpacity: isBullets ? 1 : 0
            })

            if(!toDisable.seriesClickEvent){
                sprite.events.on("click", (ev) => openDrillDownPopoverCb(ev))
            }
            return am5.Bullet.new(root, {sprite})
        })
    }

    getAxesTooltip() {
        return am5.Tooltip.new(this.root, {});
    }

    getTooltip(showCurrency) {
        let tooltipLabel = this.isHorizontal ? "{name}: {valueX}" : "{name}: {valueY}"
        if (showCurrency) {
            tooltipLabel += ` (in ${this.currencyId.symbol})`
        }
        const pointerOrientation = this.isHorizontal ? "vertical" : "horizontal"

        return am5.Tooltip.new(this.root, {pointerOrientation, labelText: tooltipLabel});
    }

    // ==================== Axes Management ====================

    getXRenderer() {
        let xRenderer = am5xy.AxisRendererX.new(this.root, { minorLabelsEnabled: true,  minGridDistance: 60});
        xRenderer.grid.template.setAll({ location: 1 });
        return xRenderer;
    }

    getYRenderer() {
        return am5xy.AxisRendererY.new(this.root, { strokeOpacity: 0.1 });
    }

    getCategoryAxis(renderer) {
        return am5xy.CategoryAxis.new(this.root, {
            renderer: renderer, categoryField: this.groupbyName, tooltip: this.getAxesTooltip(), maxDeviation: 0.3
        });
    }

    getValueAxis(renderer) {
        return am5xy.ValueAxis.new(this.root, {
            min: 0, extraMax: 0.1, renderer: renderer, tooltip: this.getAxesTooltip(), maxDeviation: 0.3
        });
    }

    setupYAxis() {
        let renderer = this.getYRenderer();
        let axes = this.isHorizontal ? this.getCategoryAxis(renderer) : this.getValueAxis(renderer);
        this.yAxis = this.chart.yAxes.push(axes)
    }

    setupXAxis() {
        let renderer = this.getXRenderer()
        let axes = this.isHorizontal ? this.getValueAxis(renderer) : this.getCategoryAxis(renderer);
        this.xAxis = this.chart.xAxes.push(axes);

        if(!this.isHorizontal){
            this.xAxis.get("renderer").labels.template.setAll({
                oversizedBehavior: this.rendererOversizedBehaviour,
                textAlign: "center", ellipsis: "..."
            })
            this.xAxis.onPrivate("cellWidth", (cellWidth) => renderer.labels.template.set("maxWidth", cellWidth))
        }

    }

    // ==================== Series Management ====================

    getValueCategoryFieldSetting(groupbyName, sequencedAggregate){
        return this.isHorizontal
                ? { categoryYField: groupbyName, valueXField: sequencedAggregate }
                : { categoryXField: groupbyName, valueYField: sequencedAggregate }
    }

    setupDataProcessor(amSeries, sourceData) {
        amSeries.data.processor = am5.DataProcessor.new(this.root, {
            numericFields: sourceData.sequenced_aggregates
        });
    }

    getFormattedSourceRecords(formatted_groupby_record_mapped_data) {
        return Object.values(formatted_groupby_record_mapped_data);
    }

    setupColumnSeries({sourceData, sequencedAggregate, name, toDisable}) {
        const aggregate = splitAggregate(sequencedAggregate)
        const showCurrency = sourceData.aggregates_data?.[aggregate]?.show_currency
        const {
            categoryXField, categoryYField, valueXField, valueYField
        } = this.getValueCategoryFieldSetting(this.groupbyName, sequencedAggregate);

        let amSeries = this.chart.series.push(
            am5xy.ColumnSeries.new(this.root, {
                name: name, xAxis: this.xAxis, tooltip: this.getTooltip(showCurrency), yAxis: this.yAxis,
                categoryXField, categoryYField, valueXField, valueYField, userData: { sourceData }
            })
        );

        let radiusSettings = {}
        if(this.isHorizontal){
            radiusSettings = {cornerRadiusBR: 5, cornerRadiusTR: 5}
        }
        else {
            radiusSettings = {cornerRadiusTL: 5, cornerRadiusTR: 5}
        }

        amSeries.columns.template.setAll({
            ...radiusSettings, strokeOpacity: 0, cursorOverStyle: "pointer"
        })

        if(!toDisable.seriesClickEvent){
            amSeries.columns.template.events.on("click", (ev) => this.openDrillDownPopoverCb(ev));
        }

        this.setupDataProcessor(amSeries, sourceData)
        amSeries.data.setAll(this.getFormattedSourceRecords(this.formattedGroupbyRecordMappedData))
    }

    setupLineSeries({sourceData, sequencedAggregate, name, toDisable}) {
        const aggregate = splitAggregate(sequencedAggregate)
        const showCurrency = sourceData.aggregates_data?.[aggregate]?.show_currency
        const isAreaChart = sourceData.model_data.is_area_chart
        const {
            categoryXField, categoryYField, valueXField, valueYField
        } = this.getValueCategoryFieldSetting(this.groupbyName, sequencedAggregate)

        let amSeries = this.chart.series.push(
            am5xy.LineSeries.new(this.root, {
                name: name, xAxis: this.xAxis, tooltip: this.getTooltip(showCurrency),
                yAxis: this.yAxis, categoryXField, categoryYField, valueXField, valueYField,
                userData: { sourceData }
            })
        );

        amSeries.strokes.template.setAll({ strokeWidth: 3 });
        this.setupDataProcessor(amSeries, sourceData);

        if (isAreaChart) amSeries.fills.template.setAll({ fillOpacity: 0.5, visible: true });
        this.addCircularSpriteBullet(amSeries, sourceData, toDisable)
        amSeries.data.setAll(this.getFormattedSourceRecords(this.formattedGroupbyRecordMappedData));
    }

    // ==================== Chart Features ====================

    getScrollBar(settings){
        return am5.Scrollbar.new(this.root, {
            orientation: "horizontal", ...settings
        })
    }

    setupScrollbar() {
        const dimension = this.isHorizontal ? "minWidth" : "minHeight";
        const orientation = this.isHorizontal ? "vertical" : "horizontal";

        let scrollbar = this.getScrollBar({orientation, [dimension]: 8})
        scrollbar.startGrip.setAll({ visible: false });
        scrollbar.endGrip.setAll({ visible: false });

        const scrollBarAxes = this.isHorizontal ? "scrollbarY" : "scrollbarX";
        this.chart.set(scrollBarAxes, scrollbar)
    }

    setupCursor() {
        this.cursor = this.chart.set("cursor", am5xy.XYCursor.new(this.root, {}));
    }

    setupLegend() {
        // TODO: Make the height adjustable automatically
        let legend = this.chart.children.push(
            am5.Legend.new(this.root, {
                centerX: am5.p50, x: am5.p50, y: am5.p100, centerY: am5.p100, layout: this.root.gridLayout,
                useDefaultMarker: true, height: am5.percent(30), reverseChildren: this.isRtl,
                verticalScrollbar: this.getScrollBar({orientation: "vertical", minWidth: 7})
            })
        )

        legend.data.setAll(this.chart.series.values);
        legend.labels.template.setAll({maxWidth: 150, oversizedBehavior: "wrap"})
        legend.valueLabels.template.setAll({width: 70, textAlign: "right"})
    }

    setupExporting() {
        let numericFields = [this.groupbyName]
        let dataFields = { [this.groupbyName]: 'GroupBy' }

        for (let i = 0; i < this.data.sources.length; i++) {
            let sourceData = this.data.sources[i];
            for (let j = 0; j < sourceData.sequenced_aggregates.length; j++) {
                let sequencedAggregate = sourceData.sequenced_aggregates[j];
                numericFields.push(sequencedAggregate);
                const aggregate = splitAggregate(sequencedAggregate);
                dataFields[sequencedAggregate] = sourceData.aggregates_data[aggregate].field_description;
            }
        }

        for (let i = 0; i < this.data.formula_sources.length; i++) {
            let formulaData = this.data.formula_sources[i];
            for (let j = 0; j < formulaData.sequenced_aggregates.length; j++) {
                let sequencedAggregate = formulaData.sequenced_aggregates[j];
                numericFields.push(sequencedAggregate);
                dataFields[sequencedAggregate] = formulaData.model_data.name;
            }
        }

        this.exporting = am5plugins_exporting.Exporting.new(this.root, {
            menu: am5plugins_exporting.ExportingMenu.new(this.root, {
                align: "right",
                valign: "top"
            }),
            filePrefix: this.chartName, title: this.chartName,
            dataSource: this.getFormattedSourceRecords(this.data.formatted_groupby_record_mapped_data),
            numericFields, dataFields, numberFormat: "#,###.00",
            pdfOptions: {
                includeData: true, addURL: false, pageSize: "LETTER", pageOrientation: "landscape",
                pageMargins: [20, 20, 20, 40]
            }
        });

        this.exporting.events.on("dataprocessed", (ev) => {
            if(ev.format === 'json'){
                ev.data = this.getFormattedSourceRecords(this.data.formatted_groupby_record_mapped_data)
            }
        })


        let annotator = am5plugins_exporting.Annotator.new(this.root, {});
        let menuItems = this.exporting.get("menu").get("items");

        menuItems.push({ type: "separator" });
        menuItems.push({
            type: "custom",
            label: "Annotate",
            callback: function () {
                this.close();
                annotator.toggle();
            }
        });
    }
}