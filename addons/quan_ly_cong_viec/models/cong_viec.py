import requests
import json
from odoo import models, fields, api
from google import genai
from odoo.tools import config
import logging
_logger = logging.getLogger(__name__)


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
    def ai_predict_priority(self):
        api_key = config.get('gemini_api_key')
        if not api_key:
            _logger.error("❌ Chưa cấu hình gemini_api_key trong odoo.conf")
            return

        client = genai.Client(api_key=api_key)

        for record in self:
            prompt = f"""
                    Phân loại mức độ ưu tiên công việc.
                    Tên: {record.ten_cong_viec}
                    Mô tả: {record.mo_ta or ''}
                    Hạn chót: {record.han_chot}

                    Chỉ trả về DUY NHẤT một trong các giá trị sau (không giải thích):
                    thap
                    trung_binh
                    cao
                    rat_cao
                    """
            _logger.info("📤 [Gemini SDK] Prompt:\n%s", prompt)

            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=prompt,
                )

                ai_value = response.text.strip().lower()
                _logger.info("🤖 Gemini trả về: %s", ai_value)

                valid_values = dict(self._fields['muc_do_uu_tien'].selection)
                if ai_value in valid_values:
                    record.muc_do_uu_tien = ai_value
                    _logger.info("✅ Đã set mức độ ưu tiên = %s", ai_value)
                else:
                    _logger.warning("⚠️ Giá trị không hợp lệ từ Gemini: %s", ai_value)

            except Exception as e:
                _logger.exception("💥 Lỗi khi gọi Gemini SDK: %s", e)
    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).trang_thai.selection]