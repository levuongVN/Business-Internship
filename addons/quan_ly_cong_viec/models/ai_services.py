# -*- coding: utf-8 -*-
import json
import logging
import re
import unicodedata

from odoo import fields
from odoo.tools import config

try:
    from google import genai
except Exception:  # pragma: no cover - optional dependency
    genai = None

_logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODELS = (
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
)
PRIORITY_VALUES = {'thap', 'trung_binh', 'cao', 'rat_cao'}


def _clean_json_payload(payload):
    payload = (payload or '').strip()
    if payload.startswith('```'):
        payload = re.sub(r'^```(?:json)?', '', payload).strip()
        payload = re.sub(r'```$', '', payload).strip()
    return payload


def _extract_json_array(payload):
    payload = _clean_json_payload(payload)
    if payload.startswith('[') and payload.endswith(']'):
        return payload
    match = re.search(r'(\[[\s\S]*\])', payload)
    if match:
        return match.group(1)
    return payload


def _extract_priority_value(payload):
    payload = (payload or '').strip().lower()
    match = re.search(r'\b(thap|trung_binh|cao|rat_cao)\b', payload)
    if match:
        return match.group(1)
    return None


def _safe_text(value):
    return str(value).strip() if value not in (None, False) else 'Không có'


def _normalize_text(value):
    value = _safe_text(value).lower()
    value = unicodedata.normalize('NFD', value)
    value = ''.join(char for char in value if unicodedata.category(char) != 'Mn')
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _employee_name(employee):
    if not employee:
        return 'Không có'
    return (
        getattr(employee, 'ho_va_ten', False)
        or getattr(employee, 'display_name', False)
        or getattr(employee, 'ten', False)
        or 'Không có'
    )


def _customer_name(customer):
    if not customer:
        return 'Không có'
    return (
        getattr(customer, 'ten_khach_hang', False)
        or getattr(customer, 'display_name', False)
        or 'Không có'
    )


def get_gemini_client():
    api_key = config.get('gemini_api_key')
    if not api_key:
        return None, 'Chưa cấu hình gemini_api_key trong odoo.conf'
    if genai is None:
        return None, 'Thư viện google-genai chưa sẵn sàng trong môi trường chạy'
    try:
        return genai.Client(api_key=api_key), None
    except Exception as exc:  # pragma: no cover - depends on runtime env
        _logger.exception('Không khởi tạo được Gemini client: %s', exc)
        return None, str(exc)


def get_gemini_model():
    return get_gemini_models()[0]


def get_gemini_models():
    configured_models = []
    primary_model = (config.get('gemini_model') or '').strip()
    candidate_models = (config.get('gemini_model_candidates') or '').split(',')

    if primary_model:
        configured_models.append(primary_model)

    configured_models.extend(
        candidate.strip()
        for candidate in candidate_models
        if candidate.strip()
    )

    if not configured_models:
        configured_models = list(DEFAULT_GEMINI_MODELS)

    unique_models = []
    for model in configured_models:
        if model not in unique_models:
            unique_models.append(model)
    return unique_models


def _should_try_next_model(error):
    lowered = (error or '').lower()
    return any(token in lowered for token in (
        '429',
        'resource_exhausted',
        '503',
        'unavailable',
        'high demand',
        '403',
        'permission_denied',
        '404',
        'not found',
    ))


def _generate_content_with_fallback(client, prompt):
    attempted = []
    for model in get_gemini_models():
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            if attempted:
                _logger.info(
                    'Gemini fallback succeeded with model %s after failures on: %s',
                    model,
                    ', '.join(item['model'] for item in attempted),
                )
            return response.text, model, None
        except Exception as exc:  # pragma: no cover - depends on runtime env
            error = str(exc)
            attempted.append({'model': model, 'error': error})
            _logger.warning('Gemini model %s failed: %s', model, error)
            if not _should_try_next_model(error):
                return None, None, humanize_ai_error(
                    error,
                    model=model,
                    tried_models=[item['model'] for item in attempted],
                )

    last_attempt = attempted[-1] if attempted else {'model': get_gemini_model(), 'error': ''}
    return None, None, humanize_ai_error(
        last_attempt['error'],
        model=last_attempt['model'],
        tried_models=[item['model'] for item in attempted],
    )


