# -*- coding: utf-8 -*-

from odoo import models, fields, api

class NhanVien(models.Model):
    _inherit = 'nhan_vien'

    cong_viec_ids = fields.One2many(
        'cong_viec', 
        'nhan_vien_thuc_hien_id', 
        string='Danh sách công việc'
    )
    
    # Thêm field user_id để liên kết nhân viên với tài khoản hệ thống
    user_id = fields.Many2one('res.users', string="Tài khoản hệ thống")

    def action_view_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Công việc được giao',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'tree,form',
            'domain': [('nhan_vien_thuc_hien_id', '=', self.id)],
            'context': {'default_nhan_vien_thuc_hien_id': self.id},
        }
