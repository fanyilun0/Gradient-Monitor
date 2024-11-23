import asyncio
import aiohttp
from datetime import datetime, timedelta
import copy
import random
import json
import zstandard as zstd  # 需要先安装：pip install zstandard

previous_state = {}

# 导入配置
from config import (
    API_URL,  # 节点列表API
    PROFILE_API_URL,  # 个人资料API
    TOKENS_CONFIG,
    WEBHOOK_URL, 
    PROXY_URL, 
    USE_PROXY, 
    INTERVAL, 
    TIME_OFFSET,
    ALWAYS_NOTIFY,
    SHOW_DETAIL
)

# 新增：随机延迟函数
async def random_delay():
    """生成随机延迟时间（3-10秒）"""
    delay = random.uniform(3, 10)
    print(f"等待 {delay:.2f} 秒...")
    await asyncio.sleep(delay)

async def monitor_single_token(session, token_config, webhook_url, use_proxy, proxy_url):
    """监控单个token的节点状态"""
    try:
        await random_delay()
        
        print(f"\n=== 检查Token: {token_config['name']} ===")
        
        # 初始化变量
        profile_data = None
        current_state = None
        
        # 获取节点数据
        current_state = await fetch_nodes_data(
            session=session,
            api_url=API_URL,
            api_token=token_config['token']
        )
        
        if not current_state:
            print(f"获取节点数据失败，跳过此token: {token_config['name']}")
            return
            
        # 获取个人资料数据
        try:
            profile_data = await fetch_profile_data(
                session=session,
                api_token=token_config['token']
            )
        except Exception as e:
            print(f"获取个人资料失败: {str(e)}")
            return
            
        if current_state and profile_data:
            # 检查在线节点数
            online_nodes = sum(1 for node in current_state if node['connect'])
            expected_online = profile_data.get('node', {}).get('sentryActive', 0)
            
            # 判断是否需要推送消息
            should_notify = (
                ALWAYS_NOTIFY or
                online_nodes < expected_online
            )
            
            if should_notify:
                message = build_status_message(
                    current_state, 
                    profile_data, 
                    SHOW_DETAIL,
                    online_nodes,
                    expected_online
                )
                if message:
                    await send_message_async(webhook_url, message, use_proxy, proxy_url)
            
            token_config['previous_state'] = copy.deepcopy(current_state)
            
    except Exception as e:
        print(f"监控Token {token_config['name']} 时出错: {str(e)}")