def humanize_ai_error(error, model=None, tried_models=None):
    message = (error or '').strip()
    if not message:
        return 'Không thể kết nối Gemini.'

    lowered = message.lower()
    model = model or get_gemini_model()
    attempted = ', '.join(tried_models or [])
    suffix = f' Đã thử: {attempted}.' if attempted else ''
    if '429' in lowered and 'resource_exhausted' in lowered:
        return (
            f'Gemini đang hết quota hoặc vượt giới hạn sử dụng cho model {model}. '
            f'Hãy kiểm tra quota và billing của API key.{suffix}'
        )
    if '401' in lowered or 'invalid api key' in lowered or 'api key not valid' in lowered:
        return 'Gemini API key không hợp lệ hoặc đã bị thu hồi.'
    if '403' in lowered or 'permission_denied' in lowered:
        return f'API key hiện không có quyền dùng model {model}. Hãy kiểm tra project và billing.{suffix}'
    if '404' in lowered or 'not found' in lowered:
        return f'Không tìm thấy model Gemini `{model}`.{suffix}'
    if '503' in lowered or 'unavailable' in lowered or 'high demand' in lowered:
        return f'Model Gemini `{model}` đang quá tải tạm thời. Hệ thống sẽ thử model khác nếu có.{suffix}'
    return message


def predict_task_priority(task_name, description, deadline):
    client, error = get_gemini_client()
    if not client:
        return None, error

    prompt = f"""
    Phân loại mức độ ưu tiên công việc.
    Tên: {task_name}
    Mô tả: {description or ''}
    Hạn chót: {deadline or ''}

    Chỉ trả về đúng một giá trị trong danh sách:
    thap
    trung_binh
    cao
    rat_cao
    """

    try:
        response_text, _used_model, error = _generate_content_with_fallback(client, prompt)
        if error:
            return None, error
        value = _extract_priority_value(response_text)
        if value in PRIORITY_VALUES:
            return value, None
        return None, 'Gemini trả về giá trị ưu tiên không hợp lệ'
    except Exception as exc:  # pragma: no cover - depends on runtime env
        _logger.exception('Lỗi khi gọi Gemini phân loại ưu tiên: %s', exc)
        return None, humanize_ai_error(str(exc))


def suggest_tasks_from_interaction(interaction):
    fallback = _fallback_suggestions(interaction)
    client, error = get_gemini_client()
    if not client:
        return fallback, error

    prompt = f"""
    Bạn là trợ lý quản lý công việc cho doanh nghiệp.
    Hãy đọc nội dung tương tác khách hàng và đề xuất từ 2 đến 4 công việc follow-up.

    Khách hàng: {interaction.khach_hang_id.ten_khach_hang}
    Loại tương tác: {interaction.loai_tuong_tac}
    Nội dung: {interaction.noi_dung or ''}
    Kết quả hiện tại: {interaction.ket_qua or ''}
    Ngày hẹn tiếp: {interaction.ngay_hen_tiep or ''}

    Trả về JSON array, mỗi phần tử có cấu trúc:
    {{
      "title": "Tên công việc",
      "description": "Mô tả ngắn",
      "priority": "thap|trung_binh|cao|rat_cao",
      "due_in_days": 1
    }}

    Không trả lời giải thích ngoài JSON.
    """

    try:
        response_text, _used_model, error = _generate_content_with_fallback(client, prompt)
        if error:
            return fallback, error
        raw = _extract_json_array(response_text)
        payload = json.loads(raw)
        suggestions = []
        for item in payload:
            priority = item.get('priority', 'trung_binh')
            if priority not in PRIORITY_VALUES:
                priority = 'trung_binh'
            try:
                due_in_days = int(item.get('due_in_days', 1))
            except (TypeError, ValueError):
                due_in_days = 1
            suggestions.append({
                'title': item.get('title') or 'Công việc theo dõi khách hàng',
                'description': item.get('description') or interaction.noi_dung or '',
                'priority': priority,
                'due_in_days': max(due_in_days, 0),
            })
        if suggestions:
            return suggestions, None
        return fallback, 'Gemini không trả về gợi ý công việc hợp lệ'
    except Exception as exc:  # pragma: no cover - depends on runtime env
        _logger.exception('Lỗi khi gọi Gemini gợi ý công việc: %s', exc)
        return fallback, humanize_ai_error(str(exc))


