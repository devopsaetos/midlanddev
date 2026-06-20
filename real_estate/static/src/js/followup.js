odoo.define('real_estate.followup', function (require) {

"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var Widget = require('web.Widget');
var session = require('web.session');

var QWeb = core.qweb;
var _t = core._t;

var FollowUpDashboard = AbstractAction.extend({
	template: 'FollowUpDashboardMain',

    events: {
        'click [data-user-id]': 'go_invoice',
        'click [data-partner-id]': 'go_chatter',
        'click [data-customer-id]': 'get_data',
    },

    init: function(){
        return this._super.apply(this, arguments);
    },

    start: function(){
        return this.load();
    },

    load: function(){
        var self = this;
        var loading_done = new $.Deferred();
        this._rpc({route: '/real_estate/followup'})
            .then(function (data) {
                self.$el.html(QWeb.render('FollowUpSummery', {item: data}));
            	// self.$el.html(QWeb.render('FollowUpTable', {item: data}));
            	loading_done.resolve();
            });
        return loading_done;
    },

    go_invoice: function(e){
        var self = this;
        e.preventDefault();

        this._rpc({
                model: 'ir.model.data',
                method: 'xmlid_to_res_id',
                kwargs: {xmlid: 'account.move_tree'},
        }).then(function(data){
            var user_id = parseInt($('.o_top_tr.active').attr('data-sp-id'))
            
            if (user_id == 0) {
                user_id = false;
            }

            var action = {
                type: 'ir.actions.act_window',
                name:'Invoices',
                view_type: 'form',
                view_mode: 'tree,form',
                res_model: 'account.move',
                context: {'current_view': 'realestate'},
                domain: [
                    ['partner_id', '=', parseInt($(e.target).attr('data-user-id'))],
                    ['user_id','=', user_id],
                    ['ageing','=', $(e.target).attr('data-ageing-id')],
                    ['state','=', 'open'],
                    ],
                views: [[data, 'list'], [false, 'form']],
            };
            self.do_action(action,{
                on_reverse_breadcrumb: function(){ return self.reload();}
            });
        });
    },

    go_chatter: function(e){
        var self = this;
        e.preventDefault();
        var partner_id = $(e.currentTarget).attr('data-partner-id');
        if (partner_id) {
            partner_id = parseInt(partner_id);
        }

        this._rpc({
                model: 'ir.model.data',
                method: 'xmlid_to_res_id',
                kwargs: {xmlid: 'real_estate.view_partner_followup_form'},
        }).then(function(data){
            var action = {
                type: 'ir.actions.act_window',
                name:'Chatter',
                view_type: 'form',
                view_mode: 'form',
                res_model: 'res.partner',
                res_id: partner_id,
                context: {'current_view': 'realestate'},
                views: [[data, 'form']],
            };
            self.do_action(action,{
                on_reverse_breadcrumb: function(){ return self.reload();}
            });
        });
    },

    reload:function(){
        return this.load();
    },

    get_data: function(e){
        var self = this;
        e.preventDefault();
        e.stopPropagation();
        var target = parseInt($(e.currentTarget).attr("data-customer-id"));
        console.log(target);

        // check if already detail is open then remove it.
        this.remove_detail();

        // check if active class already there on selected node.
        if ($('.o_top_tr.active')) {
            
            
            if ($("[data-sp-id='"+target+"']").hasClass("active")){
                $("[data-sp-id='"+target+"']").toggleClass("active");
            }
            else{
                $('.o_top_tr.active').toggleClass("active");
                $("[data-sp-id='"+target+"']").toggleClass("active");
            }
        } 
        else {
            $("[data-sp-id='"+target+"']").toggleClass("active");
        }

        if ($('.glyphicon.glyphicon-resize-small')) {
            
            
            if ($("[data-customer-id='"+target+"'] > i").hasClass("glyphicon glyphicon-resize-small")){
                $("[data-customer-id='"+target+"'] > i").removeClass("glyphicon glyphicon-resize-small");
            }
            else{
                $('.glyphicon.glyphicon-resize-small').removeClass('glyphicon glyphicon-resize-small');
                $("[data-customer-id='"+target+"'] > i").addClass("glyphicon glyphicon-resize-small");
            }
        } 
        else {
            $("[data-customer-id='"+target+"'] > i").addClass("glyphicon glyphicon-resize-small");
        }


        var loading_done = new $.Deferred();
        this._rpc({
            route: '/real_estate/followup_detail',
            params: {
                saleperson_id: target,
            }
        }).then(function (data) {
                var html = $(QWeb.render("FollowUpTable", {item: data}));
                var selector = ".active.o_top_tr"
                $(html).insertAfter(selector).show('slow');;
                loading_done.resolve();
            });
        return loading_done;
    },

    remove_detail: function(){
        if ($('.o_details')) {
            $('.o_details').remove();
        }
    }
});

var FollowUpTable = Widget.extend({
	template: 'FollowUpTable',

	init: function(parent, data){
		this.data = data;
        this.parent = parent;
        return this._super.apply(this, arguments);
    },

    start: function(){
        return this._super.apply(this, arguments);
    }
});

core.action_registry.add('real_estate.followup', FollowUpDashboard);
return {
    FollowUpDashboard: FollowUpDashboard,
    FollowUpTable: FollowUpTable,
};
});