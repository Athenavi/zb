from user_agents import parse


def user_agent_info(user_agent):
    # 解析 User-Agent 字符串
    user_agent_parsed = parse(user_agent)

    # 初始化值得转换后的 User-Agent 描述
    converted_ua = "Unknown Device"

    # 根据解析结果构造转换后的描述
    if user_agent_parsed.is_pc:
        converted_ua = f"PC / {user_agent_parsed.browser.family} / {user_agent_parsed.os.family}"
    elif user_agent_parsed.is_mobile:
        converted_ua = f"Mobile / {user_agent_parsed.device.family} / {user_agent_parsed.os.family}"
    elif user_agent_parsed.is_tablet:
        converted_ua = f"Tablet / {user_agent_parsed.device.family} / {user_agent_parsed.os.family}"

    return converted_ua


def get_client_ip(req):
    if 'X-Forwarded-For' in req.headers:
        ip = req.headers['X-Forwarded-For'].split(',')[0].strip()
    elif 'X-Real-IP' in req.headers:
        ip = req.headers['X-Real-IP'].strip()
    else:
        ip = req.remote_addr

    return ip


def anonymize_ip_address(ip):
    # 将 IP 地址分割成四个部分
    parts = ip.split('.')
    if len(parts) == 4:
        # 隐藏最后两个部分
        masked_ip = f"{parts[0]}.{parts[1]}.xxx.xxx"
        return masked_ip
    return ip
