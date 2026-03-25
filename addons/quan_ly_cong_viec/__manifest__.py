# -*- coding: utf-8 -*-
{
    'name': "Quản lý công việc",
    'summary': "Quản lý khách hàng, tương tác chăm sóc, công việc và hợp đồng nhẹ",
    'description': """
        Module Quản lý công việc giúp:
        - Quản lý danh sách công việc và theo dõi tiến độ
        - Gắn công việc với khách hàng và tương tác chăm sóc
        - Sinh công việc từ tương tác khách hàng
        - Quản lý hợp đồng nhẹ sau khi chốt khách
        - Tích hợp AI gợi ý ưu tiên và đầu việc
    """,
    'author': "TungNT",
    'website': "https://www.yourcompany.com",
    'license': 'LGPL-3',
    'category': 'Productivity',
    'version': '0.2',
    'depends': ['base', 'mail', 'nhan_su', 'quan_ly_khach_hang'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/loai_cong_viec_data.xml',
        'data/contract_cron.xml',
        'views/cong_viec_view.xml',
        'views/tuong_tac_khach_hang_view.xml',
        'views/hop_dong_khach_hang_view.xml',
        'views/loai_cong_viec_view.xml',
        'views/nhan_vien_view_inherit.xml',
        'views/khach_hang_view_inherit.xml',
        'wizard/ai_goi_y_cong_viec_wizard_view.xml',
        'wizard/cong_viec_chatbot_wizard_view.xml',
        'views/menu_view.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'quan_ly_cong_viec/static/src/css/cong_viec_chatbot.css',
            'quan_ly_cong_viec/static/src/js/cong_viec_chatbot_form.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