def answer_task_chatbot(task, question, history=None):
    return answer_quan_ly_cong_viec_chatbot(task.env, question, history=history, task=task)


def answer_quan_ly_cong_viec_chatbot(env, question, history=None, task=None):
    fallback = _fallback_task_chatbot_response(task, question) if task else _fallback_module_chatbot_response(env, question)
    direct_answer = _direct_task_chat_response(task, question) if task else _direct_module_chat_response(env, question)
    if direct_answer:
        return direct_answer, None

    client, error = get_gemini_client()
    if not client:
        return fallback, error

    history_lines = []
    for role, content in history or []:
        if content:
            history_lines.append(f'{role}: {content}')

    scope_prompt = 'một công việc cụ thể' if task else 'toàn bộ module quản lý công việc'
    context_payload = _build_task_chat_context(task) if task else _build_module_chat_context(env)

    prompt = f"""
    Bạn là chatbot nội bộ của module quan_ly_cong_viec trong Odoo.
    Chỉ được trả lời bằng thông tin nằm trong CONTEXT dưới đây và chỉ cho các nội dung thuộc:
    - công việc
    - tương tác khách hàng
    - hợp đồng khách hàng
    - khách hàng
    - nhân viên phụ trách

    Nếu câu hỏi không liên quan đến các mục trên hoặc không có trong CONTEXT, trả lời đúng câu này:
    "Tôi chỉ hỗ trợ các nội dung liên quan đến công việc, tương tác khách hàng và hợp đồng trong module quản lý công việc."

    Phong cách trả lời:
    - ngắn gọn, rõ ràng, thông minh
    - ưu tiên tóm tắt tình trạng công việc, việc cần làm tiếp theo, rủi ro, hợp đồng liên quan
    - không suy diễn ra ngoài dữ liệu được cung cấp
    - phạm vi hiện tại là: {scope_prompt}

    HISTORY:
    {_safe_text(chr(10).join(history_lines))}

    CONTEXT:
    {context_payload}

    CÂU HỎI:
    {_safe_text(question)}
    """

    try:
        response_text, _used_model, warning = _generate_content_with_fallback(client, prompt)
        if warning:
            return fallback, warning
        answer = (response_text or '').strip()
        return answer or fallback, None
    except Exception as exc:  # pragma: no cover - depends on runtime env
        _logger.exception('Lỗi khi gọi Gemini chatbot công việc: %s', exc)
        return fallback, humanize_ai_error(str(exc))


