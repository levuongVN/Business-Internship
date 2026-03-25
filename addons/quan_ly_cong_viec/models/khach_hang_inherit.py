# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KhachHang(models.Model):
    _inherit = 'khach_hang'

    ten_cong_ty = fields.Char(string='Tên công ty', tracking=True)
    nguoi_lien_he = fields.Char(string='Người liên hệ', tracking=True)
    chuc_vu_nguoi_lien_he = fields.Char(string='Chức vụ người liên hệ', tracking=True)
    cong_viec_ids = fields.One2many('cong_viec', 'khach_hang_id', string='Danh sách công việc')
    tuong_tac_ids = fields.One2many('tuong_tac_khach_hang', 'khach_hang_id', string='Danh sách tương tác')
    hop_dong_ids = fields.One2many('hop_dong_khach_hang', 'khach_hang_id', string='Danh sách hợp đồng')
    cong_viec_count = fields.Integer(string='Số công việc', compute='_compute_dashboard_fields', store=True)
    tuong_tac_count = fields.Integer(string='Số tương tác', compute='_compute_dashboard_fields', store=True)
    hop_dong_count = fields.Integer(string='Số hợp đồng', compute='_compute_dashboard_fields', store=True)
    tong_cong_viec_mo = fields.Integer(string='Công việc mở', compute='_compute_dashboard_fields', store=True)
    tong_cong_viec_qua_han = fields.Integer(string='Công việc quá hạn', compute='_compute_dashboard_fields', store=True)
    tong_hop_dong = fields.Integer(string='Tổng hợp đồng', compute='_compute_dashboard_fields', store=True)
    lich_hen_gan_nhat = fields.Datetime(string='Lịch hẹn gần nhất', compute='_compute_dashboard_fields', store=True)

    @api.depends(
        'cong_viec_ids.trang_thai',
        'cong_viec_ids.is_qua_han',
        'tuong_tac_ids.ngay_hen_tiep',
        'hop_dong_ids',
    )
    def _compute_dashboard_fields(self):
        for record in self:
            open_tasks = record.cong_viec_ids.filtered(lambda task: task.trang_thai not in ('hoan_thanh', 'huy'))
            overdue_tasks = open_tasks.filtered('is_qua_han')
            upcoming_dates = record.tuong_tac_ids.filtered(lambda i: i.ngay_hen_tiep).mapped('ngay_hen_tiep')
            record.cong_viec_count = len(record.cong_viec_ids)
            record.tuong_tac_count = len(record.tuong_tac_ids)
            record.hop_dong_count = len(record.hop_dong_ids)
            record.tong_cong_viec_mo = len(open_tasks)
            record.tong_cong_viec_qua_han = len(overdue_tasks)
            record.tong_hop_dong = len(record.hop_dong_ids)
            record.lich_hen_gan_nhat = min(upcoming_dates) if upcoming_dates else False

    @api.onchange('ten_cong_ty', 'nguoi_lien_he')
    def _onchange_business_identity(self):
        for record in self:
            if not record.ten_khach_hang:
                record.ten_khach_hang = record.ten_cong_ty or record.nguoi_lien_he
            if record.ten_khach_hang and not record.ten_cong_ty and not record.nguoi_lien_he:
                record.ten_cong_ty = record.ten_khach_hang

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_business_identity_values(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._sync_business_identity_values(vals)
        return super().write(vals)

    def _sync_business_identity_values(self, vals):
        company_name = (vals.get('ten_cong_ty') or '').strip()
        contact_name = (vals.get('nguoi_lien_he') or '').strip()
        display_name = (vals.get('ten_khach_hang') or '').strip()
        if not display_name:
            vals['ten_khach_hang'] = company_name or contact_name or vals.get('ten_khach_hang')
        if display_name and not company_name and not contact_name:
            vals['ten_cong_ty'] = display_name

    def action_view_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Công việc của khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'kanban,tree,form',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {'default_khach_hang_id': self.id},
        }

    def action_create_cong_viec(self):
        self.ensure_one()
        loai = self.env['loai_cong_viec'].search([], limit=1)
        return {
            'name': 'Tạo công việc mới',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'form',
            'context': {
                'default_khach_hang_id': self.id,
                'default_nhan_vien_thuc_hien_id': self.nhan_vien_phu_trach_id.id,
                'default_nguon_tao': 'thu_cong',
                'default_loai_cong_viec_id': loai.id,
            },
        }

    def action_view_tuong_tac(self):
        self.ensure_one()
        return {
            'name': 'Tương tác khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'tuong_tac_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {
                'default_khach_hang_id': self.id,
                'default_nhan_vien_id': self.nhan_vien_phu_trach_id.id,
            },
        }

    def action_create_tuong_tac(self):
        self.ensure_one()
        return {
            'name': 'Tạo tương tác mới',
            'type': 'ir.actions.act_window',
            'res_model': 'tuong_tac_khach_hang',
            'view_mode': 'form',
            'context': {
                'default_khach_hang_id': self.id,
                'default_nhan_vien_id': self.nhan_vien_phu_trach_id.id,
                'default_ten_tuong_tac': f'Tương tác với {self.ten_khach_hang}',
            },
        }

    def action_view_hop_dong(self):
        self.ensure_one()
        return {
            'name': 'Hợp đồng khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'hop_dong_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {
                'default_khach_hang_id': self.id,
                'default_nhan_vien_phu_trach_id': self.nhan_vien_phu_trach_id.id,
            },
        }

    def action_create_hop_dong(self):
        self.ensure_one()
        return {
            'name': 'Tạo hợp đồng',
            'type': 'ir.actions.act_window',
            'res_model': 'hop_dong_khach_hang',
            'view_mode': 'form',
            'context': {
                'default_khach_hang_id': self.id,
                'default_nhan_vien_phu_trach_id': self.nhan_vien_phu_trach_id.id,
                'default_ten_hop_dong': f'Hợp đồng - {self.ten_khach_hang}',
            },
        }
