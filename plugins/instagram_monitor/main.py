"""
Instagram 监控插件 — 无需登录，通过 i.instagram.com 公开 API 获取帖子

命令:
  /ins 订阅    — 订阅自动推送
  /ins 取消    — 取消订阅
  /ins 状态    — 查看状态
  /ins 最新 [N]  — 获取 Winter 最新 N 条帖子 (默认 3)
"""

import asyncio, json, re
from datetime import datetime, timezone
from pathlib import Path

import requests
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.event.filter import command
from astrbot.api.message_components import Image as MsgImage
from astrbot.api.platform import MessageType
from astrbot.api.star import Context, Star, register

API_BASE = "https://i.instagram.com/api/v1"
UA = "Instagram 269.0.0.18.75 Android"
DEFAULT_ACCOUNTS = ["imwinter"]
INTERVAL = 60 * 30
DATA_DIR = Path(__file__).parent / "data"

# ── 工具 ──────────────────────────────────────────────
def _load(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except: pass
    return default

def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

class Store:
    def __init__(self, d):
        d.mkdir(parents=True, exist_ok=True)
        self._s = d / "subs.json"
        self._c = d / "cfg.json"
    @property
    def subs(self): return _load(self._s, {})
    def add_sub(self, k, v): s = self.subs; s[k] = v; _save(self._s, s)
    def del_sub(self, k): s = self.subs; s.pop(k, None); _save(self._s, s)
    @property
    def cfg(self):
        d = {"accounts": DEFAULT_ACCOUNTS, "interval": INTERVAL, "proxy": "", "last_check": None}
        c = _load(self._c, {})
        for k, v in d.items(): c.setdefault(k, v)
        return c
    def update_cfg(self, **kw): c = self.cfg; c.update(kw); _save(self._c, c)

# ── Instagram API ─────────────────────────────────────
class IG:
    def __init__(self, store: Store):
        self.store = store
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA})
        self._profile_cache: dict[str, dict] = {}
        self._proxy_set = False

    def _ensure_proxy(self):
        """每次请求前检查代理配置，避免插件加载时 cfg.json 还不存在导致代理为空"""
        if not self._proxy_set:
            p = self.store.cfg.get("proxy", "")
            if p:
                self.s.proxies = {"http": p, "https": p}
            self._proxy_set = True

    def _profile(self, username: str) -> dict:
        """获取用户完整信息（含最近帖子），结果缓存。web_profile_info 仍无需登录。"""
        self._ensure_proxy()
        if username in self._profile_cache:
            return self._profile_cache[username]
        try:
            r = self.s.get(f"{API_BASE}/users/web_profile_info/?username={username}", timeout=15)
            if r.status_code == 200:
                user = r.json()["data"]["user"]
                self._profile_cache[username] = user
                return user
        except Exception as e:
            print(f"[IG] profile error {username}: {e}")
        return {}

    def _uid(self, username: str) -> str:
        p = self._profile(username)
        return p.get("id", "")

    def posts(self, username: str, count=3) -> list[dict]:
        user = self._profile(username)
        if not user:
            return []

        media = user.get("edge_owner_to_timeline_media", {})
        edges = media.get("edges", [])

        out = []
        for edge in edges[:count]:
            node = edge.get("node", {})
            # 文案
            cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            cap_text = cap_edges[0]["node"]["text"] if cap_edges else ""
            # 图片
            images = []
            children = node.get("edge_sidecar_to_children", {}).get("edges", [])
            if children:
                for c in children:
                    url = c.get("node", {}).get("display_url", "")
                    if url:
                        images.append(url)
            else:
                url = node.get("display_url", "")
                if url:
                    images.append(url)
            out.append({
                "code": node.get("shortcode", ""),
                "caption": cap_text,
                "url": f"https://instagram.com/p/{node.get('shortcode', '')}/",
                "images": images,
                "account": username,
                "time": node.get("taken_at_timestamp", 0),
            })
        return out

