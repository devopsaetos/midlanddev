import { FormStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";
import { patch } from "@web/core/utils/patch";


patch(FormStatusIndicator.prototype, {
    async save() {
        if (this.props.model.config.resModel == 'ks_custom_report.ks_report' && this.props.model.config.resId){
                await this.props.save();
                window.location.reload();
            }
        else{
                await this.props.save();
            }
        }
});
