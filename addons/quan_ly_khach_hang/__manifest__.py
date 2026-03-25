{
    'name': 'Quản lý khách hàng',
    'version': '1.0',
    'summary': 'Module quản lý khách hàng cho doanh nghiệp',
    'category': 'Administration',
    'author': 'BTL Odoo',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'nhan_su',
        'mail'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/khach_hang_view.xml',
    ],
    'application': True,
}
