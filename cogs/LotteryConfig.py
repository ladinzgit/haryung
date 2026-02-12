import discord
from discord.ext import commands
import json
import os
import random

from admin_utils import is_guild_admin

# JSON 파일 경로
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'lottery_config.json')
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'lottery_data.json')

TOTAL_NUMBERS = 100
NUMBERS_PER_BOARD = 25
DEFAULT_PRIZES = [{"name": "꽝", "count": 100}]


def load_config():
    """설정 파일을 로드합니다."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(data):
    """설정 파일을 저장합니다."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_data():
    """데이터 파일을 로드합니다."""
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_data(data):
    """데이터 파일을 저장합니다."""
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_guild_config(guild_id: str) -> dict:
    """특정 길드의 설정을 가져옵니다."""
    config = load_config()
    if guild_id not in config:
        config[guild_id] = {
            "alert_channel_id": None,
            "mention_role_id": None,
            "prizes": [{"name": "꽝", "count": 100}],
            "shuffled": False,
            "shuffled_prizes": [],
            "board_channel_id": None,
            "board_message_ids": [],
            "info_channel_id": None,
            "info_message_id": None,
            "drawn_numbers": {}
        }
        save_config(config)
    return config[guild_id]


def get_guild_data(guild_id: str) -> dict:
    """특정 길드의 유저 데이터를 가져옵니다."""
    data = load_data()
    if guild_id not in data:
        data[guild_id] = {}
        save_data(data)
    return data[guild_id]