def _fallback_suggestions(interaction):
    customer_name = interaction.khach_hang_id.ten_khach_hang or 'khách hàng'
    content = interaction.noi_dung or 'Theo dõi và cập nhật nhu cầu của khách hàng.'
    mapping = {
        'goi_dien': [
            {
                'title': f'Gọi lại chăm sóc {customer_name}',
                'description': content,
                'priority': 'trung_binh',
                'due_in_days': 1,
            },
            {
                'title': f'Cập nhật kết quả cuộc gọi với {customer_name}',
                'description': 'Tổng hợp nhu cầu và bước xử lý tiếp theo sau cuộc gọi.',
                'priority': 'thap',
                'due_in_days': 1,
            },
        ],
        'bao_gia': [
            {
                'title': f'Chuẩn bị và gửi báo giá cho {customer_name}',
                'description': content,
                'priority': 'cao',
                'due_in_days': 1,
            },
            {
                'title': f'Theo dõi phản hồi báo giá của {customer_name}',
                'description': 'Chủ động gọi lại hoặc gửi email nhắc phản hồi báo giá.',
                'priority': 'trung_binh',
                'due_in_days': 3,
            },
        ],
        'lich_hen': [
            {
                'title': f'Chuẩn bị nội dung buổi hẹn với {customer_name}',
                'description': content,
                'priority': 'cao',
                'due_in_days': 0,
            },
            {
                'title': f'Xác nhận lịch hẹn với {customer_name}',
                'description': 'Liên hệ xác nhận thời gian, địa điểm và người tham gia.',
                'priority': 'trung_binh',
                'due_in_days': 1,
            },
        ],
    }
    return mapping.get(interaction.loai_tuong_tac, [
        {
            'title': f'Theo dõi khách hàng {customer_name}',
            'description': content,
            'priority': 'trung_binh',
            'due_in_days': 2,
        },
        {
            'title': f'Cập nhật hồ sơ chăm sóc của {customer_name}',
            'description': 'Ghi nhận lại kết quả tương tác và hành động tiếp theo.',
            'priority': 'thap',
            'due_in_days': 1,
        },
    ])


def _build_task_chat_context(task):
    contract_lines = []
    for contract in task.hop_dong_ids:
        contract_lines.append(
            f'- {contract.so_hop_dong}: {contract.ten_hop_dong}, trạng thái {contract.trang_thai}, '
            f'giá trị {_safe_text(contract.gia_tri)}, ngày ký {_safe_text(contract.ngay_ky)}, '
            f'hết hạn {_safe_text(contract.ngay_het_han)}'
        )
    interaction = task.tuong_tac_id
    interaction_text = 'Không có'
    if interaction:
        interaction_text = (
            f'Mã {interaction.ma_tuong_tac}, loại {interaction.loai_tuong_tac}, '
            f'trạng thái {interaction.trang_thai}, ngày hẹn tiếp {_safe_text(interaction.ngay_hen_tiep)}, '
            f'nội dung {_safe_text(interaction.noi_dung)}, kết quả {_safe_text(interaction.ket_qua)}'
        )

    return f"""
    Công việc:
    - Tên: {_safe_text(task.ten_cong_viec)}
    - Mô tả: {_safe_text(task.mo_ta)}
    - Trạng thái: {_safe_text(task.trang_thai)}
    - Ưu tiên: {_safe_text(task.muc_do_uu_tien)}
    - Hạn chót: {_safe_text(task.han_chot)}
    - Ngày bắt đầu: {_safe_text(task.ngay_bat_dau)}
    - Ngày hoàn thành: {_safe_text(task.ngay_hoan_thanh)}
    - Kết quả xử lý: {_safe_text(task.ket_qua_xu_ly)}
    - Quá hạn: {'Có' if task.is_qua_han else 'Không'}
    - Nguồn tạo: {_safe_text(task.nguon_tao)}

    Khách hàng:
    - Tên: {_safe_text(_customer_name(task.khach_hang_id))}
    - Nhân viên phụ trách khách hàng: {_safe_text(_employee_name(task.khach_hang_id.nhan_vien_phu_trach_id if task.khach_hang_id else False))}

    Nhân viên thực hiện:
    - {_safe_text(_employee_name(task.nhan_vien_thuc_hien_id))}

    Tương tác nguồn:
    - {interaction_text}

    Hợp đồng liên quan:
    {chr(10).join(contract_lines) if contract_lines else '- Không có'}
    """


