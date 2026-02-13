import discord
from discord.ext import commands
from discord import ui
import random
import datetime
import json
import os

# JSON 파일 경로
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'lottery_config.json')
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'lottery_data.json')

TOTAL_NUMBERS = 100
NUMBERS_PER_BOARD = 25
DAILY_CLAIM_LIMIT = 1


def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_data():
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_data(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_data(guild_id: str, user_id: str) -> dict:
    """유저 데이터를 가져오거나 초기화합니다."""
    data = load_data()
    guild_data = data.setdefault(guild_id, {})
    if user_id not in guild_data:
        guild_data[user_id] = {
            "tickets": 0,
            "total_draws": 0,
            "daily_claims": 0,
            "last_claim_date": None
        }
        save_data(data)
    return guild_data[user_id]


def reset_daily_if_needed(user_data: dict) -> bool:
    """날짜가 바뀌었으면 일일 횟수를 초기화합니다."""
    today = datetime.date.today().isoformat()
    if user_data.get("last_claim_date") != today:
        user_data["daily_claims"] = 0
        user_data["last_claim_date"] = today
        return True
    return False


# --- 하령 페르소나 메시지 ---

CLAIM_MESSAGES = [
    "안녕... {user}...? 오늘의 운명을 살짝 들여다봤어...... 너에겐 **{n}회**의 기회를 줄게... 신중하게 골라......",
    "...{user}... 별을 읽어봤어...... 오늘 너에겐 **{n}회**가 어울린다고 해...... 행운을 빌어......",
    "{user}... 한참 고민했어...... 오늘은 **{n}회**만큼 기회를 줄 수 있을 것 같아...... 잘 써......",
    "......{user}... 너의 운세를 봤는데...... **{n}회**의 빛이 보였어...... 좋은 결과가 있길......",
]

CLAIM_ALREADY_DONE = "...{user}... 오늘은 이미 충분한 기회를 줬어...... 내일 다시 와......  ᶻ 𝗓 𐰁"

DRAW_WIN = "...! 뭔가... 반짝이는 게 보여...... **{prize}**(이)라니... 축하해...... ✨"
DRAW_LOSE = "......아무것도 없었어... 다음엔... 좋은 게 나올지도......"
DRAW_NO_TICKETS = "...뽑기권이 없어... 먼저 뽑기권을 받아와......"

INFO_TEMPLATE = (
    "**🎫 {user}의 뽑기 정보**\n\n"
    "보유 뽑기권: **{tickets}**개\n"
    "지금까지 뽑은 횟수: **{total_draws}**회\n"
    "오늘 남은 뽑기권 획득 기회: **{remaining_claims}**회"
)


# --- Persistent Views ---

class LotteryNumberButton(ui.Button):
    """뽑기판의 개별 번호 버튼"""

    def __init__(self, number: int, guild_id: str, is_drawn: bool):
        self.number = number
        self.guild_id = guild_id
        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.secondary if is_drawn else discord.ButtonStyle.success,
            disabled=is_drawn,
            custom_id=f"lottery_number:{guild_id}:{number}",
            row=(number - 1) % NUMBERS_PER_BOARD // 5
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = str(interaction.user.id)

        # 유저 데이터 확인
        data = load_data()
        guild_data = data.setdefault(guild_id, {})
        user_data = guild_data.setdefault(user_id, {
            "tickets": 0, "total_draws": 0, "daily_claims": 0, "last_claim_date": None
        })

        if user_data["tickets"] <= 0:
            await interaction.response.send_message(
                DRAW_NO_TICKETS.format(user=interaction.user.mention),
                ephemeral=True
            )
            return

        # 이미 뽑힌 번호 확인
        config = load_config()
        gc = config.get(guild_id, {})
        drawn = gc.get("drawn_numbers", {})

        if str(self.number) in drawn:
            await interaction.response.send_message(
                "...이 번호는 이미 누군가가 뽑았어......",
                ephemeral=True
            )
            return

        # 뽑기 실행
        user_data["tickets"] -= 1
        user_data["total_draws"] += 1
        save_data(data)

        # 경품 결과
        shuffled = gc.get("shuffled_prizes", [])
        prize = shuffled[self.number - 1] if self.number - 1 < len(shuffled) else "꽝"

        # 뽑힌 번호 기록
        drawn[str(self.number)] = {
            "user_id": user_id,
            "user_name": interaction.user.display_name,
            "prize": prize
        }
        gc["drawn_numbers"] = drawn
        save_config(config)

        # 유저에게 결과 전송
        if prize == "꽝":
            result_msg = DRAW_LOSE
        else:
            result_msg = DRAW_WIN.format(prize=prize)

        await interaction.response.send_message(
            f"**{self.number}번**을 뽑았어...\n{result_msg}",
            ephemeral=True
        )

        # 버튼 상태 업데이트 (현재 메시지의 뷰 갱신)
        board_idx = (self.number - 1) // NUMBERS_PER_BOARD
        new_view = LotteryBoardView(guild_id, board_idx)
        await interaction.message.edit(view=new_view)

        # 알림 채널에 결과 전송
        alert_channel_id = gc.get("alert_channel_id")
        if alert_channel_id:
            alert_channel = interaction.guild.get_channel(alert_channel_id)
            if alert_channel:
                if prize != "꽝":
                    mention_role_id = gc.get("mention_role_id")
                    role_mention = f"<@&{mention_role_id}>" if mention_role_id else ""
                    alert_embed = discord.Embed(
                        title="🎉 당첨!",
                        description=f"{interaction.user.mention}님이 **{self.number}번**에서 **{prize}**에 당첨되었습니다!",
                        color=discord.Color.gold()
                    )
                    await alert_channel.send(content=role_mention, embed=alert_embed)
                else:
                    alert_embed = discord.Embed(
                        title="🎰 뽑기 결과",
                        description=f"{interaction.user.mention}님이 **{self.number}번**을 뽑았습니다. (꽝)",
                        color=discord.Color.greyple()
                    )
                    await alert_channel.send(embed=alert_embed)


class LotteryBoardView(ui.View):
    """5x5 뽑기판 View"""

    def __init__(self, guild_id: str, board_idx: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.board_idx = board_idx

        config = load_config()
        gc = config.get(guild_id, {})
        drawn = gc.get("drawn_numbers", {})

        start_num = board_idx * NUMBERS_PER_BOARD + 1
        for i in range(NUMBERS_PER_BOARD):
            num = start_num + i
            is_drawn = str(num) in drawn
            self.add_item(LotteryNumberButton(num, guild_id, is_drawn))


class LotteryInfoView(ui.View):
    """뽑기권 안내 메시지 View"""

    def __init__(self, guild_id: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @ui.button(label="🎫 내 뽑기 정보", style=discord.ButtonStyle.primary, custom_id="lottery_info_check")
    async def check_info(self, interaction: discord.Interaction, button: ui.Button):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        user_data = get_user_data(guild_id, user_id)
        reset_daily_if_needed(user_data)

        # 저장 (날짜 리셋 반영)
        data = load_data()
        data.setdefault(guild_id, {})[user_id] = user_data
        save_data(data)

        remaining = DAILY_CLAIM_LIMIT - user_data["daily_claims"]
        msg = INFO_TEMPLATE.format(
            user=interaction.user.display_name,
            tickets=user_data["tickets"],
            total_draws=user_data["total_draws"],
            remaining_claims=max(0, remaining)
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @ui.button(label="🎁 뽑기권 받기", style=discord.ButtonStyle.success, custom_id="lottery_claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        data = load_data()
        guild_data = data.setdefault(guild_id, {})
        user_data = guild_data.setdefault(user_id, {
            "tickets": 0, "total_draws": 0, "daily_claims": 0, "last_claim_date": None
        })

        reset_daily_if_needed(user_data)

        if user_data["daily_claims"] >= DAILY_CLAIM_LIMIT:
            await interaction.response.send_message(
                CLAIM_ALREADY_DONE.format(user=interaction.user.mention),
                ephemeral=True
            )
            return

        # 1~5 랜덤 뽑기권 지급
        amount = random.randint(1, 5)
        user_data["tickets"] += amount
        user_data["daily_claims"] += 1
        save_data(data)

        msg_template = random.choice(CLAIM_MESSAGES)
        await interaction.response.send_message(
            msg_template.format(user=interaction.user.mention, n=amount),
            ephemeral=True
        )


class LotteryBoard(commands.Cog):
    """뽑기판 UI 및 상호작용"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Persistent View 등록"""
        config = load_config()
        for guild_id, gc in config.items():
            # 뽑기판 View 등록
            if gc.get("board_message_ids"):
                for board_idx in range(4):
                    view = LotteryBoardView(guild_id, board_idx)
                    self.bot.add_view(view)

            # 안내 메시지 View 등록
            if gc.get("info_message_id"):
                view = LotteryInfoView(guild_id)
                self.bot.add_view(view)

        print(f"✅ {self.__class__.__name__} loaded successfully!")

    def create_board_view(self, guild_id: str, board_idx: int) -> LotteryBoardView:
        """LotteryConfig에서 호출할 뽑기판 View 생성"""
        view = LotteryBoardView(guild_id, board_idx)
        self.bot.add_view(view)
        return view

    def create_info_view(self, guild_id: str) -> LotteryInfoView:
        """LotteryConfig에서 호출할 안내 메시지 View 생성"""
        view = LotteryInfoView(guild_id)
        self.bot.add_view(view)
        return view

    async def cog_command_error(self, ctx, error):
        print(f"LotteryBoard 오류: {error}")
        logger = self.bot.get_cog('Logger')
        if logger:
            await logger.log(f"LotteryBoard 오류: {error}", "LotteryBoard.py")


async def setup(bot):
    await bot.add_cog(LotteryBoard(bot))
