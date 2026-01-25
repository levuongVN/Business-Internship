# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date

class CongViec(models.Model):
    _name = 'cong_viec'
    _description = 'Quản lý công việc'
    _rec_name = 'ten_cong_viec'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ten_cong_viec = fields.Char(string='Tên công việc', required=True, tracking=True)
    mo_ta = fields.Text(string='Mô tả chi tiết')
    
    nhan_vien_thuc_hien_id = fields.Many2one(
        'nhan_vien', 
        string='Nhân viên thực hiện', 
        required=True, 
        tracking=True
    )
    
    khach_hang_id = fields.Many2one(
        'khach_hang', 
        string='Khách hàng', 
        tracking=True
    )
    
    loai_cong_viec_id = fields.Many2one(
        'loai_cong_viec', 
        string='Loại công việc',
        required=True
    )

    han_chot = fields.Date(string='Hạn chót', default=fields.Date.today, tracking=True)
    
    muc_do_uu_tien = fields.Selection([
        ('thap', 'Thấp'),
        ('trung_binh', 'Trung bình'),
        ('cao', 'Cao'),
        ('rat_cao', 'Rất cao')
    ], string='Mức độ ưu tiên', default='trung_binh', tracking=True)
    
    trang_thai = fields.Selection([
        ('moi', 'Mới'),
        ('dang_lam', 'Đang làm'),
        ('hoan_thanh', 'Hoàn thành'),
        ('huy', 'Hủy')
    ], string='Trạng thái', default='moi', tracking=True, group_expand='_expand_states')

    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).trang_thai.selection]