def _fallback_task_chatbot_response(task, question):
    contracts = task.hop_dong_ids
    next_steps = []
    if task.trang_thai == 'moi':
        next_steps.append('Bắt đầu xử lý và xác nhận lại yêu cầu công việc.')
    elif task.trang_thai == 'dang_lam':
        next_steps.append('Tiếp tục thực hiện và cập nhật kết quả xử lý khi có tiến triển.')
    elif task.trang_thai == 'hoan_thanh':
        next_steps.append('Rà soát đầu ra cuối cùng và kiểm tra hợp đồng hoặc tương tác liên quan.')
    elif task.trang_thai == 'huy':
        next_steps.append('Xác nhận lý do hủy và lưu lại ghi chú nếu cần.')

    if task.is_qua_han:
        next_steps.append('Ưu tiên xử lý ngay vì công việc đang quá hạn.')
    if task.tuong_tac_id and task.tuong_tac_id.ngay_hen_tiep:
        next_steps.append(f'Theo dõi mốc hẹn tiếp: {task.tuong_tac_id.ngay_hen_tiep}.')
    if contracts:
        next_steps.append(f'Có {len(contracts)} hợp đồng liên quan cần đối chiếu.')

    contract_summary = ', '.join(
        f'{contract.so_hop_dong} ({contract.trang_thai})'
        for contract in contracts
    ) or 'Không có hợp đồng liên quan.'

    lines = [
        f'Tóm tắt công việc: {task.ten_cong_viec}.',
        f'Trạng thái hiện tại: {task.trang_thai}.',
        f'Mức ưu tiên: {task.muc_do_uu_tien}.',
        f'Hạn chót: {_safe_text(task.han_chot)}.',
        f'Nhân viên thực hiện: {_safe_text(_employee_name(task.nhan_vien_thuc_hien_id))}.',
        f'Khách hàng: {_safe_text(_customer_name(task.khach_hang_id))}.',
        f'Mô tả chính: {_safe_text(task.mo_ta)}.',
        f'Kết quả xử lý hiện có: {_safe_text(task.ket_qua_xu_ly)}.',
        f'Hợp đồng liên quan: {contract_summary}',
    ]
    if question:
        lines.append(f'Câu hỏi của bạn: {question}')
    if next_steps:
        lines.append('Việc nên làm tiếp:')
        lines.extend(f'- {step}' for step in next_steps)
    return '\n'.join(lines)


