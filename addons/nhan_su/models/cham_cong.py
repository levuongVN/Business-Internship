from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time


class ChamCong(models.Model):
    _name = 'cham_cong'
    _description = 'Chấm công nhân viên'
    _order = 'check_in desc'

    # ================== BASIC ==================

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên',
        required=True,
        ondelete='cascade'
    )

    check_in = fields.Datetime(string='Giờ vào', required=True)
    check_out = fields.Datetime(string='Giờ ra')
    ghi_chu = fields.Text("Ghi chú")
    from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time


class ChamCong(models.Model):
    _name = 'cham_cong'
    _description = 'Chấm công nhân viên'
    _order = 'check_in desc'

    # ================== BASIC ==================

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên',
        required=True,
        ondelete='cascade'
    )
        # ================== RELATED LƯƠNG TỪ NHÂN VIÊN ==================
    luong_co_ban = fields.Float(string="Lương cơ bản")
    cong_khoan = fields.Integer(string="Công khoán", default=26)
    phu_cap = fields.Float(string="Phụ cấp")
    thuong_phat = fields.Float(string="Thưởng / Phạt")
    check_in = fields.Datetime(string='Giờ vào', required=True)
    check_out = fields.Datetime(string='Giờ ra')
    ghi_chu = fields.Text("Ghi chú")

    # ================== CHẤM CÔNG NGÀY ==================

    so_gio_lam = fields.Float(
        string='Số giờ làm',
        compute='_compute_gio_lam',
        store=True
    )

    cong_thuc_te = fields.Float(
        string='Công thực tế',
        compute='_compute_cong_thuc_te',
        store=True
    )

    so_gio_ot = fields.Float(
        string='Số giờ OT',
        compute='_compute_ot',
        store=True
    )

    tien_ot = fields.Integer(
        string='Tiền OT',
        compute='_compute_tien_ot',
        store=True
    )

    # ================== TRẠNG THÁI ==================

    di_muon = fields.Boolean(
        string='Đi muộn',
        compute='_compute_trang_thai',
        store=True
    )

    ve_som = fields.Boolean(
        string='Về sớm',
        compute='_compute_trang_thai',
        store=True
    )

    # ================== LƯƠNG ==================

    luong_ngay = fields.Float(
        string='Lương ngày',
        compute='_compute_luong',
        store=True
    )

    luong_thang = fields.Float(
        string='Lương tháng (theo ngày)',
        compute='_compute_luong',
        store=True
    )

    # ================== COMPUTE ==================

    @api.depends('check_in', 'check_out')
    def _compute_gio_lam(self):
        for r in self:
            r.so_gio_lam = 0
            if r.check_in and r.check_out:
                r.so_gio_lam = (r.check_out - r.check_in).total_seconds() / 3600

    @api.depends('so_gio_lam')
    def _compute_cong_thuc_te(self):
        for r in self:
            if r.so_gio_lam >= 8:
                r.cong_thuc_te = 1
            elif r.so_gio_lam > 0:
                r.cong_thuc_te = r.so_gio_lam / 8
            else:
                r.cong_thuc_te = 0

    @api.depends('check_in', 'check_out')
    def _compute_trang_thai(self):
        gio_vao = time(8, 0)
        gio_ra = time(17, 0)

        for r in self:
            r.di_muon = False
            r.ve_som = False

            if r.check_in:
                check_in_local = fields.Datetime.context_timestamp(r, r.check_in)
                if check_in_local.time() > gio_vao:
                    r.di_muon = True

            if r.check_out:
                check_out_local = fields.Datetime.context_timestamp(r, r.check_out)
                if check_out_local.time() < gio_ra:
                    r.ve_som = True

    @api.depends('check_out')
    def _compute_ot(self):
        gio_ra = time(17, 0)

        for r in self:
            r.so_gio_ot = 0
            if not r.check_out:
                continue

            check_out_local = fields.Datetime.context_timestamp(r, r.check_out)
            if check_out_local.time() > gio_ra:
                ot = (
                    datetime.combine(check_out_local.date(), check_out_local.time())
                    - datetime.combine(check_out_local.date(), gio_ra)
                )
                r.so_gio_ot = ot.total_seconds() / 3600

    @api.depends('so_gio_ot')
    def _compute_tien_ot(self):
        for r in self:
            if r.so_gio_ot >= 3:
                r.tien_ot = 800_000
            elif r.so_gio_ot >= 2:
                r.tien_ot = 450_000
            elif r.so_gio_ot >= 1:
                r.tien_ot = 200_000
            else:
                r.tien_ot = 0

    # ================== TÍNH LƯƠNG ==================

    @api.depends(
        'cong_thuc_te',
        'tien_ot',
        'luong_co_ban',
        'cong_khoan',
        'phu_cap',
        'thuong_phat'
    )
    def _compute_luong(self):
        for r in self:
            if not r.cong_khoan:
                r.luong_ngay = 0
                r.luong_thang = 0
                continue

            r.luong_ngay = r.luong_co_ban / r.cong_khoan
            r.luong_thang = (
                r.luong_ngay * r.cong_thuc_te +
                r.phu_cap +
                r.thuong_phat +
                r.tien_ot
            )

    # ================== CONSTRAINT ==================

    @api.constrains('check_in', 'check_out')
    def _check_time(self):
        for r in self:
            if r.check_out and r.check_out < r.check_in:
                raise ValidationError("Giờ ra không được nhỏ hơn giờ vào")

    @api.constrains('nhan_vien_id', 'check_in')
    def _check_duplicate(self):
        for r in self:
            if not r.check_in:
                continue

            start = datetime.combine(r.check_in.date(), time.min)
            end = datetime.combine(r.check_in.date(), time.max)

            exist = self.search([
                ('nhan_vien_id', '=', r.nhan_vien_id.id),
                ('check_in', '>=', start),
                ('check_in', '<=', end),
                ('id', '!=', r.id)
            ])

            if exist:
                raise ValidationError("Nhân viên đã chấm công trong ngày này")

    # ================== CHẤM CÔNG NGÀY ==================

    so_gio_lam = fields.Float(
        string='Số giờ làm',
        compute='_compute_gio_lam',
        store=True
    )

    cong_thuc_te = fields.Float(
        string='Công thực tế',
        compute='_compute_cong_thuc_te',
        store=True
    )

    so_gio_ot = fields.Float(
        string='Số giờ OT',
        compute='_compute_ot',
        store=True
    )

    tien_ot = fields.Integer(
        string='Tiền OT',
        compute='_compute_tien_ot',
        store=True
    )

    # ================== TRẠNG THÁI ==================

    di_muon = fields.Boolean(
        string='Đi muộn',
        compute='_compute_trang_thai',
        store=True
    )

    ve_som = fields.Boolean(
        string='Về sớm',
        compute='_compute_trang_thai',
        store=True
    )

    # ================== LƯƠNG ==================

    luong_ngay = fields.Float(
        string='Lương ngày',
        compute='_compute_luong',
        store=True
    )

    luong_thang = fields.Float(
        string='Lương tháng (theo ngày)',
        compute='_compute_luong',
        store=True
    )

    # ================== COMPUTE ==================

    @api.depends('check_in', 'check_out')
    def _compute_gio_lam(self):
        for r in self:
            r.so_gio_lam = 0
            if r.check_in and r.check_out:
                r.so_gio_lam = (r.check_out - r.check_in).total_seconds() / 3600

    @api.depends('so_gio_lam')
    def _compute_cong_thuc_te(self):
        for r in self:
            if r.so_gio_lam >= 8:
                r.cong_thuc_te = 1
            elif r.so_gio_lam > 0:
                r.cong_thuc_te = r.so_gio_lam / 8
            else:
                r.cong_thuc_te = 0

    @api.depends('check_in', 'check_out')
    def _compute_trang_thai(self):
        gio_vao = time(8, 0)
        gio_ra = time(17, 0)

        for r in self:
            r.di_muon = False
            r.ve_som = False

            if r.check_in:
                check_in_local = fields.Datetime.context_timestamp(r, r.check_in)
                if check_in_local.time() > gio_vao:
                    r.di_muon = True

            if r.check_out:
                check_out_local = fields.Datetime.context_timestamp(r, r.check_out)
                if check_out_local.time() < gio_ra:
                    r.ve_som = True

    @api.depends('check_out')
    def _compute_ot(self):
        gio_ra = time(17, 0)

        for r in self:
            r.so_gio_ot = 0
            if not r.check_out:
                continue

            check_out_local = fields.Datetime.context_timestamp(r, r.check_out)
            if check_out_local.time() > gio_ra:
                ot = (
                    datetime.combine(check_out_local.date(), check_out_local.time())
                    - datetime.combine(check_out_local.date(), gio_ra)
                )
                r.so_gio_ot = ot.total_seconds() / 3600

    @api.depends('so_gio_ot')
    def _compute_tien_ot(self):
        for r in self:
            if r.so_gio_ot >= 3:
                r.tien_ot = 800_000
            elif r.so_gio_ot >= 2:
                r.tien_ot = 450_000
            elif r.so_gio_ot >= 1:
                r.tien_ot = 200_000
            else:
                r.tien_ot = 0

    # ================== TÍNH LƯƠNG ==================

    @api.depends(
        'cong_thuc_te',
        'tien_ot',
        'nhan_vien_id.luong_co_ban',
        'nhan_vien_id.cong_khoan',
        'nhan_vien_id.phu_cap',
        'nhan_vien_id.thuong_phat'
    )
    def _compute_luong(self):
        for r in self:
            nv = r.nhan_vien_id

            if not nv or not nv.cong_khoan:
                r.luong_ngay = 0
                r.luong_thang = 0
                continue

            # Lương ngày
            r.luong_ngay = nv.luong_co_ban / nv.cong_khoan

            # Lương theo ngày chấm công
            r.luong_thang = (
                r.luong_ngay * r.cong_thuc_te +
                nv.phu_cap +
                nv.thuong_phat +
                r.tien_ot
            )

    # ================== CONSTRAINT ==================

    @api.constrains('check_in', 'check_out')
    def _check_time(self):
        for r in self:
            if r.check_out and r.check_out < r.check_in:
                raise ValidationError("Giờ ra không được nhỏ hơn giờ vào")

    @api.constrains('nhan_vien_id', 'check_in')
    def _check_duplicate(self):
        for r in self:
            if not r.check_in:
                continue

            start = datetime.combine(r.check_in.date(), time.min)
            end = datetime.combine(r.check_in.date(), time.max)

            exist = self.search([
                ('nhan_vien_id', '=', r.nhan_vien_id.id),
                ('check_in', '>=', start),
                ('check_in', '<=', end),
                ('id', '!=', r.id)
            ])

            if exist:
                raise ValidationError("Nhân viên đã chấm công trong ngày này")
