
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

// TODO: remove this patch, find better solution currently used bcz of the module theme as there are some places like
// TODO:   buttons, modals where css cannot be applied without ks_body_class
patch(NavBar.prototype,{
    async adapt(){
        if(this.currentApp?.xmlid === "ks_dashboard_ninja.board_menu_root" || this.actionService?.currentController?.action.tag === 'ks_dashboard_ninja'){
            if(!$('body').hasClass('ks_body_class'))
                $('body').addClass('ks_body_class');
        }
        else{
            if($('body').hasClass('ks_body_class'))
                $('body').removeClass('ks_body_class');
        }
        return super.adapt();
    },
});
