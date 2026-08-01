/** @odoo-module **/
import { GraphRenderer } from "@web/views/graph/graph_renderer";
import { patch } from "@web/core/utils/patch";

    patch(GraphRenderer.prototype,{


        async ksDoAction(domain){
            await this.props.model.getKsmodelDomain(domain);
        },

        async onGraphClicked(ev) {
        const [activeElement] = this.chart.getElementsAtEventForMode(
            ev,
            "nearest",
            { intersect: true },
            false
        );
        if (!activeElement) {
            return;
        }
        const { datasetIndex, index } = activeElement;
        const { domains } = this.chart.data.datasets[datasetIndex];
        if (domains) {
           await this.ksDoAction(domains[index]);
        }
    },


});