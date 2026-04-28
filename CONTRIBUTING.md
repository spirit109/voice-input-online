# Contributing

感谢你愿意改进 Voice Input Online。这个项目目前以 Ubuntu GNOME Wayland
为主要目标，欢迎围绕稳定性、可安装性、平台适配和文档体验提交改进。

## 开发环境

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

运行基础检查：

```bash
.venv/bin/python -m py_compile azure_voice_input.py voice_config.py voice_i18n.py voice_input_gui.py voice_usage.py
bash -n inject-text.sh install-shortcuts.sh run-azure-voice-input.sh run-gui.sh voice-input-once.sh
```

## 提交建议

- 不要提交 `.env`、Azure key、日志截图中的密钥或本地 `.state/` 数据。
- 尽量保持跨目录路径可移植，不要写死个人 home 目录。
- 涉及桌面入口或快捷键时，请说明测试过的桌面环境和显示协议。
- 涉及界面文案时，请同时检查中文和英文字符串。

## 适配其他平台

Azure Speech 识别部分是 Python 层，理论上更容易复用。文本注入、全局快捷键、
通知和桌面入口是平台相关部分，适配 Windows、macOS、KDE、X11 或 WSL 时请把
平台边界写清楚。
