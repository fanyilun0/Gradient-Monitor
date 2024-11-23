# API配置
API_URL = "https://api.gradient.network/api/sentrynode/list"
PROFILE_API_URL = "https://api.gradient.network/api/user/profile"

# Token配置示例
# TOKENS_CONFIG = [
#     {
#         'name': 'Token1',  # token标识名称
#         'token': 'your_token_1',
#         'previous_state': {}  # 用于存储上一次状态
#     },
#     {
#         'name': 'Token2',
#         'token': 'your_token_2',
#         'previous_state': {}
#     },
#     # 可以添加更多token配置...
# ]
# Webhook配置
WEBHOOK_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='

# 代理配置
PROXY_URL = 'http://localhost:7890'
USE_PROXY = False
ALWAYS_NOTIFY = True
SHOW_DETAIL = True
# 时间配置
INTERVAL = 36000  # 10小时检查一次
TIME_OFFSET = 6  
