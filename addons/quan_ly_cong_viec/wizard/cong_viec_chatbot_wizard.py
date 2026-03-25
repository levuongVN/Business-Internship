# -*- coding: utf-8 -*-

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.ai_services import answer_quan_ly_cong_viec_chatbot


class CongViecChatbotWizard(models.TransientModel):
    _name = 'cong_viec_chatbot_wizard'
    _description = 'Chatbot công việc'

    pham_vi_hoi_dap = fields.Selection([
        ('tong_quan', 'Toàn bộ module'),
        ('mot_cong_viec', 'Một công việc'),
    ], string='Phạm vi', required=True, default='tong_quan')
    cong_viec_id = fields.Many2one('cong_viec', string='Công việc')
    open_in_dialog = fields.Boolean(string='Mở dạng hộp thoại', default=True)
    cau_hoi = fields.Text(string='Câu hỏi')
    tra_loi_gan_nhat = fields.Text(string='Trả lời gần nhất', readonly=True)
    canh_bao_ai = fields.Text(string='Cảnh báo AI', readonly=True)
    tong_hop_cong_viec = fields.Text(string='Tổng hợp công việc', compute='_compute_tong_hop_cong_viec')
    lich_su_ids = fields.One2many('cong_viec_chatbot_wizard_line', 'wizard_id', string='Lịch sử chat')
    lich_su_html = fields.Html(string='Hội thoại', compute='_compute_lich_su_html', sanitize=True)

    @api.depends(
        'cong_viec_id',
        'cong_viec_id.ten_cong_viec',
        'cong_viec_id.trang_thai',
        'cong_viec_id.muc_do_uu_tien',
        'cong_viec_id.han_chot',
        'cong_viec_id.ket_qua_xu_ly',
        'cong_viec_id.khach_hang_id',
        'cong_viec_id.hop_dong_ids',
        'pham_vi_hoi_dap',
    )
    def _compute_tong_hop_cong_viec(self):
        for record in self:
            if record.pham_vi_hoi_dap == 'tong_quan':
                record.tong_hop_cong_viec = record._build_overall_summary()
                continue
            task = record.cong_viec_id
            if not task:
                record.tong_hop_cong_viec = 'Chọn một công việc để xem tóm tắt chi tiết theo từng việc.'
                continue
            lines = [
                f'Công việc: {task.ten_cong_viec}',
                f'Trạng thái: {task.trang_thai}',
                f'Ưu tiên: {task.muc_do_uu_tien}',
                f'Hạn chót: {task.han_chot or "Không có"}',
                f'Khách hàng: {task.khach_hang_id.ten_khach_hang if task.khach_hang_id else "Không có"}',
                f'Nhân viên thực hiện: {self._employee_name(task.nhan_vien_thuc_hien_id)}',
                f'Mô tả: {task.mo_ta or "Không có"}',
                f'Kết quả xử lý: {task.ket_qua_xu_ly or "Chưa có"}',
                f'Số hợp đồng liên quan: {len(task.hop_dong_ids)}',
            ]
            record.tong_hop_cong_viec = '\n'.join(lines)

    @api.depends('lich_su_ids.vai_tro', 'lich_su_ids.noi_dung')
    def _compute_lich_su_html(self):
        for record in self:
            if not record.lich_su_ids:
                record.lich_su_html = (
                    '<div style="padding: 16px; background: linear-gradient(135deg, #f4f8ff, #eef9f2); '
                    'border: 1px solid #d7e6f6; border-radius: 16px; color: #355070;">'
                    '<strong>Chatbot công việc</strong><br/>'
                    'Bạn có thể hỏi tổng quan toàn module hoặc chọn một công việc cụ thể để hỏi sâu hơn.'
                    '</div>'
                )
                continue
            blocks = []
            for line in record.lich_su_ids.sorted('id'):
                role_label = 'Bạn' if line.vai_tro == 'user' else 'Gemini'
                align_style = 'justify-content: flex-end;' if line.vai_tro == 'user' else 'justify-content: flex-start;'
                bubble_style = (
                    'max-width: 78%; padding: 12px 14px; border-radius: 18px; '
                    'box-shadow: 0 6px 18px rgba(42, 67, 101, 0.08); '
                    'background: #e7f1ff; color: #1f3b57;'
                )
                if line.vai_tro == 'user':
                    bubble_style = (
                        'max-width: 78%; padding: 12px 14px; border-radius: 18px; '
                        'box-shadow: 0 6px 18px rgba(42, 67, 101, 0.08); '
                        'background: #dff6e8; color: #214833;'
                    )
                blocks.append(
                    '<div style="display: flex; margin: 10px 0; '
                    f'{align_style}">'
                    f'<div style="{bubble_style}">'
                    f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px;">{escape(role_label)}</div>'
                    f'<div style="line-height: 1.55;">{escape(line.noi_dung or "").replace(chr(10), Markup("<br/>"))}</div>'
                    '</div>'
                    '</div>'
                )
            record.lich_su_html = (
                '<div style="padding: 16px; background: #f7fafc; border-radius: 18px; border: 1px solid #e3ebf5;">'
                + ''.join(blocks) +
                '</div>'
            )

    @api.onchange('pham_vi_hoi_dap', 'cong_viec_id')
    def _onchange_scope_or_task(self):
        if self.pham_vi_hoi_dap == 'tong_quan':
            self.cong_viec_id = False
        self.cau_hoi = False
        self.tra_loi_gan_nhat = False
        self.canh_bao_ai = False
        self.lich_su_ids = [(5, 0, 0)]

    def action_ask_chatbot(self):
        self.ensure_one()
        if self.pham_vi_hoi_dap == 'mot_cong_viec' and not self.cong_viec_id:
            raise UserError('Vui lòng chọn công việc trước khi hỏi chatbot.')

        if self.pham_vi_hoi_dap == 'mot_cong_viec':
            default_question = (
                'Hãy tóm tắt thông minh công việc này, giải thích công việc là gì, đang ở đâu, '
                'cần làm gì tiếp theo và hợp đồng liên quan nếu có.'
            )
        else:
            default_question = (
                'Hãy tóm tắt tổng quan toàn bộ module quản lý công việc, nêu các việc mở, '
                'việc quá hạn, khách hàng cần chăm sóc và hợp đồng đáng chú ý.'
            )
        question = self.cau_hoi or default_question
        return self._submit_question(question)

    def action_clear_chat(self):
        self.ensure_one()
        self.write({
            'cau_hoi': False,
            'tra_loi_gan_nhat': False,
            'canh_bao_ai': False,
            'lich_su_ids': [(5, 0, 0)],
        })
        return self._build_chat_action()

    def action_quick_overview(self):
        self.ensure_one()
        question = (
            'Hãy tóm tắt tổng quan toàn bộ module quản lý công việc, nêu các việc mở, việc quá hạn, '
            'khách hàng cần chăm sóc và hợp đồng đáng chú ý.'
            if self.pham_vi_hoi_dap == 'tong_quan'
            else 'Hãy tóm tắt thông minh công việc này, mục tiêu, trạng thái hiện tại, việc cần làm tiếp theo và hợp đồng liên quan.'
        )
        return self._submit_question(question)

    def action_quick_deadline(self):
        self.ensure_one()
        question = (
            'Có công việc nào gần deadline không?'
            if self.pham_vi_hoi_dap == 'tong_quan'
            else 'Công việc này có gần deadline hoặc quá hạn không?'
        )
        return self._submit_question(question)

    def action_quick_contracts(self):
        self.ensure_one()
        question = (
            'Có hợp đồng nào quá hạn hoặc sắp hết hạn không?'
            if self.pham_vi_hoi_dap == 'tong_quan'
            else 'Công việc này có hợp đồng nào liên quan không?'
        )
        return self._submit_question(question)

    def action_quick_next_steps(self):
        self.ensure_one()
        question = (
            'Các việc nào cần ưu tiên xử lý ngay bây giờ?'
            if self.pham_vi_hoi_dap == 'tong_quan'
            else 'Công việc này cần làm gì tiếp theo?'
        )
        return self._submit_question(question)

    def _employee_name(self, employee):
        if not employee:
            return 'Không có'
        return employee.ho_va_ten or employee.display_name or employee.ten or 'Không có'

    def _build_overall_summary(self):
        task_model = self.env['cong_viec']
        interaction_model = self.env['tuong_tac_khach_hang']
        contract_model = self.env['hop_dong_khach_hang']
        customer_model = self.env['khach_hang']

        open_count = task_model.search_count([('trang_thai', 'not in', ('hoan_thanh', 'huy'))])
        overdue_count = task_model.search_count([('is_qua_han', '=', True)])
        contracts_expiring = contract_model.search_count([('is_sap_het_han', '=', True)])
        customers_need_care = customer_model.search_count(['|', ('tong_cong_viec_mo', '>', 0), ('lich_hen_gan_nhat', '!=', False)])
        recent_tasks = task_model.search([('trang_thai', 'not in', ('hoan_thanh', 'huy'))], limit=5, order='han_chot asc, id desc')

        lines = [
            'Tổng quan module quản lý công việc',
            f'- Tổng công việc: {task_model.search_count([])}',
            f'- Công việc mở: {open_count}',
            f'- Công việc quá hạn: {overdue_count}',
            f'- Tổng tương tác: {interaction_model.search_count([])}',
            f'- Tổng hợp đồng: {contract_model.search_count([])}',
            f'- Hợp đồng sắp hết hạn: {contracts_expiring}',
            f'- Khách hàng cần chăm sóc: {customers_need_care}',
        ]
        if recent_tasks:
            lines.append('Một số công việc đang mở:')
            lines.extend(
                f'- {task.ten_cong_viec} | {task.trang_thai} | {task.muc_do_uu_tien} | hạn {task.han_chot or "Không có"}'
                for task in recent_tasks
            )
        return '\n'.join(lines)

    def _submit_question(self, question):
        history = [(line.vai_tro, line.noi_dung) for line in self.lich_su_ids.sorted('id')[-8:]]
        answer, warning = answer_quan_ly_cong_viec_chatbot(
            self.env,
            question,
            history=history,
            task=self.cong_viec_id if self.pham_vi_hoi_dap == 'mot_cong_viec' else None,
        )
        self.write({
            'cau_hoi': False,
            'tra_loi_gan_nhat': answer,
            'canh_bao_ai': warning or False,
            'lich_su_ids': [
                (0, 0, {'vai_tro': 'user', 'noi_dung': question}),
                (0, 0, {'vai_tro': 'assistant', 'noi_dung': answer}),
            ],
        })
        return self._build_chat_action()

    def _build_chat_action(self):
        view = self.env.ref('quan_ly_cong_viec.view_cong_viec_chatbot_wizard_form')
        context = dict(self.env.context)
        context.update({
            'form_view_initial_mode': 'edit',
            'default_pham_vi_hoi_dap': self.pham_vi_hoi_dap or 'tong_quan',
            'default_open_in_dialog': self.open_in_dialog,
        })
        return {
            'name': 'Chatbot công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec_chatbot_wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new' if self.open_in_dialog else 'main',
            'context': context,
            'flags': {
                'form': {
                    'action_buttons': True,
                    'options': {'mode': 'edit'},
                },
            },
        }


class CongViecChatbotWizardLine(models.TransientModel):
    _name = 'cong_viec_chatbot_wizard_line'
    _description = 'Dòng hội thoại chatbot công việc'
    _order = 'id'

    wizard_id = fields.Many2one('cong_viec_chatbot_wizard', required=True, ondelete='cascade')
    vai_tro = fields.Selection([
        ('user', 'Người dùng'),
        ('assistant', 'Gemini'),
    ], string='Vai trò', required=True)
    noi_dung = fields.Text(string='Nội dung', required=True)
