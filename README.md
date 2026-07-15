# desktop-pet

macOS 桌面动漫宠物 · 星街彗星陪你写代码 · 定时提醒喝水站立 · 一键唤起 Claude / Codex / DeepSeek 聊天

<p align="center">
  <b>浮在所有窗口之上 · 无 Dock 图标 · 跟随鼠标 · 工作时段自动上班</b>
</p>

---

## 功能一览

- 🐾 **透明抠图桌宠** — 支持 sprite atlas (codex-pets 站的 192×208 图集,9 个动作) 和 "一个目录多张状态 GIF" 两种资源模式
- 🖱️ **拖动 + 跟随鼠标** — 左键拖走,右键呼出菜单,跟随鼠标时按方向自动切 `running-right` / `running-left` / `idle`
- 🪟 **穿透全屏 App + 所有 Space** — `NSFloatingWindowLevel` + `canJoinAllSpaces | fullScreenAuxiliary` + `hidesOnDeactivate = NO`,点终端也不消失
- 🚫 **无 Dock 图标** — `NSApplicationActivationPolicyAccessory`,后台常驻不占任务栏
- 💧 **强提醒气泡** — 起立 / 喝水 定时提醒,气泡"从苏酱嘴里吹气球"式生长 (充气 → 抖动 → 变形成对话框),文字在气球中同步放大;永不自动消失,点 `×` 才关闭,关闭后宠物自动恢复原动作
- ⭐ **鼓励语** — 每 10-15 分钟随机在苏酱头顶浮一句鼓励,淡入淡出 (不打扰,不需要点)
- 🌙 **Snooze 暂停** — 一键"今天/3天/7天/自定义 天内不再弹出",退出并静音;设定 ≥2 天会二次确认并给出恢复命令;第 N+1 天自动恢复;也可以随时双击 `resume.command` 立即恢复
- 💬 **LLM 聊天** — 点气泡 → 缩小成对话框,支持 Claude / Codex / DeepSeek,自动检测本机 `claude` / `codex` CLI 是否已登录,零配置直接用
- 📅 **工作时段自动上班** — launchd 在周一到周五 (法定节假日除外) 10/11/14/15/16/17/18 点触发,午休 12/13 点跳过。宠物没启动就自动拉起。用户手动 Quit 后,下一次到点又拉起
- ⚙️ **配置可视化** — 提醒文案 / 间隔 / API key / 系统提示词 全部有 GUI 编辑,不用改代码

---

## 环境要求

- **macOS 12+** (作者在 macOS 15 / Darwin 25 上验证)
- **Python 3.10+** (推荐 Homebrew 装的 3.14)
- 网络能到 GitHub / PyPI / 各 LLM 提供商

Windows / Linux 提示: PyQt5 窗口和 LLM 聊天逻辑跨平台,但 launchd、NSWindow 桥、`pgrep` 都是 macOS 专属。想在 Windows 跑要自己实现 Task Scheduler + `tasklist` 版本的 `launch_or_remind`。

---

## 安装

```bash
git clone https://github.com/chaserr/desktop-pet.git
cd desktop-pet

# venv (Homebrew Python 有 PEP 668,不能直接 pip install)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 手动启动 (不装 launchd 也能用)
.venv/bin/python pet.py
```

首次启动会自动在项目目录下 `data/config.json` 读/写配置,资源和运行时状态全在项目内的 `data/`。

---

## 首次使用

1. 启动后左键**拖动**苏酱到喜欢的位置
2. 在苏酱身上**右键**呼出菜单,常用几项:
   | 菜单 | 说明 |
   |---|---|
   | Load Codex Pet (slug)… | 输入 codex-pets 站上的 pet slug (如 `frieren` / `furina`) 自动下载 sprite atlas |
   | Recent | 已经下载过的角色 (multi-gif 目录 / codex sprite / 单 GIF) |
   | State | 手动切 9 个动作 (idle/waving/running-*/jumping/failed/waiting/review) |
   | Size / Playback speed | 尺寸 96-320px、播放速度 25-200% |
   | Follow mouse | 打开就跟着鼠标跑 |
   | Reminders → Configure… | 编辑提醒时长/文案/触发动作 |
   | Chat → Open chat… / LLM settings… | 打开对话框 / 配置 LLM |
   | Quit | 退出 |