class LotteryConfig(commands.Cog):
    """뽑기 시스템 관리자 설정 명령어"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    # --- 헬퍼 ---

    def _format_prize_list(self, prizes: list) -> str:
        """경품 목록을 포맷팅합니다."""
        lines = []
        for i, p in enumerate(prizes, 1):
            lines.append(f"`{i}.` **{p['name']}** — {p['count']}개")
        total = sum(p['count'] for p in prizes)
        lines.append(f"\n총 **{total}**개")
        return "\n".join(lines)

    # --- 그룹 커맨드 ---

    @commands.group(name="뽑기설정", invoke_without_command=True)
    @is_guild_admin()
    async def lottery_settings(self, ctx):
        """뽑기 설정 도움말을 표시합니다."""
        embed = discord.Embed(
            title="🎰 뽑기 설정 명령어",
            color=discord.Color.gold()
        )
        cmds = [
            ("`*뽑기설정 경품목록`", "현재 경품 구성을 확인합니다."),
            ("`*뽑기설정 경품추가 (경품명)`", "경품을 추가합니다."),
            ("`*뽑기설정 경품셔플`", "경품 번호를 랜덤 배정합니다."),
            ("`*뽑기설정 경품초기화`", "경품을 꽝 100개로 초기화합니다."),
            ("`*뽑기설정 알림채널설정`", "뽑기 결과 알림 채널을 설정합니다."),
            ("`*뽑기설정 역할설정`", "당첨 시 멘션할 역할을 설정합니다."),
            ("`*뽑기설정 뽑기판생성`", "현재 채널에 뽑기판을 생성합니다."),
            ("`*뽑기설정 메시지생성`", "현재 채널에 뽑기권 안내 메시지를 생성합니다."),
        ]
        for name, desc in cmds:
            embed.add_field(name=name, value=desc, inline=False)
        await ctx.send(embed=embed)

    # --- 경품 관리 ---

    @lottery_settings.command(name="경품목록")
    @is_guild_admin()
    async def prize_list(self, ctx):
        """현재 경품 구성을 나열합니다."""
        guild_id = str(ctx.guild.id)
        gc = get_guild_config(guild_id)
        embed = discord.Embed(
            title="🎁 현재 경품 목록",
            description=self._format_prize_list(gc["prizes"]),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @lottery_settings.command(name="경품추가")
    @is_guild_admin()
    async def prize_add(self, ctx, *, prize_name: str):
        """경품을 추가합니다. 추가 후 개수를 입력받습니다."""
        guild_id = str(ctx.guild.id)

        await ctx.send(f"**{prize_name}**을(를) 몇 개 추가할까요? (숫자를 입력해주세요)")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
        except Exception:
            await ctx.send("시간이 초과되었습니다. 다시 시도해주세요.")
            return

        count = int(msg.content)
        if count <= 0:
            await ctx.send("1 이상의 숫자를 입력해주세요.")
            return

        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))
        prizes = gc["prizes"]

        # 총 경품 수 확인
        total = sum(p['count'] for p in prizes)
        if total < count:
            await ctx.send(f"현재 총 경품 수({total}개)보다 많이 추가할 수 없습니다.")
            return

        # 꽝 개수 차감
        for p in prizes:
            if p['name'] == '꽝':
                if p['count'] < count:
                    await ctx.send(f"꽝의 개수({p['count']}개)가 부족합니다.")
                    return
                p['count'] -= count
                break

        # 기존 경품이 있으면 합산, 없으면 추가
        existing = next((p for p in prizes if p['name'] == prize_name), None)
        if existing:
            existing['count'] += count
        else:
            prizes.append({"name": prize_name, "count": count})

        # 꽝이 0개면 제거
        gc["prizes"] = [p for p in prizes if p['count'] > 0]
        gc["shuffled"] = False
        save_config(config)

        embed = discord.Embed(
            title="✅ 경품 추가 완료",
            description=f"**{prize_name}** {count}개가 추가되었습니다.\n\n{self._format_prize_list(gc['prizes'])}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @lottery_settings.command(name="경품셔플")
    @is_guild_admin()
    async def prize_shuffle(self, ctx):
        """경품 번호를 랜덤 배정합니다."""
        guild_id = str(ctx.guild.id)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))

        # 경품을 번호에 매핑
        prize_pool = []
        for p in gc["prizes"]:
            prize_pool.extend([p["name"]] * p["count"])

        if len(prize_pool) != TOTAL_NUMBERS:
            await ctx.send(f"경품 총 수가 {TOTAL_NUMBERS}개여야 합니다. 현재: {len(prize_pool)}개")
            return

        random.shuffle(prize_pool)
        gc["shuffled_prizes"] = prize_pool
        gc["shuffled"] = True
        save_config(config)

        await ctx.send("🔀 경품 번호가 셔플되었습니다! 이제 뽑기판을 생성할 수 있습니다.")

    @lottery_settings.command(name="경품초기화")
    @is_guild_admin()
    async def prize_reset(self, ctx):
        """모든 뽑기 데이터를 초기화합니다. (알림채널/역할 제외)"""
        guild_id = str(ctx.guild.id)

        # 설정 초기화 (알림채널, 역할, 메시지 ID 유지)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))
        gc["prizes"] = [{"name": "꽝", "count": 100}]
        gc["shuffled"] = False
        gc["shuffled_prizes"] = []
        gc["drawn_numbers"] = {}
        save_config(config)

        # 유저 데이터 초기화
        data = load_data()
        if guild_id in data:
            data[guild_id] = {}
            save_data(data)

        # 기존 뽑기판 메시지 갱신 (버튼 전부 초록색으로)
        board_cog = self.bot.get_cog("LotteryBoard")
        if board_cog and gc.get("board_message_ids") and gc.get("board_channel_id"):
            channel = self.bot.get_channel(gc["board_channel_id"])
            if channel:
                for idx, mid in enumerate(gc["board_message_ids"]):
                    try:
                        msg = await channel.fetch_message(mid)
                        new_view = board_cog.create_board_view(guild_id, idx)
                        await msg.edit(view=new_view)
                    except Exception:
                        pass

        await ctx.send("🔄 모든 뽑기 데이터가 초기화되었습니다. (꽝 100개, 유저 기록 삭제)")

    # --- 채널/역할 설정 ---

    @lottery_settings.command(name="알림채널설정")
    @is_guild_admin()
    async def set_alert_channel(self, ctx):
        """현재 채널을 뽑기 결과 알림 채널로 설정합니다."""
        guild_id = str(ctx.guild.id)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))
        gc["alert_channel_id"] = ctx.channel.id
        save_config(config)

        await ctx.send(f"📢 뽑기 결과 알림 채널이 {ctx.channel.mention}(으)로 설정되었습니다.")

    @lottery_settings.command(name="역할설정")
    @is_guild_admin()
    async def set_mention_role(self, ctx, role: discord.Role):
        """당첨 시 멘션할 역할을 설정합니다."""
        guild_id = str(ctx.guild.id)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))
        gc["mention_role_id"] = role.id
        save_config(config)

        await ctx.send(f"🏷️ 당첨 알림 역할이 {role.mention}(으)로 설정되었습니다.")

    # --- 뽑기판 / 메시지 생성 ---

    @lottery_settings.command(name="뽑기판생성")
    @is_guild_admin()
    async def create_board(self, ctx):
        """현재 채널에 뽑기판을 생성합니다."""
        guild_id = str(ctx.guild.id)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))

        if not gc.get("shuffled"):
            await ctx.send("⚠️ 먼저 `*뽑기설정 경품셔플`을 실행해주세요.")
            return

        # 기존 뽑기판 메시지 삭제 시도
        if gc.get("board_message_ids") and gc.get("board_channel_id"):
            old_channel = self.bot.get_channel(gc["board_channel_id"])
            if old_channel:
                for mid in gc["board_message_ids"]:
                    try:
                        old_msg = await old_channel.fetch_message(mid)
                        await old_msg.delete()
                    except Exception:
                        pass

        drawn = gc.get("drawn_numbers", {})
        gc["board_channel_id"] = ctx.channel.id
        gc["board_message_ids"] = []

        # LotteryBoard cog에서 View를 가져와서 사용
        board_cog = self.bot.get_cog("LotteryBoard")
        if not board_cog:
            await ctx.send("⚠️ LotteryBoard cog가 로드되지 않았습니다.")
            return

        # 타이틀 메시지
        BOARD_TITLE = "# <:BM_inv:1384475516152582144> <a:BM_gliter_008:1377697360632610823> 설날 운명의 뽑기판 <a:BM_gliter_008:1377697360632610823>"
        BOARD_SEPARATOR = "╴╴╴╴╴⊹ꮺ˚ ╴╴╴╴╴⊹˚ ╴╴╴╴˚ೃ ╴╴"

        await ctx.send(BOARD_TITLE)

        for board_idx in range(4):
            view = board_cog.create_board_view(guild_id, board_idx)
            msg = await ctx.send(view=view)
            gc["board_message_ids"].append(msg.id)

            # 마지막 뽑기판 뒤에는 구분선 생략
            if board_idx < 3:
                await ctx.send(BOARD_SEPARATOR)

        save_config(config)

    @lottery_settings.command(name="메시지생성")
    @is_guild_admin()
    async def create_info_message(self, ctx):
        """현재 채널에 뽑기권 안내 메시지를 생성합니다."""
        guild_id = str(ctx.guild.id)
        config = load_config()
        gc = config.setdefault(guild_id, get_guild_config(guild_id))

        # 기존 메시지 삭제 시도
        if gc.get("info_message_id") and gc.get("info_channel_id"):
            old_channel = self.bot.get_channel(gc["info_channel_id"])
            if old_channel:
                try:
                    old_msg = await old_channel.fetch_message(gc["info_message_id"])
                    await old_msg.delete()
                except Exception:
                    pass

        board_cog = self.bot.get_cog("LotteryBoard")
        if not board_cog:
            await ctx.send("⚠️ LotteryBoard cog가 로드되지 않았습니다.")
            return

        embed = discord.Embed(
            title="설날 운명의 뽑기판",
            description="아래 버튼을 눌러 뽑기권을 확인하거나 받을 수 있어...",
            color=discord.Color.purple()
        )
        view = board_cog.create_info_view(guild_id)
        msg = await ctx.send(embed=embed, view=view)

        gc["info_channel_id"] = ctx.channel.id
        gc["info_message_id"] = msg.id
        save_config(config)

    # --- 에러 핸들러 ---

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("필요한 인자가 부족합니다. 명령어를 확인해주세요.")
        elif isinstance(error, commands.CheckFailure):
            pass
        else:
            print(f"LotteryConfig 오류: {error}")
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(f"LotteryConfig 오류: {error}", "LotteryConfig.py")


async def setup(bot):
    await bot.add_cog(LotteryConfig(bot))