def _build_module_chat_context(env):
    task_model = env['cong_viec']
    interaction_model = env['tuong_tac_khach_hang']
    contract_model = env['hop_dong_khach_hang']
    customer_model = env['khach_hang']

    total_tasks = task_model.search_count([])
    open_tasks_count = task_model.search_count([('trang_thai', 'not in', ('hoan_thanh', 'huy'))])
    overdue_tasks_count = task_model.search_count([('is_qua_han', '=', True)])
    done_tasks_count = task_model.search_count([('trang_thai', '=', 'hoan_thanh')])
    total_interactions = interaction_model.search_count([])
    active_interactions = interaction_model.search_count([('trang_thai', 'in', ('moi', 'dang_theo_doi'))])
    total_contracts = contract_model.search_count([])
    signed_contracts = contract_model.search_count([('trang_thai', '=', 'da_ky')])
    expiring_contracts = contract_model.search_count([('is_sap_het_han', '=', True)])
    customers_need_care_count = customer_model.search_count(['|', ('tong_cong_viec_mo', '>', 0), ('lich_hen_gan_nhat', '!=', False)])

    open_tasks = task_model.search([('trang_thai', 'not in', ('hoan_thanh', 'huy'))], limit=8, order='han_chot asc, id desc')
    overdue_tasks = task_model.search([('is_qua_han', '=', True)], limit=8, order='han_chot asc, id desc')
    recent_interactions = interaction_model.search([], limit=8, order='ngay_gio desc, id desc')
    expiring_contract_records = contract_model.search([('is_sap_het_han', '=', True)], limit=8, order='ngay_het_han asc, id desc')
    customers_need_care = customer_model.search(['|', ('tong_cong_viec_mo', '>', 0), ('lich_hen_gan_nhat', '!=', False)], limit=8, order='id desc')

    open_task_lines = [
        f'- {task.ten_cong_viec} | trạng thái {task.trang_thai} | ưu tiên {task.muc_do_uu_tien} | hạn {_safe_text(task.han_chot)} | nhân viên {_employee_name(task.nhan_vien_thuc_hien_id)} | khách hàng {_customer_name(task.khach_hang_id)}'
        for task in open_tasks
    ]
    overdue_task_lines = [
        f'- {task.ten_cong_viec} | hạn {_safe_text(task.han_chot)} | nhân viên {_employee_name(task.nhan_vien_thuc_hien_id)} | khách hàng {_customer_name(task.khach_hang_id)}'
        for task in overdue_tasks
    ]
    interaction_lines = [
        f'- {interaction.ma_tuong_tac} | {interaction.ten_tuong_tac} | loại {interaction.loai_tuong_tac} | trạng thái {interaction.trang_thai} | khách hàng {_customer_name(interaction.khach_hang_id)} | hẹn tiếp {_safe_text(interaction.ngay_hen_tiep)}'
        for interaction in recent_interactions
    ]
    contract_lines = [
        f'- {contract.so_hop_dong} | {contract.ten_hop_dong} | trạng thái {contract.trang_thai} | khách hàng {_customer_name(contract.khach_hang_id)} | hết hạn {_safe_text(contract.ngay_het_han)}'
        for contract in expiring_contract_records
    ]
    customer_lines = [
        f'- {_customer_name(customer)} | công việc mở {customer.tong_cong_viec_mo} | quá hạn {customer.tong_cong_viec_qua_han} | lịch hẹn gần nhất {_safe_text(customer.lich_hen_gan_nhat)}'
        for customer in customers_need_care
    ]

    return f"""
    TỔNG QUAN MODULE QUẢN LÝ CÔNG VIỆC

    Chỉ số chính:
    - Tổng công việc: {total_tasks}
    - Công việc đang mở: {open_tasks_count}
    - Công việc quá hạn: {overdue_tasks_count}
    - Công việc hoàn thành: {done_tasks_count}
    - Tổng tương tác: {total_interactions}
    - Tương tác đang theo dõi: {active_interactions}
    - Tổng hợp đồng: {total_contracts}
    - Hợp đồng đã ký: {signed_contracts}
    - Hợp đồng sắp hết hạn: {expiring_contracts}
    - Khách hàng cần chăm sóc: {customers_need_care_count}

    Danh sách công việc đang mở:
    {chr(10).join(open_task_lines) if open_task_lines else '- Không có'}

    Danh sách công việc quá hạn:
    {chr(10).join(overdue_task_lines) if overdue_task_lines else '- Không có'}

    Tương tác gần đây:
    {chr(10).join(interaction_lines) if interaction_lines else '- Không có'}

    Hợp đồng sắp hết hạn:
    {chr(10).join(contract_lines) if contract_lines else '- Không có'}

    Khách hàng cần chăm sóc:
    {chr(10).join(customer_lines) if customer_lines else '- Không có'}
    """


def _fallback_module_chatbot_response(env, question):
    task_model = env['cong_viec']
    interaction_model = env['tuong_tac_khach_hang']
    contract_model = env['hop_dong_khach_hang']
    customer_model = env['khach_hang']

    open_tasks = task_model.search([('trang_thai', 'not in', ('hoan_thanh', 'huy'))], limit=5, order='han_chot asc, id desc')
    overdue_tasks = task_model.search([('is_qua_han', '=', True)], limit=5, order='han_chot asc, id desc')
    expiring_contracts = contract_model.search([('is_sap_het_han', '=', True)], limit=5, order='ngay_het_han asc, id desc')
    customers_need_care = customer_model.search(['|', ('tong_cong_viec_mo', '>', 0), ('lich_hen_gan_nhat', '!=', False)], limit=5, order='id desc')

    lines = [
        'Tổng quan module quản lý công việc:',
        f'- Tổng công việc: {task_model.search_count([])}',
        f'- Công việc mở: {task_model.search_count([("trang_thai", "not in", ("hoan_thanh", "huy"))])}',
        f'- Công việc quá hạn: {task_model.search_count([("is_qua_han", "=", True)])}',
        f'- Tổng tương tác: {interaction_model.search_count([])}',
        f'- Tổng hợp đồng: {contract_model.search_count([])}',
        f'- Khách hàng cần chăm sóc: {customer_model.search_count(["|", ("tong_cong_viec_mo", ">", 0), ("lich_hen_gan_nhat", "!=", False)])}',
    ]
    if question:
        lines.append(f'Câu hỏi của bạn: {question}')
    if open_tasks:
        lines.append('Các công việc mở đáng chú ý:')
        lines.extend(
            f'- {task.ten_cong_viec} | trạng thái {task.trang_thai} | ưu tiên {task.muc_do_uu_tien} | hạn {_safe_text(task.han_chot)}'
            for task in open_tasks
        )
    if overdue_tasks:
        lines.append('Công việc quá hạn:')
        lines.extend(
            f'- {task.ten_cong_viec} | hạn {_safe_text(task.han_chot)} | khách hàng {_customer_name(task.khach_hang_id)}'
            for task in overdue_tasks
        )
    if expiring_contracts:
        lines.append('Hợp đồng sắp hết hạn:')
        lines.extend(
            f'- {contract.so_hop_dong} | {contract.ten_hop_dong} | hết hạn {_safe_text(contract.ngay_het_han)}'
            for contract in expiring_contracts
        )
    if customers_need_care:
        lines.append('Khách hàng cần chăm sóc:')
        lines.extend(
            f'- {_customer_name(customer)} | công việc mở {customer.tong_cong_viec_mo} | lịch hẹn {_safe_text(customer.lich_hen_gan_nhat)}'
            for customer in customers_need_care
        )
    return '\n'.join(lines)