---

## LLM 聊天

### 零配置 (推荐)

如果本机已装 `claude` (Claude Code) 或 `codex` CLI 并登录过,程序会自动探测,右键 → Chat → LLM settings 里对应 provider 会显示 **"CLI 已安装 / 已登录"** 且 "使用本机 CLI 登录" 复选框默认勾选。这时 **不用填 API key**,请求直接走本机 CLI (`claude -p …` / `codex exec …`),复用你订阅的 subscription。

### DeepSeek 或想用 API key

右键 → Chat → LLM settings…,选 provider,填 api_key。默认 model:
- claude → `claude-sonnet-4-6`
- codex → `gpt-4o-mini` (基础 URL `https://api.openai.com/v1`,可换成任何 OpenAI 兼容端点)
- deepseek → `deepseek-chat`

### 修改人设

同一个 dialog 底部 "System prompt" 定义了苏酱的语气 (默认: 温柔活泼 60 字内)。改成你自己想要的口气就行。

---

## 提醒

### 手动触发一次

右键 → Reminders → Show now: 起立走动 / 喝水 — 立即弹气泡。气泡从苏酱嘴边浮出并抖动,永不自动关闭,点右上 `×` 或右键气泡关掉。关掉后苏酱从 waving 回到 idle。

### 定时自动触发 (工作日)

装 launchd 定时任务:

```bash
cd launchd
./install.sh install
```

- 周一到周五触发 (`holidays` package 自动排除中国法定节假日)
- 10:00 / 11:00 / 14:00 / 15:00 / 16:00 / 17:00 / 18:00 触发
- 午休 12/13 点不打扰
- 偶数点喝水,奇数点起立
- 触发时**如果宠物没跑**,自动 `subprocess.Popen(...)` 拉起,新进程和 launchd 完全解耦,launchd 退出宠物照常跑

管理命令:
```bash
./install.sh status     # 查看当前是否 loaded + 最近日志
./install.sh uninstall  # 卸载定时任务
```

日志: `/tmp/desktop-pet-reminder.log` 和 `.err`

### 定制提醒内容

右键 → Reminders → Configure…,可视化编辑:
- 每条提醒的启用/间隔/首次延迟/触发动作 (waving/jumping/…)
- 每条提醒的文案 (多行,每次弹一条,顺序轮换)
- 全局气泡自动隐藏开关 (默认关,你必须手点 × 才关)

---

## 资源包

`data/gif-pets/<slug>/<state>.gif` — 一只宠物是一个目录,里面 9 个状态 GIF 文件。文件名必须严格对应:

```
idle.gif           # 待机
waving.gif         # 挥手 (提醒时默认动作)
running.gif        # 走
running-right.gif  # 向右跑 (跟随鼠标向右时用)
running-left.gif   # 向左跑 (跟随鼠标向左时用)
jumping.gif        # 跳跃
waiting.gif        # 等待
failed.gif         # 失败
review.gif         # 观察
```

不全也行 — 有几个 state 就用几个,菜单里没有的 state 会灰掉。

`data/codex-pets/<slug>/spritesheet.webp` — 从 codex-pets 站抓的 sprite atlas 图集,配 `pet.json` 用。cell 大小固定 192×208,九行状态,程序按行切帧循环。

---

## 文件结构

```
desktop-pet/
├── pet.py                  # 入口
├── pet_window.py           # 主窗口 + 菜单 + 拖动 / 跟随 / 状态管理
├── sprite_atlas.py         # sprite atlas 切帧动画
├── gif_pet.py              # 多状态 GIF 目录动画
├── gif_manager.py          # 单 GIF 导入 / 下载
├── codex_fetcher.py        # 从 codex-pets 站下载 sprite atlas
├── bubble.py               # 强提醒气泡 (带抖动 + × 按钮)
├── reminders.py            # 提醒调度器 + 默认文案
├── reminders_dialog.py     # 提醒可视化配置
├── chat_window.py          # LLM 对话框
├── chat_settings_dialog.py # LLM 可视化配置
├── llm_client.py           # HTTP + CLI 双通道 LLM 客户端
├── auth_detect.py          # 检测本机 claude / codex CLI 登录
├── holidays_check.py       # 工作日 / 工作时段判断
├── launch_or_remind.py     # launchd 触发的定时脚本
├── macos_bridge.py         # PyObjC 桥 (穿透全屏、隐藏 Dock)
├── config.py               # 配置持久化 (data/config.json)
├── requirements.txt
├── launchd/
│   ├── com.desktop-pet.reminder.plist.template
│   └── install.sh          # install / uninstall / status
└── data/                   # 资源 + 用户配置 (config.json 已 gitignore)
    ├── config.json         # 你的运行时配置 (不进 git)
    ├── gif-pets/           # 多状态 GIF 宠物
    └── codex-pets/         # sprite atlas 宠物
```

