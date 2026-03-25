# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .ai_services import suggest_tasks_from_interaction

_logger = logging.getLogger(__name__)


class TuongTacKhachHang(models.Model):
    _name = 'tuong_tac_khach_hang'
    _description = 'Tương tác khách hàng'
    _rec_name = 'ten_tuong_tac'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ngay_gio desc, id desc'

    ma_tuong_tac = fields.Char(string='Mã tương tác', required=True, copy=False, default='New', tracking=True)
    ten_tuong_tac = fields.Char(string='Tên tương tác', required=True, tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True, tracking=True)
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên phụ trách', required=True, tracking=True)
    loai_tuong_tac = fields.Selection([
        ('goi_dien', 'Gọi điện'),
        ('bao_gia', 'Báo giá'),
        ('lich_hen', 'Lịch hẹn'),
        ('cham_soc_khac', 'Chăm sóc khác'),
    ], string='Loại tương tác', required=True, default='goi_dien', tracking=True)
    ngay_gio = fields.Datetime(string='Ngày giờ ghi nhận', default=fields.Datetime.now, required=True, tracking=True)
    noi_dung = fields.Text(string='Nội dung', tracking=True)
    ket_qua = fields.Text(string='Kết quả')
    ngay_hen_tiep = fields.Datetime(string='Ngày hẹn tiếp', tracking=True)
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_theo_doi', 'Đang theo dõi'),
        ('da_xong', 'Đã xong'),
        ('huy', 'Hủy'),
    ], string='Trạng thái', default='moi', tracking=True)
    tep_dinh_kem = fields.Binary(string='Tệp đính kèm')
    tep_dinh_kem_name = fields.Char(string='Tên tệp')
    cong_viec_ids = fields.One2many('cong_viec', 'tuong_tac_id', string='Công việc')
    cong_viec_count = fields.Integer(string='Số công việc', compute='_compute_counts')
    hop_dong_ids = fields.One2many('hop_dong_khach_hang', 'tuong_tac_id', string='Hợp đồng')
    hop_dong_count = fields.Integer(string='Số hợp đồng', compute='_compute_counts')

    _sql_constraints = [
        ('ma_tuong_tac_unique', 'unique(ma_tuong_tac)', 'Mã tương tác phải là duy nhất!'),
    ]

    @api.depends('cong_viec_ids', 'hop_dong_ids')
    def _compute_counts(self):
        for record in self:
            record.cong_viec_count = len(record.cong_viec_ids)
            record.hop_dong_count = len(record.hop_dong_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('ma_tuong_tac', 'New') == 'New':
                vals['ma_tuong_tac'] = sequence.next_by_code('tuong_tac_khach_hang') or 'New'
            if not vals.get('nhan_vien_id') and vals.get('khach_hang_id'):
                customer = self.env['khach_hang'].browse(vals['khach_hang_id'])
                vals['nhan_vien_id'] = customer.nhan_vien_phu_trach_id.id
        records = super().create(vals_list)
        records._sync_follow_up_activity()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_follow_up_activity()
        return result

    @api.constrains('ngay_hen_tiep', 'ngay_gio', 'loai_tuong_tac')
    def _check_dates(self):
        for record in self:
            if (
                record.loai_tuong_tac == 'lich_hen'
                and record.ngay_hen_tiep
                and record.ngay_hen_tiep < record.ngay_gio
            ):
                raise ValidationError('Ngày hẹn tiếp không được nhỏ hơn ngày ghi nhận.')

    def _sync_follow_up_activity(self):
        todo_activity = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_activity:
            return
        for record in self:
            activities = record.activity_ids.filtered(lambda a: a.activity_type_id == todo_activity)
            if record.ngay_hen_tiep and record.nhan_vien_id.user_id and record.trang_thai not in ('da_xong', 'huy'):
                if activities:
                    activities.write({
                        'date_deadline': fields.Date.to_date(record.ngay_hen_tiep),
                        'user_id': record.nhan_vien_id.user_id.id,
                        'summary': f'Theo dõi tương tác {record.ma_tuong_tac}',
                        'note': record.noi_dung or record.ten_tuong_tac,
                    })
                else:
                    record.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=record.nhan_vien_id.user_id.id,
                        date_deadline=fields.Date.to_date(record.ngay_hen_tiep),
                        summary=f'Theo dõi tương tác {record.ma_tuong_tac}',
                        note=record.noi_dung or record.ten_tuong_tac,
                    )
            elif activities:
                activities.unlink()

    def action_view_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Công việc từ tương tác',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'kanban,tree,form',
            'domain': [('tuong_tac_id', '=', self.id)],
            'context': {
                'default_tuong_tac_id': self.id,
                'default_khach_hang_id': self.khach_hang_id.id,
                'default_nhan_vien_thuc_hien_id': self.nhan_vien_id.id,
            },
        }

    def action_create_cong_viec(self):
        self.ensure_one()
        loai = self.env['loai_cong_viec'].search([], limit=1)
        return {
            'name': 'Tạo công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_ten_cong_viec': f'Theo dõi {self.khach_hang_id.ten_khach_hang}',
                'default_mo_ta': self.noi_dung or self.ten_tuong_tac,
                'default_khach_hang_id': self.khach_hang_id.id,
                'default_nhan_vien_thuc_hien_id': self.nhan_vien_id.id,
                'default_tuong_tac_id': self.id,
                'default_han_chot': fields.Date.to_date(self.ngay_hen_tiep) if self.ngay_hen_tiep else fields.Date.context_today(self),
                'default_nguon_tao': 'tuong_tac',
                'default_loai_cong_viec_id': loai.id,
            },
        }

    def action_view_hop_dong(self):
        self.ensure_one()
        return {
            'name': 'Hợp đồng liên quan',
            'type': 'ir.actions.act_window',
            'res_model': 'hop_dong_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('tuong_tac_id', '=', self.id)],
            'context': {
                'default_tuong_tac_id': self.id,
                'default_khach_hang_id': self.khach_hang_id.id,
                'default_nhan_vien_phu_trach_id': self.nhan_vien_id.id,
            },
        }

    def action_open_ai_wizard(self):
        self.ensure_one()
        wizard = self.env['tuong_tac_khach_hang_ai_wizard'].create({
            'tuong_tac_id': self.id,
        })
        suggestions, warning = suggest_tasks_from_interaction(self)
        wizard._load_suggestions(suggestions, warning)
        return {
            'name': 'AI gợi ý công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'tuong_tac_khach_hang_ai_wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