def _direct_task_chat_response(task, question):
    normalized = _normalize_text(question)
    if not normalized:
        return None

    if any(token in normalized for token in ('tiep theo', 'can lam gi', 'viec can lam', 'buoc tiep', 'next')):
        return _fallback_task_chatbot_response(task, question)

    if 'hop dong' in normalized:
        if not task.hop_dong_ids:
            return f'Công việc `{task.ten_cong_viec}` hiện chưa có hợp đồng liên quan.'
        lines = [
            f'Hợp đồng liên quan đến công việc `{task.ten_cong_viec}`:',
        ]
        for contract in task.hop_dong_ids:
            lines.append(
                f'- {contract.so_hop_dong}: {contract.ten_hop_dong} | trạng thái {contract.trang_thai} | '
                f'giá trị {_safe_text(contract.gia_tri)} | hết hạn {_safe_text(contract.ngay_het_han)}'
            )
        return '\n'.join(lines)

    if any(token in normalized for token in ('han', 'deadline', 'den han', 'qua han')):
        status = 'đang quá hạn' if task.is_qua_han else 'chưa quá hạn'
        return (
            f'Công việc `{task.ten_cong_viec}` có hạn chót {_safe_text(task.han_chot)}, '
            f'trạng thái {task.trang_thai}, mức ưu tiên {task.muc_do_uu_tien} và hiện {status}.'
        )

    if any(token in normalized for token in ('khach hang', 'tuong tac')):
        interaction = task.tuong_tac_id
        interaction_text = 'Không có tương tác nguồn.'
        if interaction:
            interaction_text = (
                f'Tương tác nguồn: {interaction.ma_tuong_tac} | {interaction.ten_tuong_tac} | '
                f'loại {interaction.loai_tuong_tac} | trạng thái {interaction.trang_thai} | '
                f'hẹn tiếp {_safe_text(interaction.ngay_hen_tiep)}.'
            )
        return (
            f'Công việc `{task.ten_cong_viec}` đang gắn với khách hàng `{_customer_name(task.khach_hang_id)}`. '
            + interaction_text
        )

    return None


