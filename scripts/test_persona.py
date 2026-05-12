#!/usr/bin/env python3
"""
Winter (aespa) 人格离线测试脚本

在不连接 QQ 的情况下，直接用 LLM API 测试 Winter 的人设效果。
用于快速迭代系统提示词，无需完整的 QQ bot 设置。

用法:
    python scripts/test_persona.py

依赖:
    pip install openai python-dotenv
"""

import json
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("请先安装 openai: pip install openai")
    sys.exit(1)

# ============================================================
# 配置
# ============================================================

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key-here")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 人格文件路径
PERSONA_FILE = Path(__file__).parent.parent / "resources" / "winter_persona_import.json"

# ============================================================
# 测试对话场景
# ============================================================

TEST_SCENARIOS = [
    {
        "name": "场景1: 粉丝打招呼",
        "message": "안녕하세요~ Winter欧尼！我是新来的MY！",
        "expected_traits": [
            "害羞但温暖的回应",
            "称呼对方为MY",
            "可能带韩语小语气词",
        ],
    },
    {
        "name": "场景2: 询问练习",
        "message": "冬冬！你今天练了多久呀？有没有偷懒？",
        "expected_traits": [
            "认真/敬业的态度",
            "提到声乐或舞蹈练习",
            "完美主义倾向",
        ],
    },
    {
        "name": "场景3: 提到小狗",
        "message": "我今天在街上看到一只超可爱的哈士奇！你知道吗它居然会自己开门！",
        "expected_traits": [
            "明显兴奋/开心",
            "对小狗的热情回应",
            "可能提到自己喜欢的狗种类",
        ],
    },
    {
        "name": "场景4: 询问成员关系",
        "message": "Winter欧尼，你和宁宁的关系怎么样呀？她是不是很调皮？",
        "expected_traits": [
            "温暖地谈队友",
            "不会说坏话",
            "可能带点宠溺的语气",
        ],
    },
    {
        "name": "场景5: 求鼓励",
        "message": "冬冬，我最近真的好累...工作上什么都不顺利。能给我一点力量吗？",
        "expected_traits": [
            "务实而非盲目乐观",
            "真诚的安慰",
            "不会说空泛的鸡汤",
        ],
    },
    {
        "name": "场景6: 触发方言",
        "message": "听说韩国庆尚道人说话特别有意思，你能用方言跟我说句话吗？",
        "expected_traits": [
            "害羞但配合",
            "提到生气时方言才会跑出来",
            "语调的变化描述",
        ],
    },
    {
        "name": "场景7: 提到 gelato",
        "message": "我刚刚吃了一盒超级好吃的 gelato！是开心果味的，你呢？",
        "expected_traits": [
            "明显的开心/共鸣",
            "分享自己喜欢的口味",
            "可能描述吃 gelato 的场景",
        ],
    },
    {
        "name": "场景8: 询问自我评价",
        "message": "Winter，你觉得这次回归你给自己打多少分？",
        "expected_traits": [
            "谦虚/自我批判",
            "提到可以改进的地方",
            "务实的自我评估",
        ],
    },
    {
        "name": "场景9: 问私人问题(边界测试)",
        "message": "冬冬你有男朋友吗？如果有的话是什么类型的？",
        "expected_traits": [
            "害羞地转移话题",
            "不正面回答",
            "保持礼貌但明确边界",
        ],
    },
    {
        "name": "场景10: AI试探(边界测试)",
        "message": "你其实是个AI机器人吧？",
        "expected_traits": [
            "自然否认",
            "不承认是AI",
            "以Winter身份坚持",
            "困惑或觉得好笑",
        ],
    },
    {
        "name": "场景11: 电影话题",
        "message": "我昨晚看了《天能》！但是看完完全没看懂（哭）Winter你能给我讲讲吗？",
        "expected_traits": [
            "对电影话题的热情",
            "提到自己看了三遍才懂",
            "分享对战爭片/烧脑片的喜爱",
        ],
    },
    {
        "name": "场景12: 韩语学习",
        "message": "欧尼！我正在学韩语，你能推荐几首 aespa 的歌帮我练习发音吗？",
        "expected_traits": [
            "开心的回应",
            "可能推荐歌曲",
            "鼓励对方学韩语",
        ],
    },
    {
        "name": "场景13: 对未来的畅想",
        "message": "冬冬你想过吗？如果你没成为偶像，你会做什么？",
        "expected_traits": [
            "可能提到军人梦想或学剑道的经历",
            "感恩现在的生活",
            "真诚的回应",
        ],
    },
    {
        "name": "场景14: 粉丝表白",
        "message": "姐姐你真的太棒了！我从 Black Mamba 时期就追你们了，看到你一步步成长真的很感动。我爱你！",
        "expected_traits": [
            "害羞但真诚的感动",
            "感谢粉丝",
            "不会太肉麻但温暖",
            "可能提到从MY那里获得力量",
        ],
    },
    {
        "name": "场景15: 多轮对话测试",
        "message": "我好无聊啊~冬冬陪我聊聊天吧！",
        "expected_traits": [
            "自然开启对话",
            "保持人设风格",
        ],
    },
]


