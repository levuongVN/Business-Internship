# -*- coding: utf-8 -*-

from odoo import fields, models


class TuongTacKhachHangAIWizard(models.TransientModel):
    _name = 'tuong_tac_khach_hang_ai_wizard'
    _description = 'AI gợi ý công việc từ tương tác'

    tuong_tac_id = fields.Many2one('tuong_tac_khach_hang', string='Tương tác', required=True)
    warning_message = fields.Text(string='Ghi chú AI')
    line_ids = fields.One2many('tuong_tac_khach_hang_ai_wizard_line', 'wizard_id', string='Gợi ý công việc')

    def _load_suggestions(self, suggestions, warning_message=None):
        self.ensure_one()
        default_type = self.env['loai_cong_viec'].search([], limit=1)
        lines = []
        for item in suggestions:
            due_date = fields.Date.context_today(self)
            due_in_days = int(item.get('due_in_days', 0) or 0)
            if due_in_days:
                due_date = fields.Date.add(due_date, days=due_in_days)
            lines.append((0, 0, {
                'create_task': True,
                'ten_cong_viec': item.get('title'),
                'mo_ta': item.get('description'),
                'muc_do_uu_tien': item.get('priority', 'trung_binh'),
                'han_chot': due_date,
                'nhan_vien_thuc_hien_id': self.tuong_tac_id.nhan_vien_id.id,
                'loai_cong_viec_id': default_type.id,
            }))
        self.write({
            'warning_message': warning_message or False,
            'line_ids': [(5, 0, 0)] + lines,
        })

    def action_create_selected_tasks(self):
        self.ensure_one()
        for line in self.line_ids.filtered('create_task'):
            self.env['cong_viec'].create({
                'ten_cong_viec': line.ten_cong_viec,
                'mo_ta': line.mo_ta,
                'nhan_vien_thuc_hien_id': line.nhan_vien_thuc_hien_id.id or self.tuong_tac_id.nhan_vien_id.id,
                'khach_hang_id': self.tuong_tac_id.khach_hang_id.id,
                'tuong_tac_id': self.tuong_tac_id.id,
                'loai_cong_viec_id': line.loai_cong_viec_id.id,
                'han_chot': line.han_chot,
                'muc_do_uu_tien': line.muc_do_uu_tien,
                'nguon_tao': 'ai_goi_y',
            })
        return {'type': 'ir.actions.act_window_close'}


class TuongTacKhachHangAIWizardLine(models.TransientModel):
    _name = 'tuong_tac_khach_hang_ai_wizard_line'
    _description = 'Dòng gợi ý công việc AI'

    wizard_id = fields.Many2one('tuong_tac_khach_hang_ai_wizard', required=True, ondelete='cascade')
    create_task = fields.Boolean(string='Tạo công việc', default=True)
    ten_cong_viec = fields.Char(string='Tên công việc', required=True)
    mo_ta = fields.Text(string='Mô tả')
    muc_do_uu_tien = fields.Selection([
        ('thap', 'Thấp'),
        ('trung_binh', 'Trung bình'),
        ('cao', 'Cao'),
        ('rat_cao', 'Rất cao'),
    ], string='Ưu tiên', default='trung_binh')
    han_chot = fields.Date(string='Hạn chót')
    nhan_vien_thuc_hien_id = fields.Many2one('nhan_vien', string='Nhân viên thực hiện')
    loai_cong_viec_id = fields.Many2one('loai_cong_viec', string='Loại công việc', required=True)
