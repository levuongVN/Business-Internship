# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KhachHang(models.Model):
    _inherit = 'khach_hang'

    cong_viec_ids = fields.One2many(
        'cong_viec', 
        'khach_hang_id', 
        string='Danh sách công việc'
    )

    def action_view_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Công việc của khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'tree,form',
            'domain': [('khach_hang_id', '=', self.id)],
            'context': {'default_khach_hang_id': self.id},
        }

    def action_create_cong_viec(self):
        self.ensure_one()
        return {
            'name': 'Tạo công việc mới',
            'type': 'ir.actions.act_window',
            'res_model': 'cong_viec',
            'view_mode': 'form',
            'context': {'default_khach_hang_id': self.id},
        }
