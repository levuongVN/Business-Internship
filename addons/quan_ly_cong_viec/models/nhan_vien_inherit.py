# -*- coding: utf-8 -*-

from odoo import api, fields, models


class NhanVien(models.Model):
    _inherit = 'nhan_vien'

    cong_viec_ids = fields.One2many('cong_viec', 'nhan_vien_thuc_hien_id', string='Danh sách công việc')
    khach_hang_phu_trach_ids = fields.One2many('khach_hang', 'nhan_vien_phu_trach_id', string='Khách hàng phụ trách')
    tuong_tac_ids = fields.One2many('tuong_tac_khach_hang', 'nhan_vien_id', string='Tương tác phụ trách')
    hop_dong_ids = fields.One2many('hop_dong_khach_hang', 'nhan_vien_phu_trach_id', string='Hợp đồng phụ trách')
    user_id = fields.Many2one('res.users', string='Tài khoản hệ thống')
    cong_viec_count = fields.Integer(string='Số công việc', compute='_compute_dashboard_fields')
    khach_hang_phu_trach_count = fields.Integer(string='Số khách hàng phụ trách', compute='_compute_dashboard_fields')
    tuong_tac_count = fields.Integer(string='Số tương tác', compute='_compute_dashboard_fields')

    @api.depends('cong_viec_ids', 'khach_hang_phu_trach_ids', 'tuong_tac_ids')
    def _compute_dashboard_fields(self):
        for record in self:
            record.cong_viec_count = len(record.cong_viec_ids)
            record.khach_hang_phu_trach_count = len(record.khach_hang_phu_trach_ids)
            record.tuong_tac_count = len(record.tuong_tac_ids)

    def action_view_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Công việc được giao',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'kanban,tree,form',
            'domain': [('nhan_vien_thuc_hien_id', '=', self.id)],
            'context': {'default_nhan_vien_thuc_hien_id': self.id},
        }

    def action_view_khach_hang_phu_trach(self):
        self.ensure_one()
        return {
            'name': 'Khách hàng phụ trách',
            'type': 'ir.actions.act_window',
            'res_model': 'khach_hang',
            'view_mode': 'tree,form',
            'domain': [('nhan_vien_phu_trach_id', '=', self.id)],
            'context': {'default_nhan_vien_phu_trach_id': self.id},
        }

    def action_view_tuong_tac(self):
        self.ensure_one()
        return {
            'name': 'Tương tác phụ trách',
            'type': 'ir.actions.act_window',
            'res_model': 'tuong_tac_khach_hang',
            'view_mode': 'tree,form',
            'domain': [('nhan_vien_id', '=', self.id)],
            'context': {'default_nhan_vien_id': self.id},
        }
