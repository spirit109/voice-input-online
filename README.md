# Voice Input Online

[简体中文](README.md) | [English](README.en-US.md)

Voice Input Online 是一个面向 Ubuntu GNOME Wayland 的桌面语音输入工具。
它使用 Azure Speech 从默认麦克风识别一次语音，然后把识别结果输入到当前终端
或普通图形界面输入框。

设置界面提供 Azure 密钥配置、快捷键设置、冲突检查、本地额度估算、诊断和内置
开通教程。界面语言可以在简体中文和英文之间切换。

## 功能

- 使用 Azure Speech 从默认麦克风进行单次语音识别。
- 支持向 GNOME Terminal、浏览器、编辑器和其他输入框注入文本。
- PySide6 图形设置界面，覆盖密钥、语言、快捷键、额度估算、诊断和 Azure 指引。
- 支持按键识别式快捷键录入，并在保存前检查 GNOME 快捷键冲突。
- 严格的界面语言切换：简体中文或英文。
- 本地使用量估算记录在 `.state/`，与 Azure 官方账单分离。
- 默认保护密钥：`.env` 被 git 忽略，`.env.example` 只放占位内容。

## 平台状态

当前实现主要支持 Ubuntu GNOME Wayland。文本注入层使用 `ydotool` 通过
`/dev/uinput` 工作，因为 `xdotool` 对原生 Wayland 应用不可靠。

Windows、WSL、macOS、KDE 和 X11 暂不是主要支持目标。Azure 识别层是 Python，
相对容易复用；文本注入、全局快捷键、通知和桌面入口需要按平台适配。

## 快速开始

在 Ubuntu 安装系统依赖：

```bash
sudo apt install python3-venv ydotool wl-clipboard
```

克隆仓库并安装 Python 依赖：

```bash
git clone https://github.com/spirit109/voice-input-online.git
cd voice-input-online
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

创建本地配置：

```bash
cp .env.example .env
```

打开设置界面：

```bash
./run-gui.sh
```

在 GUI 的 Azure 页面填写 Speech key 和 region，然后到诊断页面测试识别和输入。

## Azure Speech 配置

在 Azure 门户创建 Azure AI Speech 资源，然后把一个 key 和资源 region 填入工具。
配置说明见 [中文](docs/azure-setup.zh-CN.md) 或
[English](docs/azure-setup.en-US.md)。

最小 `.env` 示例：

```bash
AZURE_SPEECH_KEY=replace-with-your-azure-speech-key
AZURE_SPEECH_REGION=eastasia
AZURE_SPEECH_LANGUAGE=zh-CN
```

不要提交真实 `.env`。本仓库默认忽略该文件。

## 文本注入

识别一次语音并输入到 GNOME Terminal：

```bash
./run-azure-voice-input.sh --mode terminal
```

识别并输入到普通图形界面输入框：

```bash
./run-azure-voice-input.sh --mode gui
```

只打印识别结果，不执行输入：

```bash
./run-azure-voice-input.sh --print-only
```

直接把文本送入注入层：

```bash
printf 'hello world' | ./inject-text.sh --mode gui
```

模式说明：

- `terminal`：复制到 Wayland 剪贴板，然后按 `Ctrl+Shift+V`。
- `gui`：复制到 Wayland 剪贴板，然后按 `Ctrl+V`。
- `type`：通过 `ydotool` 逐字输入，速度较慢，但不依赖剪贴板。

默认不会在输入后按 Enter。如果希望终端命令立即执行，添加 `--append-newline`。

## 桌面入口和快捷键

安装 GNOME 应用启动器、桌面入口和默认快捷键：

```bash
./install-shortcuts.sh
```

默认快捷键：

```text
Ctrl+Alt+Space -> 终端模式
Ctrl+Alt+/     -> 普通输入框模式
```

安装脚本会从 `packaging/linux/*.desktop.in` 按当前 clone 路径动态生成 `.desktop`
文件，所以用户可以把仓库克隆到任意目录。

在 GUI 的快捷键页面，点击快捷键输入框后直接按下想要的组合键。应用会检查现有
GNOME 系统快捷键和自定义快捷键，如果冲突会给出替代建议。

GNOME 自定义快捷键通常不区分左右 Shift。避免使用单独的 `Shift+/`，因为它也是
正常输入 `?` 的组合键。

## 额度估算

每次成功识别都会把近似本地时长记录到：

```text
.state/usage.json
```

GUI 的额度页会根据 `.env` 中的 `AZURE_SPEECH_FREE_TIER_SECONDS` 显示本月本地
估算使用量。这只是本工具的本地估算，不是 Azure 官方账单或官方剩余额度。

## 项目结构

```text
.
├── azure_voice_input.py          # Azure Speech 识别命令行入口
├── voice_input_gui.py            # PySide6 设置界面
├── voice_config.py               # .env 读取和写入
├── voice_i18n.py                 # 中文/英文界面文案
├── voice_usage.py                # 本地使用量估算
├── inject-text.sh                # Wayland 文本注入助手
├── voice-input-once.sh           # 适合快捷键调用的单次识别包装脚本
├── run-azure-voice-input.sh      # 加载 .env 并运行识别
├── run-gui.sh                    # 启动设置界面
├── install-shortcuts.sh          # 安装 GNOME 启动器和快捷键
├── packaging/linux/*.desktop.in  # 桌面入口模板
├── requirements.txt              # Python 依赖
└── .env.example                  # 安全配置模板
```

## 开发检查

```bash
.venv/bin/python -m py_compile azure_voice_input.py voice_config.py voice_i18n.py voice_input_gui.py voice_usage.py
bash -n inject-text.sh install-shortcuts.sh run-azure-voice-input.sh run-gui.sh voice-input-once.sh
```

如果安装了 `desktop-file-validate`，可以验证渲染后的桌面模板：

```bash
mkdir -p .state/desktop-validate
for file in packaging/linux/*.desktop.in; do
  out=".state/desktop-validate/$(basename "${file%.in}")"
  sed "s|@PROJECT_DIR@|$PWD|g" "$file" > "$out"
  desktop-file-validate "$out"
done
```

## 安全

- 真实 Azure key 只放在 `.env`。
- `.env`、`.venv/`、`.state/` 和 Python 缓存文件都被 git 忽略。
- 如果 Azure key 被提交、粘贴到 issue、日志、截图或聊天记录中，请立即轮换密钥。

## 许可证

MIT License。见 [LICENSE](LICENSE)。