def _direct_module_chat_response(env, question):
    normalized = _normalize_text(question)
    if not normalized:
        return None

    task_model = env['cong_viec']
    contract_model = env['hop_dong_khach_hang']
    customer_model = env['khach_hang']
    today = fields.Date.context_today(task_model)

    if (
        'cong viec' in normalized
        and (
            'gan deadline' in normalized
            or 'gan han' in normalized
            or 'sap den han' in normalized
            or 'sap toi han' in normalized
        )
    ) or 'deadline' in normalized:
        near_deadline_tasks = task_model.search([
            ('trang_thai', 'not in', ('hoan_thanh', 'huy')),
            ('han_chot', '>=', today),
            ('han_chot', '<=', fields.Date.add(today, days=3)),
        ], order='han_chot asc, id desc', limit=10)
        if not near_deadline_tasks:
            return 'Hiện tại không có công việc mở nào gần deadline trong 3 ngày tới.'
        lines = ['Các công việc gần deadline trong 3 ngày tới:']
        for task in near_deadline_tasks:
            lines.append(
                f'- {task.ten_cong_viec} | hạn {task.han_chot} | ưu tiên {task.muc_do_uu_tien} | '
                f'nhân viên {_employee_name(task.nhan_vien_thuc_hien_id)} | khách hàng {_customer_name(task.khach_hang_id)}'
            )
        return '\n'.join(lines)

    if 'hop dong' in normalized and ('qua han' in normalized or 'het han' in normalized):
        expired_contracts = contract_model.search([
            ('ngay_het_han', '!=', False),
            ('ngay_het_han', '<', today),
            ('trang_thai', '!=', 'huy'),
        ], order='ngay_het_han desc, id desc', limit=10)
        if not expired_contracts:
            return 'Hiện tại không có hợp đồng nào quá hạn.'
        lines = ['Các hợp đồng đã quá hạn:']
        for contract in expired_contracts:
            lines.append(
                f'- {contract.so_hop_dong}: {contract.ten_hop_dong} | khách hàng {_customer_name(contract.khach_hang_id)} | '
                f'hết hạn {contract.ngay_het_han} | trạng thái {contract.trang_thai}'
            )
        return '\n'.join(lines)

    if 'hop dong' in normalized and ('sap het han' in normalized or 'sap toi han' in normalized):
        expiring_contracts = contract_model.search([
            ('is_sap_het_han', '=', True),
        ], order='ngay_het_han asc, id desc', limit=10)
        if not expiring_contracts:
            return 'Hiện tại không có hợp đồng nào sắp hết hạn trong 30 ngày tới.'
        lines = ['Các hợp đồng sắp hết hạn trong 30 ngày tới:']
        for contract in expiring_contracts:
            lines.append(
                f'- {contract.so_hop_dong}: {contract.ten_hop_dong} | khách hàng {_customer_name(contract.khach_hang_id)} | '
                f'hết hạn {contract.ngay_het_han} | trạng thái {contract.trang_thai}'
            )
        return '\n'.join(lines)

    if 'khach hang' in normalized and ('cham soc' in normalized or 'can cham soc' in normalized):
        customers_need_care = customer_model.search([
            '|', ('tong_cong_viec_mo', '>', 0), ('lich_hen_gan_nhat', '!=', False),
        ], order='tong_cong_viec_qua_han desc, tong_cong_viec_mo desc, id desc', limit=10)
        if not customers_need_care:
            return 'Hiện tại chưa có khách hàng nào cần chăm sóc gấp.'
        lines = ['Các khách hàng cần chăm sóc:']
        for customer in customers_need_care:
            lines.append(
                f'- {_customer_name(customer)} | công việc mở {customer.tong_cong_viec_mo} | '
                f'quá hạn {customer.tong_cong_viec_qua_han} | lịch hẹn gần nhất {_safe_text(customer.lich_hen_gan_nhat)}'
            )
        return '\n'.join(lines)

    if 'cong viec' in normalized and 'qua han' in normalized:
        overdue_tasks = task_model.search([
            ('is_qua_han', '=', True),
        ], order='han_chot asc, id desc', limit=10)
        if not overdue_tasks:
            return 'Hiện tại không có công việc nào quá hạn.'
        lines = ['Các công việc đang quá hạn:']
        for task in overdue_tasks:
            lines.append(
                f'- {task.ten_cong_viec} | hạn {task.han_chot} | ưu tiên {task.muc_do_uu_tien} | '
                f'nhân viên {_employee_name(task.nhan_vien_thuc_hien_id)}'
            )
        return '\n'.join(lines)

    return None