---

## 常见问题

**Q: 点终端 / 切别的 App,苏酱就不见了?**
A: 已经修好了。用了 `NSWindow.hidesOnDeactivate = NO` + 移除 `Qt.Tool` flag。如果还遇到,右键 → Always on top 是打勾状态吗?

**Q: 启动没窗口?**
A: 检查项目内 `data/config.json` 的 `pet_path` 是否指向存在的文件/目录。删掉这个字段或整个 config.json,重启会自动选默认宠物。

**Q: 想彻底不用 Dock 图标?**
A: 已经是了。`macos_bridge.hide_dock_icon()` 在启动第一时间调,activationPolicy 直接切成 `.accessory`,连 Cmd+Tab 都不出现。

**Q: LLM 请求慢 / 报错?**
A: 用本机 CLI 模式时,首次响应可能几秒 (启动 CLI 进程 + 认证 + 请求)。API key 模式对 Claude 官方 API 一般 <2s。看错误提示 provider 名 + 具体错误,通常是 api_key 空或 URL 拼错。

**Q: 提醒气泡关不掉?**
A: 点右上 `×` 或右键气泡关掉。或右键宠物 → Reminders → Configure → 勾 "气泡自动隐藏" 恢复旧行为。

**Q: 想换宠物?**
A: 右键 → Load Codex Pet (slug)…,输入 codex-pets.net 上的 slug,比如 `frieren`、`furina`、`bocchi`。或者把 9 张状态 GIF 放到 `data/gif-pets/<你想叫的名字>/` 下,重启就出现在 Recent 里。

---

## Snooze 暂停

苏酱身上右键 → **Snooze (退出并静音)** 有 4 个选项:

| 选项 | 行为 |
|---|---|
| 今天不再弹出 | 直接静默今天,明天自动恢复,无需二次确认 |
| 3 / 7 天不再弹出 | 弹出确认框,内含 `resume.command` 路径,确认后立即静默并退出 |
| 自定义天数… | 输入 1-90 天,同样带确认 |

**恢复方式**:
1. **随时立即恢复** — Finder 双击项目根目录里的 `resume.command`,或终端跑 `./resume.command`
2. **等第 N+1 天** — 自动恢复
3. **删文件** — `rm data/suspended_until.txt` (在项目根目录里)
4. **打开宠物** — 如果处在暂停期间宠物已经启动,右键 Snooze 菜单里会显示"当前暂停至 YYYY-MM-DD (点击立即恢复)"

(暂停确认框弹出时会显示当前安装位置的 `resume.command` 完整路径,直接复制粘贴到终端也能跑。)

暂停期间:
- launchd 定时任务照跑但立刻早退,不弹提醒
- 手动启动宠物可以,但不会自动弹提醒 / 不会弹鼓励语
- 手动右键 → Reminders → Show now: xxx 还是能触发 (你主动的操作不受静默约束)

---

## 路线图

- [x] 从嘴里"吹气球"的入场动画 (充气 → 抖动 → 变形成对话框)
- [x] 头对齐的定位 (不是画面中心)
- [x] 鼓励语头顶飘字
- [x] Snooze / 一键恢复
- [ ] Windows 版本 (Task Scheduler + tasklist)
- [ ] 更多默认宠物

---

## 致谢

- Sprite atlas 素材来自 [codex-pets.net](https://codex-pets.net) 社区贡献
- Hoshimachi Suisei (星街彗星) © Cover Corp / hololive
- PyQt5 / PyObjC / holidays 生态

MIT License · 仅供学习使用
