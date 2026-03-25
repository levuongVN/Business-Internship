# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HopDongKhachHang(models.Model):
    _name = 'hop_dong_khach_hang'
    _description = 'Hợp đồng khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'ten_hop_dong'
    _order = 'ngay_ky desc, id desc'

    so_hop_dong = fields.Char(string='Số hợp đồng', required=True, copy=False, default='New', tracking=True)
    ten_hop_dong = fields.Char(string='Tên hợp đồng', required=True, tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string='Khách hàng', required=True, tracking=True)
    nhan_vien_phu_trach_id = fields.Many2one('nhan_vien', string='Nhân viên phụ trách', required=True, tracking=True)
    tuong_tac_id = fields.Many2one('tuong_tac_khach_hang', string='Tương tác nguồn', tracking=True, ondelete='set null')
    cong_viec_id = fields.Many2one('cong_viec', string='Công việc nguồn', tracking=True, ondelete='set null')
    ngay_ky = fields.Date(string='Ngày ký', tracking=True)
    ngay_hieu_luc = fields.Date(string='Ngày hiệu lực', tracking=True)
    ngay_het_han = fields.Date(string='Ngày hết hạn', tracking=True)
    gia_tri = fields.Float(string='Giá trị hợp đồng', tracking=True)
    trang_thai = fields.Selection([
        ('du_thao', 'Dự thảo'),
        ('da_gui', 'Đã gửi'),
        ('da_ky', 'Đã ký'),
        ('het_han', 'Hết hạn'),
        ('huy', 'Hủy'),
    ], string='Trạng thái', default='du_thao', tracking=True)
    ghi_chu = fields.Text(string='Ghi chú')
    tep_dinh_kem = fields.Binary(string='Tệp đính kèm')
    tep_dinh_kem_name = fields.Char(string='Tên tệp')
    is_sap_het_han = fields.Boolean(
        string='Sắp hết hạn',
        compute='_compute_contract_flags',
        search='_search_is_sap_het_han',
    )
    is_qua_han = fields.Boolean(
        string='Quá hạn',
        compute='_compute_contract_flags',
        search='_search_is_qua_han',
    )

    _sql_constraints = [
        ('so_hop_dong_unique', 'unique(so_hop_dong)', 'Số hợp đồng phải là duy nhất!'),
    ]

    @api.depends('ngay_het_han', 'trang_thai')
    def _compute_contract_flags(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_qua_han = bool(
                record.ngay_het_han
                and record.ngay_het_han < today
                and record.trang_thai not in ('huy',)
            )
            record.is_sap_het_han = bool(
                record.ngay_het_han
                and today <= record.ngay_het_han <= fields.Date.add(today, days=30)
                and record.trang_thai not in ('het_han', 'huy')
            )

    @api.model
    def _search_is_sap_het_han(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValidationError('Chỉ hỗ trợ tìm kiếm Boolean cho trường sắp hết hạn.')
        today = fields.Date.context_today(self)
        domain_true = [
            ('ngay_het_han', '>=', today),
            ('ngay_het_han', '<=', fields.Date.add(today, days=30)),
            ('trang_thai', 'not in', ('het_han', 'huy')),
        ]
        if (operator, value) in (('=', True), ('!=', False)):
            return domain_true
        return ['!', '&', '&'] + domain_true

    @api.model
    def _search_is_qua_han(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValidationError('Chỉ hỗ trợ tìm kiếm Boolean cho trường quá hạn.')
        today = fields.Date.context_today(self)
        domain_true = [
            ('ngay_het_han', '<', today),
            ('trang_thai', '!=', 'huy'),
        ]
        if (operator, value) in (('=', True), ('!=', False)):
            return domain_true
        return ['!', '&'] + domain_true

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('so_hop_dong', 'New') == 'New':
                vals['so_hop_dong'] = sequence.next_by_code('hop_dong_khach_hang') or 'New'
            if not vals.get('nhan_vien_phu_trach_id') and vals.get('khach_hang_id'):
                customer = self.env['khach_hang'].browse(vals['khach_hang_id'])
                vals['nhan_vien_phu_trach_id'] = customer.nhan_vien_phu_trach_id.id
        records = super().create(vals_list)
        records._auto_update_contract_workflow()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_contract_workflow_sync'):
            self._auto_update_contract_workflow()
        return result

    @api.constrains('ngay_ky', 'ngay_hieu_luc', 'ngay_het_han')
    def _check_dates(self):
        for record in self:
            if record.ngay_ky and record.ngay_hieu_luc and record.ngay_hieu_luc < record.ngay_ky:
                raise ValidationError('Ngày hiệu lực không được nhỏ hơn ngày ký.')
            if record.ngay_hieu_luc and record.ngay_het_han and record.ngay_het_han < record.ngay_hieu_luc:
                raise ValidationError('Ngày hết hạn không được nhỏ hơn ngày hiệu lực.')

    def _auto_update_contract_workflow(self):
        self._sync_expired_status()
        self._sync_expiry_activity()

    def _sync_expired_status(self):
        today = fields.Date.context_today(self)
        to_expire = self.filtered(
            lambda record: record.ngay_het_han
            and record.ngay_het_han < today
            and record.trang_thai not in ('het_han', 'huy')
        )
        if to_expire:
            super(HopDongKhachHang, to_expire.with_context(skip_contract_workflow_sync=True)).write({
                'trang_thai': 'het_han',
            })

    def _sync_expiry_activity(self):
        todo_activity = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_activity:
            return
        today = fields.Date.context_today(self)
        for record in self:
            activities = record.activity_ids.filtered(lambda a: a.activity_type_id == todo_activity)
            should_schedule = bool(
                record.ngay_het_han
                and today <= record.ngay_het_han <= fields.Date.add(today, days=30)
                and record.trang_thai not in ('het_han', 'huy')
                and record.nhan_vien_phu_trach_id.user_id
            )
            if should_schedule:
                reminder_date = fields.Date.subtract(record.ngay_het_han, days=7) if record.ngay_het_han else today
                if reminder_date < today:
                    reminder_date = today
                vals = {
                    'date_deadline': reminder_date,
                    'user_id': record.nhan_vien_phu_trach_id.user_id.id,
                    'summary': f'Gia hạn hợp đồng {record.so_hop_dong}',
                    'note': (
                        f'Hợp đồng {record.ten_hop_dong} sắp hết hạn vào ngày '
                        f'{record.ngay_het_han or "không xác định"}.'
                    ),
                }
                if activities:
                    activities.write(vals)
                else:
                    record.activity_schedule('mail.mail_activity_data_todo', **vals)
            elif activities:
                activities.unlink()

    @api.model
    def cron_sync_contract_workflow(self):
        contracts = self.search([('trang_thai', '!=', 'huy')])
        contracts._auto_update_contract_workflow()
