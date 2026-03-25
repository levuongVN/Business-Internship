odoo.define('quan_ly_cong_viec.cong_viec_chatbot_form', function (require) {
    'use strict';

    var FormRenderer = require('web.FormRenderer');

    FormRenderer.include({
        _renderView: function () {
            var result = this._super.apply(this, arguments);
            return Promise.resolve(result).then(this._afterRenderCongViecChatbot.bind(this));
        },

        _afterRenderCongViecChatbot: function () {
            if (!this.state || this.state.model !== 'cong_viec_chatbot_wizard') {
                return;
            }

            setTimeout(function () {
                var historyBody = this.el.querySelector('.o_qlcv_chat_history_body');
                if (historyBody) {
                    historyBody.scrollTop = historyBody.scrollHeight;
                }

                var composer = this.el.querySelector('.o_qlcv_chat_composer textarea');
                if (composer) {
                    composer.focus();
                    var textLength = composer.value ? composer.value.length : 0;
                    composer.setSelectionRange(textLength, textLength);
                }
            }.bind(this), 0);
        },
    });
});
