# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .ai_services import answer_task_chatbot, predict_task_priority

_logger = logging.getLogger(__name__)


class CongViec(models.Model):
    _name = 'cong_viec'
    _description = 'Quản lý công việc'
    _rec_name = 'ten_cong_viec'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    QUICK_SUMMARY_QUESTION = (
        'Hãy tóm tắt nhanh công việc này theo cách dễ hiểu, nêu mục tiêu công việc, '
        'trạng thái hiện tại, việc cần làm tiếp theo, rủi ro và hợp đồng liên quan nếu có.'
    )

    ten_cong_viec = fields.Char(string='Tên công việc', required=True, tracking=True)
    mo_ta = fields.Text(string='Mô tả chi tiết')
    nhan_vien_thuc_hien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên thực hiện',
        required=True,
        tracking=True,
    )
    khach_hang_id = fields.Many2one(
        'khach_hang',
        string='Khách hàng',
        tracking=True,
    )
    tuong_tac_id = fields.Many2one(
        'tuong_tac_khach_hang',
        string='Tương tác nguồn',
        tracking=True,
        ondelete='set null',
    )
    hop_dong_ids = fields.One2many('hop_dong_khach_hang', 'cong_viec_id', string='Hợp đồng')
    hop_dong_count = fields.Integer(string='Số hợp đồng', compute='_compute_hop_dong_count')
    loai_cong_viec_id = fields.Many2one(
        'loai_cong_viec',
        string='Loại công việc',
        required=True,
    )
    nguon_tao = fields.Selection([
        ('thu_cong', 'Thủ công'),
        ('tuong_tac', 'Từ tương tác'),
        ('ai_goi_y', 'AI gợi ý'),
    ], string='Nguồn tạo', default='thu_cong', tracking=True)
    ngay_bat_dau = fields.Date(string='Ngày bắt đầu', default=fields.Date.today, tracking=True)
    han_chot = fields.Date(string='Hạn chót', default=fields.Date.today, tracking=True)
    ngay_hoan_thanh = fields.Date(string='Ngày hoàn thành', tracking=True)
    muc_do_uu_tien = fields.Selection([
        ('thap', 'Thấp'),
        ('trung_binh', 'Trung bình'),
        ('cao', 'Cao'),
        ('rat_cao', 'Rất cao'),
    ], string='Mức độ ưu tiên', default='trung_binh', tracking=True)
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_lam', 'Đang làm'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy'),
    ], string='Trạng thái', default='moi', tracking=True, group_expand='_expand_states')
    ket_qua_xu_ly = fields.Text(string='Kết quả xử lý')
    ly_do_huy = fields.Text(string='Lý do hủy')
    is_qua_han = fields.Boolean(string='Quá hạn', compute='_compute_is_qua_han', store=True)
    mau_canh_bao = fields.Selection([
        ('binh_thuong', 'Bình thường'),
        ('qua_han', 'Quá hạn'),
    ], compute='_compute_is_qua_han', string='Màu cảnh báo', store=True)

    @api.depends('hop_dong_ids')
    def _compute_hop_dong_count(self):
        for record in self:
            record.hop_dong_count = len(record.hop_dong_ids)

    @api.depends('han_chot', 'trang_thai')
    def _compute_is_qua_han(self):
        today = fields.Date.context_today(self)
        for record in self:
            overdue = bool(
                record.han_chot
                and record.han_chot < today
                and record.trang_thai not in ('hoan_thanh', 'huy')
            )
            record.is_qua_han = overdue
            record.mau_canh_bao = 'qua_han' if overdue else 'binh_thuong'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_workflow_dates()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_workflow_dates()
        return result

    @api.constrains('ngay_bat_dau', 'han_chot')
    def _check_task_dates(self):
        for record in self:
            if record.ngay_bat_dau and record.han_chot and record.ngay_bat_dau > record.han_chot:
                raise ValidationError('Ngày bắt đầu không được lớn hơn hạn chót.')

    @api.constrains('trang_thai', 'ket_qua_xu_ly', 'ly_do_huy')
    def _check_workflow_requirements(self):
        for record in self:
            if record.trang_thai == 'hoan_thanh' and not (record.ket_qua_xu_ly or '').strip():
                raise ValidationError('Công việc hoàn thành phải có kết quả xử lý.')
            if record.trang_thai == 'huy' and not (record.ly_do_huy or '').strip():
                raise ValidationError('Công việc bị hủy phải có lý do hủy.')

    def _sync_workflow_dates(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.trang_thai == 'dang_lam' and not record.ngay_bat_dau:
                record.ngay_bat_dau = today
            if record.trang_thai == 'hoan_thanh' and not record.ngay_hoan_thanh:
                record.ngay_hoan_thanh = today
            elif record.trang_thai != 'hoan_thanh' and record.ngay_hoan_thanh:
                record.ngay_hoan_thanh = False
            if record.trang_thai != 'huy' and record.ly_do_huy:
                record.ly_do_huy = False

    def ai_predict_priority(self):
        notifications = []
        success_count = 0
        error_count = 0
        for record in self:
            value, error = predict_task_priority(
                task_name=record.ten_cong_viec,
                description=record.mo_ta,
                deadline=record.han_chot,
            )
            if value:
                record.muc_do_uu_tien = value
                notifications.append(f'{record.ten_cong_viec}: {value}')
                success_count += 1
            else:
                notifications.append(f'{record.ten_cong_viec}: {error}')
                _logger.warning('Không thể gợi ý ưu tiên cho %s: %s', record.display_name, error)
                error_count += 1
        notification_type = 'success'
        if error_count and success_count:
            notification_type = 'warning'
        elif error_count and not success_count:
            notification_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'AI gợi ý ưu tiên',
                'message': '\n'.join(notifications),
                'sticky': False,
                'type': notification_type,
            },
        }

    def action_create_hop_dong(self):
        self.ensure_one()
        return {
            'name': 'Tạo hợp đồng',
            'type': 'ir.actions.act_window',
            'res_model': 'hop_dong_khach_hang',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_ten_hop_dong': f'Hợp đồng - {self.ten_cong_viec}',
                'default_khach_hang_id': self.khach_hang_id.id,
                'default_nhan_vien_phu_trach_id': self.nhan_vien_thuc_hien_id.id,
                'default_tuong_tac_id': self.tuong_tac_id.id,
                'default_cong_viec_id': self.id,
            },
        }

    def action_view_hop_dong(self):
        self.ensure_one()
        return {
            'name': 'Hợp đồng liên quan',
            'type': 'ir.actions.act_window',
            'res_model': 'hop_dong_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('cong_viec_id', '=', self.id)],
            'context': {
                'default_khach_hang_id': self.khach_hang_id.id,
                'default_nhan_vien_phu_trach_id': self.nhan_vien_thuc_hien_id.id,
                'default_tuong_tac_id': self.tuong_tac_id.id,
                'default_cong_viec_id': self.id,
            },
        }

    def action_open_chatbot(self):
        self.ensure_one()
        wizard = self.env['cong_viec_chatbot_wizard'].create({
            'pham_vi_hoi_dap': 'mot_cong_viec',
            'cong_viec_id': self.id,
            'open_in_dialog': True,
        })
        return {
            'name': 'Chatbot công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec_chatbot_wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'context': {
                'form_view_initial_mode': 'edit',
            },
            'target': 'new',
            'flags': {
                'form': {
                    'action_buttons': True,
                    'options': {'mode': 'edit'},
                },
            },
        }

    def action_open_quick_summary(self):
        self.ensure_one()
        wizard = self.env['cong_viec_chatbot_wizard'].create({
            'pham_vi_hoi_dap': 'mot_cong_viec',
            'cong_viec_id': self.id,
            'open_in_dialog': True,
        })
        answer, warning = answer_task_chatbot(self, self.QUICK_SUMMARY_QUESTION)
        wizard.write({
            'tra_loi_gan_nhat': answer,
            'canh_bao_ai': warning or False,
            'lich_su_ids': [
                (0, 0, {'vai_tro': 'user', 'noi_dung': self.QUICK_SUMMARY_QUESTION}),
                (0, 0, {'vai_tro': 'assistant', 'noi_dung': answer}),
            ],
        })
        return {
            'name': 'Tóm tắt nhanh công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec_chatbot_wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'context': {
                'form_view_initial_mode': 'edit',
            },
            'target': 'new',
            'flags': {
                'form': {
                    'action_buttons': True,
                    'options': {'mode': 'edit'},
                },
            },
        }

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, _value in type(self).trang_thai.selection]