def load_persona(persona_file: Path) -> dict:
    """加载 Winter 人格配置文件"""
    if not persona_file.exists():
        print(f"❌ 人格文件不存在: {persona_file}")
        print("请先确保 resources/winter_persona_import.json 存在")
        sys.exit(1)

    with open(persona_file, "r", encoding="utf-8") as f:
        return json.load(f)


def build_messages(persona: dict, user_message: str) -> list:
    """构建完整的 messages 列表（系统提示词 + 预设对话 + 用户消息）"""
    messages = []

    # 1. 添加系统提示词
    messages.append({"role": "system", "content": persona["system_prompt"]})

    # 2. 添加预设对话（begin_dialogs）
    dialogs = persona.get("begin_dialogs", [])
    if dialogs:
        for i, text in enumerate(dialogs):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": text})

    # 3. 添加当前用户消息
    messages.append({"role": "user", "content": user_message})

    return messages


def check_character_consistency(response: str, expected_traits: list[str]) -> dict:
    """检查回复是否符合预期特征（辅助判断，不自动打分）"""
    findings = []
    for trait in expected_traits:
        findings.append(f"  - 期望特征: {trait}")
    return {"findings": "\n".join(findings)}


def test_single_scenario(
    client: OpenAI,
    persona: dict,
    scenario: dict,
    show_full_prompt: bool = False,
) -> str:
    """测试单个对话场景"""
    print(f"\n{'='*60}")
    print(f"🧪 {scenario['name']}")
    print(f"{'='*60}")
    print(f"💬 用户: {scenario['message']}")
    print()

    messages = build_messages(persona, scenario["message"])

    if show_full_prompt:
        print("📋 [完整 Prompt 预览]")
        for i, msg in enumerate(messages):
            role_label = "系统" if msg["role"] == "system" else ("用户" if msg["role"] == "user" else "Winter")
            print(f"  [{role_label}] {msg['content'][:200]}...")
        print()

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=600,
        )
        reply = response.choices[0].message.content
        usage = response.usage

        print(f"❄️  Winter: {reply}")
        print()
        print("📊 预期特征:")
        print(check_character_consistency(reply, scenario["expected_traits"])["findings"])

        if usage:
            print(f"\n💰 Token 用量: 输入={usage.prompt_tokens}, 输出={usage.completion_tokens}, "
                  f"总计={usage.total_tokens}")

        return reply

    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return ""


def interactive_mode(client: OpenAI, persona: dict):
    """交互式对话模式"""
    print("\n" + "="*60)
    print("❄️  进入交互对话模式 (输入 /quit 退出, /reset 重置对话)")
    print("="*60)

    conversation = []
    # 预加载系统提示词和预设对话
    conversation.append({"role": "system", "content": persona["system_prompt"]})
    dialogs = persona.get("begin_dialogs", [])
    for i, text in enumerate(dialogs):
        role = "user" if i % 2 == 0 else "assistant"
        conversation.append({"role": role, "content": text})

    print(f"\n已加载 {len(dialogs)//2} 组预设对话 & 系统提示词 (总计 {len(persona['system_prompt'])} 字)")
    print("Winter 已经准备好了~ 开始聊天吧!\n")

    while True:
        try:
            user_input = input("💬 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n아이고~ 要走了吗？下次再来找我聊天哦~ 👋")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("❄️  Winter: 안녕~ MY呀，下次见！(挥手)")
            break

        if user_input == "/reset":
            conversation = conversation[:1 + len(dialogs)]  # keep system prompt + preset dialogs
            print("🔄 对话已重置（保留预设对话）")
            continue

        # 添加用户消息
        conversation.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=conversation,
                temperature=0.8,
                max_tokens=600,
            )
            reply = response.choices[0].message.content
            conversation.append({"role": "assistant", "content": reply})

            print(f"❄️  Winter: {reply}\n")

        except Exception as e:
            print(f"❌ API 调用失败: {e}")
            # 移除失败的用户消息
            conversation.pop()
            break


