from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KhachHang(models.Model):
    _name = 'khach_hang'
    _description = 'Khách hàng'
    _rec_name = 'ten_khach_hang'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    ma_khach_hang = fields.Char(
        string="Mã khách hàng",
        required=True,
        tracking=True
    )

    ten_khach_hang = fields.Char(
        string="Tên khách hàng",
        required=True,
        tracking=True
    )

    loai_khach_hang = fields.Selection(
        [
            ('le', 'Khách lẻ'),
            ('si', 'Khách sỉ'),
            ('vip', 'VIP')
        ],
        string="Loại khách hàng",
        default='le',
        tracking=True
    )

    so_dien_thoai = fields.Char(
        string="Số điện thoại",
        tracking=True
    )

    email = fields.Char(
        string="Email",
        tracking=True
    )

    dia_chi = fields.Char(
        string="Địa chỉ",
        tracking=True
    )

    nhan_vien_phu_trach_id = fields.Many2one(
        'nhan_vien',
        string="Nhân viên phụ trách",
        tracking=True
    )

    trang_thai = fields.Selection(
        [
            ('moi', 'Khách mới'),
            ('dang_cham_soc', 'Đang chăm sóc'),
            ('tiem_nang', 'Tiềm năng'),
            ('ngung', 'Ngừng hợp tác')
        ],
        default='moi',
        string="Trạng thái",
        tracking=True
    )

    _sql_constraints = [
        (
            'ma_khach_hang_unique',
            'unique(ma_khach_hang)',
            'Mã khách hàng phải là duy nhất!'
        ),
        (
            'so_dien_thoai_unique',
            'unique(so_dien_thoai)',
            'Số điện thoại phải là duy nhất!'
        )
    ]

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and '@' not in record.email:
                raise ValidationError("Email không hợp lệ")
