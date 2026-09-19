r"""make_zh_to_en.py - build the reverse table the English fallback switch reads.

The dictionary is written  english=chinese .  A map whose own font lacks CJK
glyphs shows every Chinese string as boxes, and stepping aside is NOT enough
for the strings the game and the map wrote themselves - those stay Chinese
whatever we do.  This table is what turns them back into English.

Only unambiguous, plain-text entries are taken: a value that itself contains a
colour code, a wildcard or a bracket is a template or a composed label, and
reversing it would produce nonsense.  When several English keys share one
Chinese value the first one wins (file order), and the rest are dropped - a
wrong guess is worse than no guess.  (Whatever this table cannot cover stays
Chinese, and therefore stays boxes on such a map: the user has twice rejected
a pinyin fallback, so English or nothing is the rule - see MEMORY.md.)

    python make_zh_to_en.py
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "translate", "translate_zh.txt")
OUT = os.path.join(HERE, "..", "translate", "translate_en.txt")

# Anything that makes a Chinese value unsafe to use as a reverse key.
UNSAFE = re.compile(r"[*^\[\]{}<>\\]")

# A value worth reversing: Chinese, plus the punctuation that travels with it.
PLAIN = re.compile(r"^[\u4e00-\u9fff\u3400-\u4dbf，。！？：；、（）「」【】《》—～…·]+$")

# High-frequency words that the dictionary never stores on their own - it keeps
# them inside whole labels ("按住 ^3F^7 购买…"), which cannot be reversed as a
# unit.  The engine matches these against Chinese runs longest-first, so the
# words a map's own UI is built from have to be here by hand.
#
# ⚠️ WHOLE WORDS ONLY.  A single Chinese character is almost always a particle
# or a word fragment ("中" inside "丛林中", "按" inside "按住"), so a
# one-character entry does not translate a word - it cuts a real word in half
# and drops an English fragment into the middle of a Chinese sentence
# ("丛林medium的").  main() refuses anything shorter than two characters.
EXTRA = {
	"按住": "Hold",
	"按下": "Press",
	"购买": "Buy",
	"喝下": "Drink",
	"重新打包": "Repack",
	"打包": "Pack",
	"消耗": "Cost",
	"价格": "Price",
	"剩余": "Remaining",
	"升级": "Upgrade",
	"弹药": "Ammo",
	"补给": "Replenish",
	"换弹": "Reload",
	"复活": "Revive",
	"受伤": "Take Damage",
	"武器": "Weapon",
	"手雷": "Grenade",
	"技能": "Perk",
	"僵尸": "Zombie",
	"僵尸模式": "Zombies",
	"回到游戏": "Return to game",
	"结束游戏": "End game",
	"开始游戏": "Start game",
	"重新开始": "Restart",
	"离开游戏": "Leave game",
	"加入游戏": "Join game",
	"单人游戏": "Solo",
	"多人游戏": "Multiplayer",
	"战役": "Campaign",
	"暂停": "Pause",
	"保存": "Save",
	"载入": "Load",
	"读取": "Load",
	"删除": "Delete",
	"确认": "Confirm",
	"提示": "Hint",
	"警告": "Warning",
	"错误": "Error",
	"加载中": "Loading",
	"请稍候": "Please wait",
	"玩家": "Player",
	"队友": "Teammate",
	"地图": "Map",
	"模式": "Mode",
	"设置": "Settings",
	"选项": "Options",
	"退出": "Exit",
	"返回": "Back",
	"开始": "Start",
	"继续": "Continue",
	"重试": "Retry",
	"确定": "OK",
	"取消": "Cancel",
	"关闭": "Off",
	"开启": "On",
	"分钟": "min",
	"小时": "h",
	"回合": "Round",
	"击杀": "Kills",
	"死亡": "Deaths",
	"奖励": "Reward",
	"挑战": "Challenge",
	"任务": "Mission",
	"目标": "Objective",
	"使用": "Use",
	"获得": "Get",
	"解锁": "Unlock",
	"已解锁": "Unlocked",
	"已锁定": "Locked",
	"等级": "Level",
	"经验": "XP",
	"分数": "Score",
	"时间": "Time",
	"生命": "Health",
	"速度": "Speed",
	"伤害": "Damage",
	"防御": "Defense",
	"攻击": "Attack",
	"数量": "Count",
	"总计": "Total",
	"最大": "Max",
	"最小": "Min",
	"当前": "Current",
	"敌人": "Enemies",
	"剩余敌人": "Enemies Remaining",
	"重建障碍": "Rebuild Barrier",
	"重建路障": "Rebuild Barrier",
	"障碍": "Barrier",
	"路障": "Barrier",
	"技能可乐": "Perk",
	"汽水": "Perk",
	"神秘底座": "Mystery Pedestal",
	"神秘箱子": "Mystery Box",
	"泡泡糖": "GobbleGum",
	"弹药补给": "Ammo Replenish",
	"打开": "Open",
	"开启箱子": "Open",
	"花费": "Cost",
	"启用": "Enable",
	"禁用": "Disable",
	"重建": "Rebuild",
	"获得奖励": "Reward",
	"是": "Yes",
	"否": "No",
	"与": "and",
	"和": "and",
	"或": "or",
	"中": "Medium",
	"无": "None",
	"新": "New",
	"级": "Lv",
	"分": "pts",
	"秒": "s",
	"波": "Wave",
	"开": "On",
	"关": "Off",
	"值": "Value",
	"个": "",
	"人": "",
	"包": "Pack",
	# Quality levels: each is drawn as its own label beside a setting, so it is a
	# whole word there (see SINGLE_OK - it can still never match inside a longer
	# run, so "高" in "高级" is untouched).
	"高": "High",
	"低": "Low",
	# Common one-character action / direction labels (2026-09-20), see SINGLE_OK.
	"按": "Press",
	"用": "Use",
	"上": "Up",
	"下": "Down",
	"左": "Left",
	"右": "Right",
	"全": "All",
	"大": "Large",
	"小": "Small",
	"多": "More",
	"泡泡糖包": "GobbleGum Pack",
	"倒下": "Downs",
	"存活": "Survived",
	"存活时间": "Survival Time",
	"房子": "House",
	"服务器": "Server",
	"使命召唤": "Call of Duty",
	"已连接至": "Connected to",
	"已连接": "Connected",
	"连接至": "Connected to",
	# [LOCAL] 2026-09-19: the game's OWN wording, where it differs from ours.
	# The dictionary above is our translation ("graphics" -> "画面"); the game
	# ships "图像".  Reverse lookup keys off the CHINESE, so the game's wording
	# has to be listed separately or the string is never found.
	# (Whatever stays unlisted keeps its Chinese, and so keeps its boxes - the
	# wording we actually saw in game is worth listing here for that reason.)
	"图像": "Graphics",
	"显示": "Display",
	"显示帧数": "Show FPS",
	"帧数": "FPS",
	# Player name display / graphics options seen in the settings panels.
	"简略": "Abbreviated",
	"烟火": "Fireworks",
	# The ADVANCED graphics panel (2026-09-20).  Every one of these arrived from
	# the game itself and had no entry, so it drew as a row of boxes.
	"材质质量": "Material Quality",
	"材质过滤": "Texture Filtering",
	"网格质量": "Mesh Quality",
	"体积照明": "Volumetric Lighting",
	"运动模糊": "Motion Blur",
	"顺序无关透明度": "Order Independent Transparency",
	# The ammo pickup / refill toast (2026-09-20): "弹药全满！" drew as
	# "AMMO[??]!" - the toast icon sat next to two boxes.
	"弹药全满": "Ammo Full",
	"全满": "Full",
	# The CONTROLS tab subtitle (2026-09-20): a game-native sentence that is not
	# in our dictionary, so it half translated ("为GAME SETTINGS操作CONTROLS").
	# Listed as a whole sentence - longest match beats the two words inside it.
	"为游戏设置操作控制": "Edit controls for game settings",
	# 2026-09-20: "按ENTER开始" - the game writes it WITHOUT the space our
	# dictionary value has ("按 ENTER 开始"), so the reverse key never matched
	# and it drew as "按ENTER START".  Listed without the space, as shipped.
	"按ENTER开始": "Press ENTER to start",
	# Mod-map hints and GobbleGum names seen in play (2026-09-20).
	"开门": "Open Door",
	"你需要先打开电源！": "You need to turn on the power first!",
	"一个": "A",
	"生成一个随机强化能力": "Get a randomized GobbleGum",
	"启动到传送垫的连接": "Activate the teleport pad link",
	"力量蛋奶酒": "Power Eggnog",
	"双塞麦根啤酒": "Double Tap Root Beer",
	# The GobbleGum machine's free-round toast (2026-09-20): 39 bytes, so it
	# fits the 45-byte whole-run match and beats the fragments inside it.
	"每回合的第一个泡泡糖免费！": "The first GobbleGum of each round is free!",
	"免费": "Free",
	# Two labels that only half translated: 显示 and 帧数 matched on their own,
	# leaving the rest Chinese.  Listing the whole label wins by longest match.
	"显示灰度": "Display Gamma",
	"每秒最大帧数": "Max FPS",
	"分屏方向": "Splitscreen Orientation",
	"水平": "Horizontal",
	"色盲模式": "Colorblind Mode",
	"在这里": "Here",
	"隐藏该信息": "hide that information",
	"在游戏列表中": "in the game list",
	"允许动态物体显示阴影": "Allow dynamic objects to cast shadows",
	"敌我名称": "friendly and enemy names",
	"显示方式": "display style",
	"新手包": "Starter Pack",
	"战术": "Tactics",
	"全屏": "Fullscreen",
	"窗口化": "Windowed",
	"商城": "Store",
	"特色推荐": "Featured",
	"加入公共游戏": "Join Public Game",
	"私人游戏": "Private Game",
	"服务器浏览器": "Server Browser",
	"公开对局": "Public Match",
	"点击开始聊天": "Click to chat",
	"添加手柄进行分屏游戏": "Add a controller for split-screen",
	"不允许分屏游戏": "Split-screen is not allowed",
	"详细信息": "Details",
	"日常挑战": "Daily Challenge",
	"牛顿的烹饪手册": "Newton's Cookbook",
	"今日的牛顿烹饪手册配方": "Today's Newton's Cookbook recipe",
	"正在连接到在线服务器": "Connecting to online servers",
	"正在装载": "Loading",
	"下一级": "Next Level",
	"无法卧倒": "Cannot go prone",
	"影片开始": "Cinematic starts",
	"废弃机场": "Abandoned Airfield",
	"德国占领下的欧洲": "German-occupied Europe",
	"您是队长": "You are the leader",
	"微冲强化": "SMG Boost",
	"帧数": "Frame Rate",
	"垂直同步": "V-Sync",
	"刷新频率": "Refresh Rate",
	"撕裂": "Tearing",
	"分辨率": "Resolution",
	"性能": "Performance",
	"显示器": "Monitor",
	"画面": "Graphics",
	"视野": "Field of View",
	"场景": "Scene",
	"玩法": "Gameplay",
	"脚本": "Script",
	"最高等级": "Max level",
	"新转折": "New twist",
	"在线服务器": "online servers",
	"分屏游戏": "split-screen",
}

# Single characters that really ARE words on their own.
#
# The engine splits a label at the control bytes the game puts between runs, and
# those runs are translated one at a time - so a character that arrives ALONE
# really is a standalone word at that moment ("与" between "游戏设置" and
# "控制" is literally its own run).  Such a character may live in the table and
# is only ever used when the whole string is that one character (see
# RenderEnglish); the same character inside a longer run ("中" inside "丛林中")
# can never match it and cannot be cut out.
SINGLE_OK = {
	"是", "否", "与", "和", "或", "中", "无", "新", "级", "分",
	"秒", "波", "开", "关", "值", "个", "人", "包",
	# Quality levels are drawn as their own label next to a setting.
	"高", "低",
	# Common one-character action / direction labels (2026-09-20): any of these
	# can arrive as its own run ("按" in a button hint).  Safe by construction -
	# the engine only consults them when the WHOLE string is that one character,
	# so "按" inside "按住" can never be cut out.
	"按", "用", "上", "下", "左", "右", "全", "大", "小", "多",
}


def main():
	if not os.path.exists(SRC):
		sys.exit("missing dictionary: %s" % os.path.normpath(SRC))

	reverse = {}
	order = []
	singles = []
	skipped_dup = 0
	skipped_odd = 0

	with io.open(SRC, "r", encoding="utf-8", newline="") as fh:
		for raw in fh:
			line = raw.rstrip("\r\n")
			if not line or line.startswith("#"):
				continue
			if "=" not in line:
				continue

			key, value = line.split("=", 1)
			# A '~' fragment marker is a matching hint, not part of the English.
			english = key[1:] if key.startswith("~") else key

			if UNSAFE.search(english) or UNSAFE.search(value):
				skipped_odd += 1
				continue
			if not PLAIN.match(value):
				skipped_odd += 1
				continue
			# Same rule as EXTRA: one character is a fragment, not a word.
			if len(value) < 2:
				skipped_odd += 1
				continue

			if value in reverse:
				if reverse[value] != english:
					skipped_dup += 1
				continue

			reverse[value] = english
			order.append(value)

	# The hand-written words come after the derived ones: a real dictionary
	# entry always beats a guess, and the engine prefers the longest match
	# anyway, so order only decides ties.
	for chinese, english in sorted(EXTRA.items()):
		if chinese in reverse:
			continue
		if len(chinese) < 2 and chinese not in SINGLE_OK:
			print("refused one-character entry: %s" % chinese)
			continue
		reverse[chinese] = english
		order.append(chinese)
		if len(chinese) < 2:
			singles.append(chinese)

	with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
		fh.write("# 中文→英文 反查表（口口口兜底「英文」用；由 tools/make_zh_to_en.py 生成）\n")
		fh.write("# 来源：translate_zh.txt 的英文=中文条目倒过来。\n")
		fh.write("# 只收「值本身是纯中文」的条目；含颜色码 / 通配符 / 方括号的一律不收。\n")
		fh.write("# 同一个中文对应多个英文时不猜 —— 取先出现的那条。\n")
		for chinese in order:
			fh.write("%s=%s\n" % (chinese, reverse[chinese]))

	print("rows        : %d" % len(order))
	print("skipped dup : %d" % skipped_dup)
	print("skipped odd : %d" % skipped_odd)
	print("out         : %s" % os.path.normpath(OUT))


main()
