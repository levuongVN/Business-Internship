# -*- coding: utf-8 -*-
{
    'name': "Quản lý công việc",
    'summary': """
        Module quản lý công việc, giao việc cho nhân viên và theo dõi tiến độ
    """,
    'description': """
        Module Quản lý công việc giúp:
        - Tạo và quản lý danh sách công việc
        - Giao việc cho nhân viên
        - Gắn công việc với khách hàng cụ thể
        - Theo dõi trạng thái và tiến độ
    """,
    'author': "TungNT",
    'website': "https://www.yourcompany.com",
    'category': 'Productivity',
    'version': '0.1',
    'depends': ['base', 'nhan_su', 'quan_ly_khach_hang'],
    'data': [
        'security/ir.model.access.csv',
        'views/cong_viec_view.xml',
        'views/loai_cong_viec_view.xml',
        'views/nhan_vien_view_inherit.xml',
        'views/khach_hang_view_inherit.xml',
        'views/menu_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