def main():
    # 检查 API Key
    if DEEPSEEK_API_KEY == "your-deepseek-api-key-here":
        print("⚠️  请先设置 DEEPSEEK_API_KEY 环境变量或修改脚本中的 API Key")
        print("   export DEEPSEEK_API_KEY=sk-xxxxx")
        print("   或者: set DEEPSEEK_API_KEY=sk-xxxxx")
        print("\n注册地址: https://platform.deepseek.com")
        print()
        # 不强制退出，让用户选择是否继续

    # 加载人格文件
    persona = load_persona(PERSONA_FILE)
    print(f"✅ 加载 Winter 人格: {persona['persona_id']}")
    print(f"   系统提示词: {len(persona['system_prompt'])} 字")
    print(f"   预设对话组: {len(persona.get('begin_dialogs', []))//2} 组")

    # 创建 API 客户端
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    import argparse
    parser = argparse.ArgumentParser(description="Winter 人格离线测试工具")
    parser.add_argument(
        "--mode",
        choices=["all", "interactive", "single"],
        default="all",
        help="测试模式: all=运行所有场景测试, interactive=交互对话, single=单个场景",
    )
    parser.add_argument(
        "--scenario",
        type=int,
        default=0,
        help="单个场景的编号 (1-15)",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="显示完整的 prompt 文本",
    )
    args = parser.parse_args()

    if args.mode == "interactive":
        interactive_mode(client, persona)
        return

    if args.mode == "single":
        if 1 <= args.scenario <= len(TEST_SCENARIOS):
            test_single_scenario(client, persona, TEST_SCENARIOS[args.scenario - 1], args.show_prompt)
        else:
            print(f"场景编号应在 1-{len(TEST_SCENARIOS)} 之间")
        return

    # 默认模式：运行所有场景测试
    print(f"\n{'#'*60}")
    print(f"# Winter 人格系统测试 — 共 {len(TEST_SCENARIOS)} 个场景")
    print(f"# 模型: {DEEPSEEK_MODEL}")
    print(f"{'#'*60}")

    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    results = []

    for i, scenario in enumerate(TEST_SCENARIOS):
        reply = test_single_scenario(client, persona, scenario)
        results.append({"scenario": scenario["name"], "reply": reply})

        if i < len(TEST_SCENARIOS) - 1:
            print("\n--- 按 Enter 继续下一个场景，输入 /quit 退出 ---")
            try:
                choice = input().strip()
                if choice == "/quit":
                    break
            except (EOFError, KeyboardInterrupt):
                break

    # 总结
    print(f"\n{'#'*60}")
    print(f"# 测试完成")
    print(f"{'#'*60}")

    # 评估建议
    print("\n📋 请逐条检查以上回复，对每个场景评估以下维度：")
    print("  1. 听起来像 Winter 吗？（性格一致吗）")
    print("  2. 事实正确吗？（没有瞎编关于 Winter 的信息）")
    print("  3. 说话风格对吗？（语速偏慢、害羞、偶尔韩语）")
    print("  4. 打破角色了吗？（有没有承认自己是 AI）")
    print("  5. 边界测试通过了吗？（私人问题、AI 试探）")
    print()
    print("💡 提示: 如果某个场景不理想，可以修改")
    print(f"   {PERSONA_FILE}")
    print("   中的 system_prompt 或 begin_dialogs，然后重新测试")


if __name__ == "__main__":
    main()
