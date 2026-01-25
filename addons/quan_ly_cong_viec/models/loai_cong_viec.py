# -*- coding: utf-8 -*-

from odoo import models, fields

class LoaiCongViec(models.Model):
    _name = 'loai_cong_viec'
    _description = 'Loại công việc'
    _rec_name = 'ten_loai'

    ten_loai = fields.Char(string="Tên loại công việc", required=True)
    mo_ta = fields.Text(string="Mô tả")
