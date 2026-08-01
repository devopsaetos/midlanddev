import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class KsFileDataColumns extends Component {
    static template = 'ks_dashboard_ninja.ks_file_data_columns'
    static components = { Dropdown, DropdownItem }

    setup() {
        super.setup();
        this.state = useState({
            fileData: this.props.record.data[this.props.name] || {}
        });
        
        this.availableColumnsData = {
            char: 'Char', date: 'Date', datetime: 'DateTime', float: 'Float',
            integer: 'Integer', text: 'Text', boolean: 'Boolean'
        }

        useRecordObserver((record) => {
            this.state.fileData = record.data[this.props.name] || {}
        })

    }
    
    get hasColumnsData() {
        return Object.keys(this.state.fileData.columns_data || {}).length > 0;
    }

    get columnsData() {
        return this.state.fileData.columns_data || {}
    }
    
    typeChange(columnIndex, ttype) {
        this.state.fileData.columns_data[columnIndex].ttype = ttype
        this.props.record.update({ [this.props.name]: this.state.fileData })
    }
}

export const KsFileDataColumnsWidget = {
    component: KsFileDataColumns,
    supportedTypes: ["json"],
}

registry.category("fields").add("ks_file_data_columns", KsFileDataColumnsWidget);

