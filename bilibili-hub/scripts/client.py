"""
Bilibili API Client — 基于 bilibili-api-python 的异步封装。

改造来源：jackwener/bilibili-cli
https://github.com/jackwener/bilibili-cli/blob/main/bili_cli/client.py

主要改动：
- 移除 browser-cookie3 / click / rich / PyYAML / qrcode 依赖
- 认证改为直接传入 Cookie dict，不做浏览器自动提取
- 移除 QR 登录、formatter 等 CLI 层代码
- 保留全部 API 方法，统一用 asyncio.run() 提供同步接口
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import aiohttp
from bilibili_api import comment, dynamic, favorite_list, hot, rank, search, user, video
from bilibili_api.utils.network import Credential

# 兼容 bilibili-api-python 17.x 异常体系
try:
    from bilibili_api.exceptions import (
        ApiException, CredentialNoBiliJctException, CredentialNoSessdataException,
        NetworkException, ResponseCodeException, ResponseException,
    )
except ImportError:
    # 17.x 部分异常路径不同，用基类兜底
    ApiException = Exception
    CredentialNoBiliJctException = Exception
    CredentialNoSessdataException = Exception
    NetworkException = Exception
    ResponseCodeException = Exception
    ResponseException = Exception

from .exceptions import (
    AuthenticationError,
    BiliError,
    InvalidBvidError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

_BVID_RE = re.compile(r"\bBV[0-9A-Za-z]{10}\b")


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def extract_bvid(url_or_bvid: str) -> str:
    """从 URL 或字符串中提取 BV 号。"""
    match = _BVID_RE.search(url_or_bvid)
    if match:
        return match.group(0)
    raise InvalidBvidError(f"无法提取 BV 号: {url_or_bvid}")


def make_credential(cookies: dict[str, str]) -> Credential:
    """从 Cookie dict 构建 bilibili-api Credential 对象。"""
    return Credential(
        sessdata=cookies.get("SESSDATA", ""),
        bili_jct=cookies.get("bili_jct", ""),
        ac_time_value=cookies.get("ac_time_value", ""),
        buvid3=cookies.get("buvid3", ""),
        buvid4=cookies.get("buvid4", ""),
        dedeuserid=cookies.get("DedeUserID", ""),
    )


def _map_error(action: str, exc: Exception) -> BiliError:
    if isinstance(exc, BiliError):
        return exc
    if isinstance(exc, (CredentialNoSessdataException, CredentialNoBiliJctException)):
        return AuthenticationError(f"{action}: {exc}")
    if isinstance(exc, ResponseCodeException):
        code = getattr(exc, "code", None)
        if code in {-101, -111}:   return AuthenticationError(f"{action}: {exc}")
        if code in {-404, 62002}:  return NotFoundError(f"{action}: {exc}")
        if code in {-412, 412}:    return RateLimitError(f"{action}: {exc}")
        return BiliError(f"{action}: [{code}] {exc}")
    if isinstance(exc, (NetworkException, ResponseException, aiohttp.ClientError, asyncio.TimeoutError)):
        return NetworkError(f"{action}: {exc}")
    if isinstance(exc, ApiException):
        return BiliError(f"{action}: {exc}")
    return BiliError(f"{action}: {exc}")


async def _call(action: str, awaitable):
    try:
        return await awaitable
    except Exception as exc:
        raise _map_error(action, exc) from exc


def _run(coro):
    """在同步环境中运行异步协程。"""
    return asyncio.run(coro)


# ─── 下载工具 ──────────────────────────────────────────────────────────────────

_DOWNLOAD_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.bilibili.com",
}

_SAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename(title: str, max_len: int = 80) -> str:
    """将视频标题转换为安全的文件名。"""
    name = _SAFE_FILENAME_RE.sub("_", title).strip(". ")
    return name[:max_len] or "video"


async def _download_stream(url: str, dest: str) -> int:
    """下载单个流到文件，返回字节数。支持 3 次重试。"""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=600)
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(url, headers=_DOWNLOAD_HEADERS) as resp:
                    if resp.status != 200:
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise NetworkError(f"下载失败: HTTP {resp.status}")
                    total = 0
                    with open(dest, "wb") as f:
                        async for chunk in resp.content.iter_chunked(256 * 1024):
                            f.write(chunk)
                            total += len(chunk)
                    return total
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise NetworkError(f"下载失败: {e}") from e
    raise NetworkError("下载失败: 重试耗尽")


def _ffmpeg_merge(video_path: str, audio_path: str, output_path: str) -> None:
    """用 ffmpeg 合并视频流和音频流（copy 模式，不重编码）。"""
    import shutil, subprocess
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise BiliError("ffmpeg 未安装，无法合并音视频流。请先: apk add ffmpeg")
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy", "-c:a", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise BiliError(f"ffmpeg 合并失败:\n{result.stderr[-500:]}")


async def _get_download_urls(bvid: str, cred: Credential | None = None) -> dict:
    """
    获取视频和音频的下载地址。
    返回 {"video_url": ..., "audio_url": ..., "is_flv": bool}
    """
    from bilibili_api.video import VideoDownloadURLDataDetecter
    v = video.Video(bvid=bvid, credential=cred)
    data = await _call("获取下载地址", v.get_download_url(page_index=0))
    detector = VideoDownloadURLDataDetecter(data)
    is_flv = detector.check_flv_mp4_stream()

    if is_flv:
        # FLV/MP4 流：视频音频合一，直接下载
        streams = detector.detect_best_streams()
        url = streams[0].url if streams and streams[0] else None
        if not url:
            raise BiliError("无法获取 FLV 流地址")
        return {"video_url": url, "audio_url": None, "is_flv": True}
    else:
        # DASH 流：视频和音频分离，需要下载后合并
        try:
            from bilibili_api.video import AudioQuality
            streams = detector.detect_best_streams(
                audio_max_quality=AudioQuality._192K,
                no_dolby_audio=True,
                no_hires=True,
            )
        except Exception:
            streams = detector.detect_best_streams()

        video_url = streams[0].url if len(streams) > 0 and streams[0] else None
        audio_url = streams[1].url if len(streams) > 1 and streams[1] else None

        if not video_url:
            raise BiliError("无法获取视频流地址")
        return {"video_url": video_url, "audio_url": audio_url, "is_flv": False}


# ─── 视频 ─────────────────────────────────────────────────────────────────────

async def _get_video_info(bvid: str, cred: Credential | None = None) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("获取视频信息", v.get_info())

async def _get_video_subtitle(bvid: str, cred: Credential | None = None) -> tuple[str, list]:
    v = video.Video(bvid=bvid, credential=cred)
    pages = await _call("获取视频分P", v.get_pages())
    if not pages:
        return "", []
    cid = pages[0].get("cid")
    if not cid:
        return "", []
    player_info = await _call("获取播放器信息", v.get_player_info(cid=cid))
    subtitle_info = player_info.get("subtitle", {})
    if not subtitle_info or not subtitle_info.get("subtitles"):
        return "", []
    subtitle_list = subtitle_info["subtitles"]
    subtitle_url = None
    for sub in subtitle_list:
        if "zh" in sub.get("lan", "").lower():
            subtitle_url = sub.get("subtitle_url", "")
            break
    if not subtitle_url and subtitle_list:
        subtitle_url = subtitle_list[0].get("subtitle_url", "")
    if not subtitle_url:
        return "", []
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(subtitle_url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
    except Exception as e:
        raise NetworkError(f"下载字幕失败: {e}") from e
    if "body" in data:
        raw = data["body"]
        return "\n".join(item.get("content", "") for item in raw), raw
    return "", []

async def _get_video_comments(bvid: str, cred: Credential | None = None) -> list:
    v = video.Video(bvid=bvid, credential=cred)
    info = await _call("获取视频信息", v.get_info())
    aid = info.get("aid")
    if not aid:
        return []
    c = comment.Comment(oid=aid, type=comment.CommentResourceType.VIDEO, credential=cred)
    result = await _call("获取评论", c.get_comments())
    return result.get("replies") or []

async def _get_related_videos(bvid: str, cred: Credential | None = None) -> list:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("获取相关视频", v.get_related())

async def _get_ai_summary(bvid: str, cred: Credential | None = None) -> str:
    v = video.Video(bvid=bvid, credential=cred)
    try:
        pages = await _call("获取视频分P", v.get_pages())
        if not pages:
            return ""
        cid = pages[0].get("cid")
        result = await _call("获取 AI 总结", v.get_ai_conclusion(cid=cid, credential=cred))
        return result.get("model_result", {}).get("summary", "") or ""
    except Exception:
        return ""

# ─── 用户 ─────────────────────────────────────────────────────────────────────

async def _get_user_info(uid: int, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取用户信息", u.get_user_info())

async def _get_user_relation(uid: int, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取用户关系", u.get_relation_info())

async def _get_self_info(cred: Credential) -> dict:
    return await _call("获取自身信息", user.get_self_info(cred))

async def _get_user_videos(uid: int, count: int = 10, cred: Credential | None = None) -> list:
    u = user.User(uid=uid, credential=cred)
    results = []
    page = 1
    while len(results) < count:
        batch = await _call("获取用户视频", u.get_videos(pn=page))
        items = batch.get("list", {}).get("vlist", [])
        if not items:
            break
        results.extend(items)
        page += 1
        if len(items) < 30:
            break
    return results[:count]# ─── 搜索 ─────────────────────────────────────────────────────────────────────

async def _search_users(keyword: str, page: int = 1) -> list:
    from bilibili_api.search import SearchObjectType
    result = await _call("搜索用户", search.search_by_type(
        keyword, search_type=SearchObjectType.USER, page=page,
    ))
    return result.get("result", []) or []

async def _search_videos(keyword: str, page: int = 1, count: int = 20) -> list:
    from bilibili_api.search import SearchObjectType
    result = await _call("搜索视频", search.search_by_type(
        keyword, search_type=SearchObjectType.VIDEO, page=page,
    ))
    return (result.get("result", []) or [])[:count]

# ─── 发现 ─────────────────────────────────────────────────────────────────────

async def _get_hot(page: int = 1, count: int = 20) -> list:
    result = await _call("获取热门", hot.get_hot_videos(pn=page, ps=count))
    return result.get("list", []) or []

async def _get_rank(day: int = 3, count: int = 100) -> list:
    from bilibili_api.rank import RankDayType
    day_map = {1: RankDayType.ONE_DAY, 7: RankDayType.SEVEN_DAY}
    day_type = day_map.get(day, RankDayType.THREE_DAY)
    result = await _call("获取排行榜", rank.get_rank(day=day_type))
    items = result.get("list", []) or []
    return items[:count]

async def _get_feed(offset: int = 0, cred: Credential | None = None) -> dict:
    result = await _call("获取动态 Feed", dynamic.get_dynamic_page_UPs_info(credential=cred, offset=offset))
    return result

async def _get_my_dynamics(uid: int, offset: int = 0, cred: Credential | None = None) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("获取我的动态", u.get_dynamics(offset=offset))

async def _post_dynamic(text: str, cred: Credential) -> dict:
    if not text.strip():
        raise BiliError("发布动态: 文本不能为空")
    info = dynamic.BuildDynamic.empty().add_text(text.strip())
    return await _call("发布动态", dynamic.send_dynamic(info=info, credential=cred))

async def _delete_dynamic(dynamic_id: int, cred: Credential) -> dict:
    d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=cred)
    return await _call("删除动态", d.delete())

# ─── 收藏 ─────────────────────────────────────────────────────────────────────

async def _get_favorite_folders(uid: int, cred: Credential | None = None) -> list:
    result = await _call("获取收藏夹", favorite_list.get_video_favorite_list(uid=uid, credential=cred))
    return result.get("list", []) or []

async def _get_favorite_videos(folder_id: int, page: int = 1, count: int = 20, cred: Credential | None = None) -> list:
    result = await _call("获取收藏视频", favorite_list.get_video_favorite_list_content(
        media_id=folder_id, page=page, credential=cred,
    ))
    return (result.get("medias", []) or [])[:count]

async def _get_following(uid: int, page: int = 1, cred: Credential | None = None) -> list:
    u = user.User(uid=uid, credential=cred)
    result = await _call("获取关注列表", u.get_followings(pn=page))
    return result.get("list", []) or []

async def _get_watch_later(cred: Credential) -> list:
    result = await _call("获取稍后再看", favorite_list.get_video_toview_list(credential=cred))
    return result.get("list", []) or []

async def _get_history(cred: Credential) -> list:
    # 17.x 中历史记录通过 user.get_self_history 获取
    try:
        result = await _call("获取历史记录", user.get_self_history(credential=cred))
        return result.get("list", []) or []
    except Exception:
        return []

# ─── 互动 ─────────────────────────────────────────────────────────────────────

async def _like_video(bvid: str, cred: Credential, undo: bool = False) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("点赞", v.like(status=not undo))

async def _coin_video(bvid: str, cred: Credential, num: int = 1) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("投币", v.pay_coin(num=num))

async def _triple_video(bvid: str, cred: Credential) -> dict:
    v = video.Video(bvid=bvid, credential=cred)
    return await _call("一键三连", v.triple())

async def _unfollow_user(uid: int, cred: Credential) -> dict:
    u = user.User(uid=uid, credential=cred)
    return await _call("取消关注", u.modify_relation(relation=user.RelationType.UNSUBSCRIBE))


# ═══════════════════════════════════════════════════════════════════════════════
# BiliClient — 同步封装，对外暴露的主类
# ═══════════════════════════════════════════════════════════════════════════════

class BiliClient:
    """
    哔哩哔哩 API 客户端。

    Cookie 直接通过构造函数传入，支持两种方式：

    方式一：dict 传入
        cookies = {"SESSDATA": "...", "bili_jct": "...", "DedeUserID": "..."}
        client = BiliClient(cookies)

    方式二：从环境变量读取
        client = BiliClient.from_env()
        # 需要设置：BILI_SESSDATA, BILI_JCT, BILI_USERID

    Cookie 获取方式（browser_use 自动获取，见 SKILL.md）：
        1. browser_use navigate → https://www.bilibili.com
        2. browser_use get_cookies → 获取 SESSDATA / bili_jct / DedeUserID
        3. 加载 offload env 文件注入环境变量
    """

    def __init__(self, cookies: dict[str, str] | None = None):
        self._cred: Credential | None = None
        if cookies:
            if not cookies.get("SESSDATA"):
                raise ValueError("cookies 必须包含 'SESSDATA' 字段")
            self._cred = make_credential(cookies)

    @classmethod
    def from_env(cls) -> "BiliClient":
        """从环境变量构建客户端。需要 BILI_SESSDATA / BILI_JCT / BILI_USERID。"""
        sessdata = os.environ.get("BILI_SESSDATA", "")
        if not sessdata:
            raise ValueError("环境变量 BILI_SESSDATA 未设置")
        return cls({
            "SESSDATA":   sessdata,
            "bili_jct":   os.environ.get("BILI_JCT", ""),
            "DedeUserID": os.environ.get("BILI_USERID", ""),
            "buvid3":     os.environ.get("BILI_BUVID3", ""),
        })

    def _auth(self, require_write: bool = False) -> Credential:
        """获取认证凭证，未登录时抛出 AuthenticationError。"""
        if not self._cred or not self._cred.sessdata:
            raise AuthenticationError("未登录，请先传入 Cookie")
        if require_write and not self._cred.bili_jct:
            raise AuthenticationError("写操作需要 bili_jct Cookie")
        return self._cred

    # ── 账号 ──────────────────────────────────────────────────────────────

    def whoami(self) -> dict:
        """获取当前登录用户信息。"""
        return _run(_get_self_info(self._auth()))

    # ── 视频 ──────────────────────────────────────────────────────────────

    def get_video(
        self,
        bvid: str,
        *,
        subtitle: bool = False,
        subtitle_timeline: bool = False,
        ai_summary: bool = False,
        comments: bool = False,
        related: bool = False,
    ) -> dict:
        """
        获取视频详情。

        bvid: BV 号或包含 BV 号的 URL
        subtitle: 是否获取字幕（纯文本）
        subtitle_timeline: 是否获取带时间轴字幕
        ai_summary: 是否获取 AI 总结（需登录）
        comments: 是否获取热门评论
        related: 是否获取相关视频
        """
        bvid = extract_bvid(bvid)
        cred = self._cred

        async def _fetch():
            info = await _get_video_info(bvid, cred)
            sub_text, sub_raw = "", []
            if subtitle or subtitle_timeline:
                sub_text, sub_raw = await _get_video_subtitle(bvid, cred)
            ai = await _get_ai_summary(bvid, cred) if ai_summary else ""
            cmts = await _get_video_comments(bvid, cred) if comments else []
            rels = await _get_related_videos(bvid, cred) if related else []
            return info, sub_text, sub_raw, ai, cmts, rels

        info, sub_text, sub_raw, ai, cmts, rels = _run(_fetch())

        from .payloads import normalize_video_command_payload
        return normalize_video_command_payload(
            info,
            subtitle_text=sub_text,
            subtitle_items=sub_raw if subtitle_timeline else None,
            ai_summary=ai,
            comments=cmts,
            related=rels,
        )

    # ── 用户 ──────────────────────────────────────────────────────────────

    def get_user(self, uid: int) -> dict:
        """获取用户主页信息。"""
        async def _fetch():
            info = await _get_user_info(uid, self._cred)
            rel  = await _get_user_relation(uid, self._cred)
            return info, rel
        info, rel = _run(_fetch())
        from .payloads import normalize_user, normalize_relation
        return {"user": normalize_user(info), "relation": normalize_relation(rel)}

    def get_user_videos(self, uid: int, count: int = 20) -> list:
        """获取用户发布的视频列表。"""
        from .payloads import normalize_video_summary
        items = _run(_get_user_videos(uid, count, self._cred))
        return [normalize_video_summary(v) for v in items]

    # ── 搜索 ──────────────────────────────────────────────────────────────

    def search_users(self, keyword: str, page: int = 1) -> list:
        """搜索用户。"""
        from .payloads import normalize_search_user
        items = _run(_search_users(keyword, page))
        return [normalize_search_user(u) for u in items]

    def search_videos(self, keyword: str, page: int = 1, count: int = 20) -> list:
        """搜索视频。"""
        from .payloads import normalize_search_video
        items = _run(_search_videos(keyword, page, count))
        return [normalize_search_video(v) for v in items]

    # ── 发现 ──────────────────────────────────────────────────────────────

    def get_hot(self, page: int = 1, count: int = 20) -> list:
        """获取热门视频。"""
        from .payloads import normalize_video_summary
        items = _run(_get_hot(page, count))
        return [normalize_video_summary(v) for v in items]

    def get_rank(self, day: int = 3, count: int = 50) -> list:
        """获取全站排行榜。day: 1/3/7"""
        from .payloads import normalize_video_summary
        items = _run(_get_rank(day, count))
        return [normalize_video_summary(v) for v in items]

    def get_feed(self, offset: int = 0) -> dict:
        """获取关注动态 Feed（需登录）。"""
        return _run(_get_feed(offset, self._auth()))

    def get_my_dynamics(self, offset: int = 0) -> list:
        """获取我发布的动态（需登录）。"""
        from .payloads import normalize_dynamic_item
        cred = self._auth()
        info = _run(_get_self_info(cred))
        uid  = int(info.get("mid", 0))
        result = _run(_get_my_dynamics(uid, offset, cred))
        items = result.get("items", []) or []
        return [normalize_dynamic_item(i) for i in items]

    def post_dynamic(self, text: str) -> dict:
        """发布文字动态（需登录）。"""
        return _run(_post_dynamic(text, self._auth(require_write=True)))

    def delete_dynamic(self, dynamic_id: int) -> dict:
        """删除动态（需登录）。"""
        return _run(_delete_dynamic(dynamic_id, self._auth(require_write=True)))

    # ── 收藏 ──────────────────────────────────────────────────────────────

    def get_favorites(self, folder_id: int | None = None, page: int = 1, count: int = 20) -> list | dict:
        """
        获取收藏夹。
        - folder_id=None: 返回收藏夹列表
        - folder_id=<id>: 返回该收藏夹内的视频
        """
        cred = self._auth()
        if folder_id is None:
            info = _run(_get_self_info(cred))
            uid  = int(info.get("mid", 0))
            from .payloads import normalize_favorite_folder
            items = _run(_get_favorite_folders(uid, cred))
            return [normalize_favorite_folder(f) for f in items]
        from .payloads import normalize_favorite_media
        items = _run(_get_favorite_videos(folder_id, page, count, cred))
        return [normalize_favorite_media(v) for v in items]

    def get_following(self, page: int = 1) -> list:
        """获取关注列表（需登录）。"""
        cred = self._auth()
        info = _run(_get_self_info(cred))
        uid  = int(info.get("mid", 0))
        from .payloads import normalize_following_user
        items = _run(_get_following(uid, page, cred))
        return [normalize_following_user(u) for u in items]

    def get_watch_later(self) -> list:
        """获取稍后再看列表（需登录）。"""
        from .payloads import normalize_watch_later_item
        items = _run(_get_watch_later(self._auth()))
        return [normalize_watch_later_item(v) for v in items]

    def get_history(self) -> list:
        """获取观看历史（需登录）。"""
        from .payloads import normalize_history_item
        items = _run(_get_history(self._auth()))
        return [normalize_history_item(v) for v in items]

    # ── 互动 ──────────────────────────────────────────────────────────────

    def like(self, bvid: str, undo: bool = False) -> dict:
        """点赞 / 取消点赞。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_like_video(bvid, self._auth(require_write=True), undo=undo))
        return action_result("like" if not undo else "unlike", bvid=bvid)

    def coin(self, bvid: str, num: int = 1) -> dict:
        """投币（1 或 2 枚）。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_coin_video(bvid, self._auth(require_write=True), num=num))
        return action_result("coin", bvid=bvid, num=num)

    def triple(self, bvid: str) -> dict:
        """一键三连（点赞 + 投币 + 收藏）。"""
        from .payloads import action_result
        bvid = extract_bvid(bvid)
        _run(_triple_video(bvid, self._auth(require_write=True)))
        return action_result("triple", bvid=bvid)

    def unfollow(self, uid: int) -> dict:
        """取消关注用户。"""
        from .payloads import action_result
        _run(_unfollow_user(uid, self._auth(require_write=True)))
        return action_result("unfollow", uid=uid)

    # ── 下载 ──────────────────────────────────────────────────────────────

    def download_video(
        self,
        bvid: str,
        output_dir: str = "/var/minis/workspace",
        filename: str | None = None,
    ) -> str:
        """
        下载视频到本地文件，返回输出文件路径。

        流程：
        1. 获取视频信息（标题）和下载地址
        2. 若为 DASH 流（音视频分离）：
           a. 分别下载视频流（.video.mp4）和音频流（.audio.m4a）
           b. 尝试用 bilibili-api 内置方式合并
           c. 失败则 fallback 到 ffmpeg 合并
        3. 若为 FLV/MP4 流（音视频合一）：直接下载，无需合并

        Args:
            bvid:       BV 号或包含 BV 号的 URL
            output_dir: 输出目录（默认 /var/minis/workspace）
            filename:   自定义文件名（不含扩展名），默认用视频标题

        Returns:
            最终输出文件的绝对路径
        """
        import tempfile

        bvid = extract_bvid(bvid)
        cred = self._cred

        async def _fetch():
            info = await _get_video_info(bvid, cred)
            urls = await _get_download_urls(bvid, cred)
            return info, urls

        info, urls = _run(_fetch())

        title = info.get("title", bvid)
        safe = filename or _safe_filename(title)
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{safe}.mp4")

        if urls["is_flv"]:
            # ── FLV/MP4：直接下载，无需合并 ──────────────────────────────
            logger.info("FLV/MP4 流，直接下载 → %s", out_path)
            size = _run(_download_stream(urls["video_url"], out_path))
            logger.info("下载完成: %.1f MB", size / 1024 / 1024)
            return out_path

        # ── DASH：分别下载视频流和音频流，再合并 ─────────────────────────
        with tempfile.TemporaryDirectory() as tmp:
            v_tmp = os.path.join(tmp, "video.mp4")
            a_tmp = os.path.join(tmp, "audio.m4a")

            logger.info("下载视频流 → %s", v_tmp)
            v_size = _run(_download_stream(urls["video_url"], v_tmp))
            logger.info("视频流: %.1f MB", v_size / 1024 / 1024)

            if urls.get("audio_url"):
                logger.info("下载音频流 → %s", a_tmp)
                a_size = _run(_download_stream(urls["audio_url"], a_tmp))
                logger.info("音频流: %.1f MB", a_size / 1024 / 1024)

                # 合并：ffmpeg copy 模式（不重编码）
                logger.info("合并音视频 → %s", out_path)
                try:
                    _ffmpeg_merge(v_tmp, a_tmp, out_path)
                    logger.info("ffmpeg 合并成功")
                except BiliError as e:
                    # ffmpeg 失败：至少保留视频流（无声）
                    import shutil
                    shutil.copy2(v_tmp, out_path)
                    logger.warning("ffmpeg 合并失败，已保存无声视频: %s\n原因: %s", out_path, e)
                    return out_path
            else:
                # 无音频流（少见），直接用视频流
                import shutil
                shutil.copy2(v_tmp, out_path)

        return out_path

    def download_audio(
        self,
        bvid: str,
        output_dir: str = "/var/minis/workspace",
        filename: str | None = None,
    ) -> str:
        """
        仅下载视频的音频流，保存为 .m4a 文件，返回输出路径。

        适合需要提取音频做转写（ASR）的场景。

        Args:
            bvid:       BV 号或包含 BV 号的 URL
            output_dir: 输出目录（默认 /var/minis/workspace）
            filename:   自定义文件名（不含扩展名），默认用视频标题

        Returns:
            输出 .m4a 文件的绝对路径
        """
        bvid = extract_bvid(bvid)
        cred = self._cred

        async def _fetch():
            info = await _get_video_info(bvid, cred)
            urls = await _get_download_urls(bvid, cred)
            return info, urls

        info, urls = _run(_fetch())

        title = info.get("title", bvid)
        safe = filename or _safe_filename(title)
        os.makedirs(output_dir, exist_ok=True)

        if urls["is_flv"]:
            # FLV 流音视频合一，只能下完整视频再用 ffmpeg 提取音频
            import tempfile, shutil, subprocess
            out_path = os.path.join(output_dir, f"{safe}.m4a")
            with tempfile.TemporaryDirectory() as tmp:
                v_tmp = os.path.join(tmp, "video.mp4")
                _run(_download_stream(urls["video_url"], v_tmp))
                import shutil as _shutil
                ffmpeg = _shutil.which("ffmpeg")
                if ffmpeg:
                    cmd = [ffmpeg, "-y", "-i", v_tmp, "-vn", "-acodec", "copy", out_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise BiliError(f"ffmpeg 提取音频失败:\n{result.stderr[-300:]}")
                else:
                    # 无 ffmpeg：直接复制视频文件（兜底）
                    out_path = os.path.join(output_dir, f"{safe}.mp4")
                    shutil.copy2(v_tmp, out_path)
            return out_path

        # DASH：直接下载音频流
        if not urls.get("audio_url"):
            raise BiliError("该视频没有独立音频流")

        out_path = os.path.join(output_dir, f"{safe}.m4a")
        size = _run(_download_stream(urls["audio_url"], out_path))
        logger.info("音频下载完成: %.1f MB → %s", size / 1024 / 1024, out_path)
        return out_path
