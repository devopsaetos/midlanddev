/** @odoo-module */

import { Model } from "@web/model/model";
import { sortBy } from "@web/core/utils/arrays";
import { GraphModel } from "@web/views/graph/graph_model";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";


const { useEffect,onMounted} = owl;
import { SEP } from "@web/views/graph/graph_model";

patch(GraphModel.prototype, {
    /**
     * @override
     */
    setup(params) {
        this.rpc = rpc
        this.action = useService("action");
        super.setup(params);


},


        async getKsmodelDomain(domain){
            var context = session.user_context;
            var result = await rpc(
                '/ks_custom_report/get_model_name',
                {
                    model: this.metaData.resModel,
                    local_context: context,
                    domain: domain,
                }
            )
            if(result){
                 this.env.services.action.doAction(result);
            }
        },


});