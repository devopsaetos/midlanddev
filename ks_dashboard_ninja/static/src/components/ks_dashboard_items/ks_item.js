import {
    Component, useState, useRef, onWillStart
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ExplanationViewer } from "@ks_dashboard_ninja/components/explanation_viewer/explanation_viewer";
import {
    setupLazyDataFetching, itemStandardProps, itemStandardDefaultProps, setupPopoverActions
} from "@ks_dashboard_ninja/components/ks_dashboard_items/item_util";
import { registry } from "@web/core/registry";
import { loadBundle } from '@web/core/assets';
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { pick } from "@web/core/utils/objects";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const dnItemTypesRegistry = registry.category("ks_dashboard_ninja.dashboard_items");

export class KsItem extends Component {

    static template = "ks_dashboard_ninja.ks_item"
    static components = { Dropdown, DropdownItem, ExplanationViewer }
    static toDisable = []
    static props = itemStandardProps
    static defaultProps = itemStandardDefaultProps

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialogService = useService("dialog");

        this.aiAudioRef = useRef("aiAudioRef");
        this.rootRef = useRef("rootRef");
        this.itemPopoverRef = useRef("itemPopoverRef");

        this.allowItemFetching = true;

        this.state = useState({
            data: this.props.data,
            isLoadingAnimation: !this.props.toDisable.lazyDataFetching,
            renderKey: 0
        });

        onWillStart(async() => await loadBundle("ks_dashboard_ninja.ks_dashboard_lib"))

        // Setup lazy data fetching
        if (!this.props.toDisable.lazyDataFetching && this.state.data.model_data?.id) {
            setupLazyDataFetching({
                id: this.state.data.model_data.id,
                bus: this.env.bus,
                dataFetchCallback: this.dataFetching.bind(this),
                eventPrefix: 'item_'
            });
        }

        this.popoverAction = setupPopoverActions({
            getDataCb: () => this.state.data,
            callbacks: {
                dataFetching: this.dataFetching.bind(this),
                editItem: this.editItem.bind(this),
                deleteItem: this.deleteItem.bind(this),
            },
            refToPopover: this.itemPopoverRef, toDisable: {drillDown: true}
        })

    }

    async dataFetching({args = [], kwargs = {}, options = {}, isForced = false} = {}) {
        let domain = [];
        let id = this.state.data.model_data.id

        const result = await this.orm.call(
            'ks_dashboard_ninja.item' , 'get_item_config', [[id], domain, ...args], kwargs
        )
        this.state.data = result
        this.state.isLoadingAnimation = false
        this.allowItemFetching = false;
        
        // Update renderKey to force rerender when isForced is true
        if (isForced) {
            this.state.renderKey = (this.state.renderKey || 0) + 1;
        }
    }

    openItemPopover(ev){
        if (this.props.toDisable.itemPopover) return

        this.popoverAction.openItemPopover({
            pointerEvent: ev, data: this.state.data
        })
    }

    editItem() {
        if(!this.props.dashboardData) return;

        this.dialogService.add(FormViewDialog, {
            resModel: 'ks_dashboard_ninja.item',
            title: 'Edit Chart',
            resId : this.state.data.model_data.id,
            is_expand_icon_visible: true,
            onRecordSaved: (record) => {
                let itemBasicData = pick(record.data, ...this.props.dashboardData.item_basic_data_fields)
                this.env.bus.trigger(
                    'MODIFY: Dashboard ITEM', { isUpdate: true, itemsDataToUpdate: [itemBasicData]}
                )
            },
            size: 'fs'
        })
        this.popoverAction.popover.close()
    }

    deleteItem() {
        this.dialogService.add(ConfirmationDialog, {
            body: _t("Are you sure that you want to remove this item?"),
            confirmLabel: _t("Delete Item"),
            title: _t("Delete Dashboard Item"),
            confirm: () => {
                let itemDataToRemove = pick(this.state.data.model_data, ...this.props.dashboardData.item_basic_data_fields)
                this.env.bus.trigger('MODIFY: Dashboard ITEM', { isRemove: true, itemDataToRemove})
                this.orm.unlink('ks_dashboard_ninja.item', [this.state.data.model_data.id])
                return true;
            },
        });
    }

    get componentInfo() {
        // Only render child components when KsItem is used directly (not extended)
        if (this.constructor !== KsItem) return null;
        
        const itemType = this.state.data.model_data.type;
        if (!itemType) return null;
        
        const itemInfo = dnItemTypesRegistry.get(itemType, false);
        if (!itemInfo || !itemInfo.component) return null;

        return {
            component: itemInfo.component,
            props: {
                ...this.props, data: this.state.data,
                callbacks: {
                    dataFetching: this.dataFetching.bind(this),
                }
            }
        };
    }
}