# ── 插件主体 ──────────────────────────────────────────
@register("instagram_monitor", "Winter Bot", "Instagram 监控推送(免登录)", "2.0.0")
class InstagramMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.store = Store(DATA_DIR)
        self.ig = IG(self.store)
        self._seen: dict[str, set] = {}
        self._running = True
        asyncio.ensure_future(self._loop())

    async def _loop(self):
        await asyncio.sleep(8)
        cfg = self.store.cfg
        print(f"[IG] v2.0 started. proxy={'YES' if cfg['proxy'] else 'NO'}, accounts={cfg['accounts']}, interval={cfg['interval']}s")
        while self._running:
            try: await self._check()
            except Exception as e: print(f"[IG] check err: {e}")
            await asyncio.sleep(cfg["interval"])

    async def _check(self):
        subs = self.store.subs
        if not subs: return
        for acc in self.store.cfg["accounts"]:
            ps = self.ig.posts(acc, 3)
            if not ps: continue
            seen = self._seen.setdefault(acc, set())
            new = [p for p in ps if p["code"] not in seen]
            if not new: continue
            plat = self._qq()
            if not plat: return
            for _, sub in subs.items():
                for p in new:
                    await self._push(plat, sub, p)
                    await asyncio.sleep(2)
            for p in new: seen.add(p["code"])

    async def _push(self, plat, sub, post):
        from astrbot.core.platform.astr_message_event import MessageSesion
        s = MessageSesion(session_id=sub["session_id"], platform_name=sub["platform_name"], message_type=MessageType.FRIEND_MESSAGE)
        ts = datetime.fromtimestamp(post["time"], tz=timezone.utc).strftime("%Y-%m-%d")
        cap = post["caption"][:300]
        cn = await self._translate(cap)
        if cn and cn != cap:
            cap = f"{cap}\n\n🌐 {cn}"
        text = f"📸 @{post['account']} ({ts})\n\n{cap}"
        await plat.send_by_session(s, MessageChain().message(text))
        for url in post["images"]:
            try: await plat.send_by_session(s, MessageChain().message(MsgImage.fromURL(url)))
            except: pass
        await plat.send_by_session(s, MessageChain().message(f"🔗 {post['url']}"))

    async def _reply(self, event, posts):
        if not posts:
            yield event.plain_result("未找到帖子。")
            return
        for p in posts:
            ts = datetime.fromtimestamp(p["time"], tz=timezone.utc).strftime("%Y-%m-%d")
            cap = p["caption"][:300]
            cn = await self._translate(cap)
            if cn and cn != cap:
                cap = f"{cap}\n\n🌐 {cn}"
            yield event.plain_result(f"📸 @{p['account']} ({ts})\n\n{cap}")

            # 逐张发送全部图片
            for url in p["images"]:
                try:
                    yield event.make_result().url_image(url)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            yield event.plain_result(f"🔗 {p['url']}")
            await asyncio.sleep(0.5)

    def _qq(self):
        for p in self.context.platform_manager.platform_insts:
            if p.meta().name == "qq_official": return p

    def _is_cn(self, text: str) -> bool:
        """检测文本是否含中文"""
        for ch in text[:50]:
            if '一' <= ch <= '鿿':
                return True
        return False

    async def _translate(self, text: str) -> str:
        """用 LLM 翻译非中文文本"""
        if self._is_cn(text) or not text.strip():
            return text
        try:
            prov = self.context.get_using_provider()
            if not prov:
                return text
            resp = await prov.text_chat(
                prompt=f"将以下内容翻译成简体中文，只输出译文，不要解释：\n\n{text}",
                system_prompt="你是一个翻译助手。只输出译文。",
            )
            return resp.completion_text.strip() or text
        except Exception:
            return text

    def _parse_count(self, text, default=3):
        try:
            for w in text.split():
                n = int(w)
                if 1 <= n <= 20: return n
        except: pass
        return default

    # ── 命令 ──
    @command("ins 订阅")
    async def cmd_sub(self, e: AstrMessageEvent):
        k = f"{e.get_platform_id()}:{e.session_id}"
        if k in self.store.subs:
            yield e.plain_result("✅ 已订阅~")
            return
        self.store.add_sub(k, {"session_id": e.session_id, "platform_name": e.get_platform_id(), "time": datetime.now(timezone.utc).isoformat()})
        yield e.plain_result(f"✅ 订阅成功！({', '.join(self.store.cfg['accounts'])})")

    @command("ins 取消")
    async def cmd_unsub(self, e: AstrMessageEvent):
        k = f"{e.get_platform_id()}:{e.session_id}"
        if k not in self.store.subs: yield e.plain_result("还没订阅~"); return
        self.store.del_sub(k); yield e.plain_result("已取消。")

    @command("ins 状态")
    async def cmd_status(self, e: AstrMessageEvent):
        c = self.store.cfg
        s = self.store.subs
        yield e.plain_result(
            f"📊 IG v2.0 (免登录)\n账号: {', '.join(c['accounts'])}\n"
            f"代理: {'✅' if c['proxy'] else '❌ 未设'}\n订阅: {len(s)}人\n间隔: {c['interval']//60}分钟"
        )

    @command("ins 最新")
    async def cmd_latest(self, e: AstrMessageEvent, count: int = 3):
        n = count if count and 1 <= count <= 20 else self._parse_count(e.message_str, 3)
        acc = self.store.cfg["accounts"][0]
        yield e.plain_result(f"🔍 @{acc} 最新 {n} 条...")
        ps = self.ig.posts(acc, n)
        async for r in self._reply(e, ps): yield r