def get_random_user_agent():
    """获取随机User-Agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    return random.choice(user_agents)


async def send_message_async(webhook_url, message_content, use_proxy, proxy_url):
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": message_content
        }
    }
    
    proxy = proxy_url if use_proxy else None
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload, headers=headers, proxy=proxy) as response:
            if response.status == 200:
                print("Message sent successfully!")
            else:
                print(f"Failed to send message: {response.status}, {await response.text()}")


async def fetch_nodes_data(session, api_url, api_token):
    """获取节点数据"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "authorization": f"Bearer {api_token}",
        "content-type": "application/json",
        "user-agent": get_random_user_agent(),
        "origin": "https://app.gradient.network",
        "referer": "https://app.gradient.network/",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site"
    }
    
    payload = {
        "active": True,
        "banned": False,
        "direction": 0,
        "field": "active",
        "hide": 0,
        "page": 1,
        "size": 12
    }

    print(f"\n--- 请求详情 ---")
    print(f"API URL: {api_url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        async with session.post(api_url, headers=headers, json=payload, timeout=30, ssl=False) as response:
            print(f"\n--- 响应详情 ---")
            print(f"状态码: {response.status}")
            
            response_text = await response.text()
            print(f"响应内容: {response_text[:500]}...")  # 只打印前500个字符
            
            if response.status == 403:
                print(f"Token认证失败，请检查token是否有效: {api_token}")
                return None
            elif response.status == 200:
                data = await response.json()
                print(f"\n--- 解析结果 ---")
                print(f"响应代码: {data.get('code')}")
                print(f"响应消息: {data.get('message', '无')}")
                
                if data.get('code') == 200:
                    result_data = data.get('data', [])
                    print(f"获取到的节点数量: {len(result_data)}")
                    return result_data
                else:
                    print(f"API返回错误码: {data.get('code')}, 消息: {data.get('message', '未知错误')}")
                    return None
            else:
                print(f"API请求失败: {response.status}, 错误信息: {response_text}")
                return None
                
    except asyncio.TimeoutError:
        print("请求超时")
        return None
    except Exception as e:
        print(f"获取数据失败: {str(e)}")
        print(f"异常类型: {type(e).__name__}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return None

async def fetch_profile_data(session, api_token):
    """获取用户资料数据"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
        "authorization": f"Bearer {api_token}",
        "content-type": "application/json",
        "origin": "https://app.gradient.network",
        "referer": "https://app.gradient.network/",
        "user-agent": get_random_user_agent()
    }
    
    try:
        async with session.post(PROFILE_API_URL, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('code') == 200:
                    return data.get('data', {})  # 返回 data 字段的内容
                else:
                    raise Exception(f"API返回错误: {data}")
            else:
                error_text = await response.text()
                raise Exception(f"获取个人资料失败: {response.status}, 错误信息: {error_text}")
    except Exception as e:
        print(f"获取个人资料失败: {str(e)}")
        raise

def compare_states(previous, current):
    """比较两个状态的差异"""
    changes = []
    
    for node in current:
        node_id = node['_id']
        prev_node = next((n for n in previous if n['_id'] == node_id), None)
        
        if not prev_node:
            changes.append(f"新增节点: {node['pubKey']}")
            continue
            
        # 检查连接状态变化
        if node['isConnected'] != prev_node['isConnected']:
            status = "上线" if node['isConnected'] else "离线"
            changes.append(f"节点 {node['pubKey']} {status}")
            
        # 检查奖励变化
        if node['totalReward'] != prev_node['totalReward']:
            reward_diff = node['totalReward'] - prev_node['totalReward']
            changes.append(f"节点 {node['pubKey']} 总奖励变化: +{reward_diff}")
            
        if node['todayReward'] != prev_node['todayReward']:
            reward_diff = node['todayReward'] - prev_node['todayReward']
            changes.append(f"节点 {node['pubKey']} 今日奖励变化: +{reward_diff}")
            
        # 检查sessions变化
        if len(node['sessions']) != len(prev_node['sessions']):
            changes.append(f"节点 {node['pubKey']} sessions数量变化: {len(prev_node['sessions'])} -> {len(node['sessions'])}")
    
    return changes

def build_message(changes):
    """构建消息内容"""
    if not changes:
        return None
        
    adjusted_time = datetime.now() + timedelta(hours=TIME_OFFSET)
    timestamp = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
    
    message_lines = [
        "【节点状态变化监控】",
        f"时间: {timestamp}\n",
        "变化详情:"
    ]
    
    for change in changes:
        message_lines.append(f"- {change}")
        
    return "\n".join(message_lines)

async def monitor_nodes(interval, webhook_url, use_proxy, proxy_url, always_notify=False):
    """监控节点状态"""
    while True:
        try:
            # 为每个token创建独立的监控任务，每个任务使用独立的session
            tasks = []
            for token_config in TOKENS_CONFIG:
                task = monitor_token_with_session(
                    token_config=token_config,
                    webhook_url=webhook_url,
                    use_proxy=use_proxy,
                    proxy_url=proxy_url
                )
                tasks.append(task)
            
            # 并发执行所有token的监控任务
            await asyncio.gather(*tasks)
            
        except Exception as e:
            print(f"监控过程出错: {str(e)}")
            await asyncio.sleep(5)
            continue
            
        await asyncio.sleep(interval)

async def monitor_token_with_session(token_config, webhook_url, use_proxy, proxy_url):
    """为每个token创建独立的session进行监控"""
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        await monitor_single_token(
            session=session,
            token_config=token_config,
            webhook_url=webhook_url,
            use_proxy=use_proxy,
            proxy_url=proxy_url
        )

def format_point(point_value):
    """将积分格式化为 x,xxx.x pt 格式"""
    point = float(point_value) / 100000  # 转换为pt单位
    return f"{point:,.1f} pt"

def build_status_message(current_state, profile_data, show_detail, online_nodes, expected_online):
    """构建状态消息"""
    adjusted_time = datetime.now() + timedelta(hours=TIME_OFFSET)
    timestamp = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
    
    total_today = sum(node['today'] for node in current_state)
    
    # 获取积分信息
    point_data = profile_data.get('point', {})
    total_point = format_point(point_data.get('total', 0))
    balance_point = format_point(point_data.get('balance', 0))
    referral_point = format_point(point_data.get('referral', 0))
    
    # 获取节点信息
    node_data = profile_data.get('node', {})
    
    # 添加节点状态警告
    status_emoji = "✅" if online_nodes >= expected_online else "⚠️"
    
    message_lines = [
        f"{status_emoji} 【Gradient状态报告】",
        f"时间: {timestamp}\n",
        f"💎 积分统计:",
        f"  • 账号: {profile_data.get('name')}",
        f"  • 总积分: {total_point}",
        f"  • 可用积分: {balance_point}",
        f"  • 推荐奖励: {referral_point}",
        f"\n🖥️ 节点统计:",
        f"  • 预期活跃: {expected_online}",
        f"  • 在线节点: {online_nodes}",
        f"  • 今日积分: {format_point(total_today)}"
    ]
    
    if show_detail:
        message_lines.extend(["\n📝 节点详情:"])
        for node in current_state:
            status_emoji = "✅" if node['connect'] else "❌"
            message_lines.extend([
                f"  • {node['name']} {status_emoji}",
                f"    积分: {format_point(node['point'])} / 今日: {format_point(node['today'])}",
                f"    延迟: {node['latency']}ms / 位置: {node['location']['country']}-{node['location']['place']}"
            ])
    
    return "\n".join(message_lines)

if __name__ == "__main__":
    asyncio.run(monitor_nodes(
        interval=INTERVAL,
        webhook_url=WEBHOOK_URL,
        use_proxy=USE_PROXY,
        proxy_url=PROXY_URL,
        always_notify=ALWAYS_NOTIFY  # 添加这个参数来启用始终通知
    ))
