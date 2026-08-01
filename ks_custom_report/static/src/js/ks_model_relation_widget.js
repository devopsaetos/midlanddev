/** @odoo-module **/
import { registry } from "@web/core/registry";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";
import { ModelFieldSelectorPopover } from "@web/core/model_field_selector/model_field_selector_popover";


import { Component } from "@odoo/owl";

export class KsQueryBuilder extends Component{
    setup() {
    var self= this;
    }
     async onFieldChange(fieldName){
        const changes = fieldName ;
        this.props.record.update({ [this.props.name]: changes })
        }
};

KsQueryBuilder.components = {ModelFieldSelector};
KsQueryBuilder.template = "ks_model_relations.KsQueryBuilder";
export const KsQueryBuilderField = {
    component : KsQueryBuilder
}


registry.category("fields").add('ks_model_relations', KsQueryBuilderField);

