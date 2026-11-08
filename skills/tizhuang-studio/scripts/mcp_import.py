"""Validate question results from an Agent's authenticated Tizhuang MCP client.

Authentication stays with the client. This module never connects to MCP or stores
credentials; auth_mode is provenance supplied by the Agent, not proof of identity.
"""
import copy
import json
import re

MAX_BYTES = 2 * 1024 * 1024
TEXT_FIELDS = ('title', 'title_html', 'answer', 'answer_html', 'analysis', 'analysis_html',
               'question_type', 'knowledges', 'source', 'area')
SOLUTION_FIELDS = ('answer', 'answer_html', 'analysis', 'analysis_html')

def unpack(payload, tool):
    if tool not in ('search_questions', 'get_question'):
        raise ValueError('只能保存 search_questions 或 get_question 的题目结果。')
    # Refuse accidental credential exports, even in otherwise unused metadata.
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded.encode('utf-8')) > MAX_BYTES:
        raise ValueError('MCP 结果超过 2 MB，请按批保存已有结果，不要重新取题。')
    if re.search(r'(?:qsk_|tzo_[ar]_)[A-Za-z0-9_-]{16,}', encoded):
        raise ValueError('结果中疑似包含凭据；请只传题目工具结果，不传认证信息。')
    def check(value, depth=0):
        if depth > 16: raise ValueError('MCP 结果嵌套过深。')
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower().replace('-', '_') in ('authorization', 'x_api_key', 'api_key', 'access_token', 'refresh_token', 'client_secret'):
                    raise ValueError('不要向工作台传入认证字段。')
                check(item, depth+1)
        elif isinstance(value, list):
            for item in value: check(item, depth+1)
    check(payload)
    data = payload
    for _ in range(5):
        if not isinstance(data, dict) or data.get('isError') or 'error' in data:
            raise ValueError('MCP 返回失败或非题目数据，未保存；请在 Agent 中检查连接或额度。')
        if 'jsonrpc' in data:
            data = data.get('result'); continue
        if 'structuredContent' in data:
            data = data['structuredContent']; continue
        if 'content' in data and 'data' not in data:
            blocks = data['content']
            if not isinstance(blocks, list): raise ValueError('MCP 文本结果格式无效。')
            texts = [b.get('text') for b in blocks if isinstance(b, dict) and b.get('type') == 'text']
            if len(texts) != 1 or not isinstance(texts[0], str):
                raise ValueError('请传完整结构化结果，或唯一的 JSON 文本结果。')
            try: data = json.loads(texts[0])
            except (ValueError, TypeError): raise ValueError('MCP 文本不是完整 JSON；不能导入摘要或截断结果。') from None
            check(data); continue
        break
    if not isinstance(data, dict) or data.get('isError') or 'error' in data:
        raise ValueError('MCP 结果不是成功的题目响应。')
    result = data.get('data')
    if not isinstance(result, dict): raise ValueError('缺少题庄 MCP 的 data 对象。')
    rows = result.get('items') if tool == 'search_questions' else [result]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('结果须包含 1–100 道题目；空结果无需保存。')
    return rows

def clean_question(raw, scope, depth=0):
    if not isinstance(raw, dict) or depth > 6:
        raise ValueError('题目结构不完整或子题层级过深。')
    q = {'_solutions_returned': any(field in raw for field in SOLUTION_FIELDS)}
    if depth == 0:
        ident = raw.get('id')
        if not re.fullmatch(r'[1-9][0-9]{0,19}', str(ident)):
            raise ValueError('MCP 题目缺少有效网站题号。')
        if str(raw.get('subject_id')) != str(scope['subject_id']):
            raise ValueError('题目学科与此次保存范围不一致，整批未保存。')
        if raw.get('phase_id') is not None and str(raw['phase_id']) != str(scope['phase_id']):
            raise ValueError('题目学段与此次保存范围不一致，整批未保存。')
        q.update(id=str(ident), subject_id=scope['subject_id'])
    for field in TEXT_FIELDS:
        value = raw.get(field)
        if value is not None:
            if not isinstance(value, str): raise ValueError('题目文本字段格式无效。')
            q[field] = value
    if not (q.get('title_html') or q.get('title')):
        raise ValueError('题目缺少题干，不能导入摘要。')
    for field in ('options', 'options_html'):
        options = raw.get(field)
        if options is not None:
            if not isinstance(options, dict) or any(not isinstance(v, str) for v in options.values()):
                raise ValueError('题目选项格式无效。')
            q[field] = copy.deepcopy(options)
    for field in ('difficulty', 'year'):
        if raw.get(field) is not None:
            if not isinstance(raw[field], (str, int, float)) or isinstance(raw[field], bool):
                raise ValueError('题目属性格式无效。')
            q[field] = raw[field]
    children = raw.get('subquestions') or []
    if not isinstance(children, list) or len(children) > 100:
        raise ValueError('子题格式无效。')
    q['subquestions'] = [clean_question(child, scope, depth+1) for child in children]
    return q

def has_solutions(raw):
    return raw.get('_solutions_returned', False) or any(has_solutions(c) for c in raw.get('subquestions', []))

def validate(body, scope):
    mode = body.get('auth_mode')
    if mode not in ('oauth', 'api_key'): raise ValueError('请指定 MCP 接入方式 oauth 或 api_key，不传凭据。')
    if not isinstance(body.get('add_to_basket', False), bool): raise ValueError('add_to_basket 必须为布尔值。')
    rows = unpack(body.get('result'), body.get('tool'))
    unique = {}
    for row in rows:
        q = clean_question(row, scope)
        if q['id'] in unique and unique[q['id']] != q:
            raise ValueError('同批同题号内容不一致，整批未保存。')
        unique[q['id']] = q
    return list(unique.values())
