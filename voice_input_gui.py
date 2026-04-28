#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from voice_config import DEFAULTS, ENV_PATH, PROJECT_DIR, masked_secret, parse_env, write_env
from voice_usage import USAGE_PATH, format_minutes, monthly_summary


RUN_AZURE = PROJECT_DIR / "run-azure-voice-input.sh"
INSTALL_SHORTCUTS = PROJECT_DIR / "install-shortcuts.sh"
TERMINAL_BINDING_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
    "azure-voice-input-terminal/"
)
GUI_BINDING_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
    "azure-voice-input-gui/"
)


class CommandThread(QThread):
    finished_with_output = Signal(int, str, str)

    def __init__(self, command: list[str], timeout: int | None = None) -> None:
        super().__init__()
        self.command = command
        self.timeout = timeout

    def run(self) -> None:
        try:
            result = subprocess.run(
                self.command,
                cwd=PROJECT_DIR,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
            self.finished_with_output.emit(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            self.finished_with_output.emit(124, stdout, stderr or "Command timed out.")
        except Exception as exc:  # noqa: BLE001 - show GUI diagnostics instead of crashing.
            self.finished_with_output.emit(1, "", str(exc))


def command_text(command: list[str]) -> str:
    return " ".join(command)


def run_text(command: list[str], timeout: int = 4) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker: CommandThread | None = None
        self.setWindowTitle("Azure 语音输入")
        self.resize(980, 720)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_overview_tab()
        self._build_azure_tab()
        self._build_shortcut_tab()
        self._build_quota_tab()
        self._build_diagnostics_tab()
        self._build_guide_tab()

        self.load_settings()
        self.refresh_all()

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.status_box = QGroupBox("状态")
        status_layout = QGridLayout(self.status_box)
        self.azure_status = QLabel()
        self.inject_status = QLabel()
        self.shortcut_status = QLabel()
        self.quota_status = QLabel()
        status_layout.addWidget(QLabel("Azure 配置"), 0, 0)
        status_layout.addWidget(self.azure_status, 0, 1)
        status_layout.addWidget(QLabel("注入链路"), 1, 0)
        status_layout.addWidget(self.inject_status, 1, 1)
        status_layout.addWidget(QLabel("快捷键"), 2, 0)
        status_layout.addWidget(self.shortcut_status, 2, 1)
        status_layout.addWidget(QLabel("本地额度估算"), 3, 0)
        status_layout.addWidget(self.quota_status, 3, 1)
        layout.addWidget(self.status_box)

        actions = QHBoxLayout()
        self.test_button = QPushButton("测试 Azure 转写")
        self.test_button.clicked.connect(self.test_transcription)
        self.install_button = QPushButton("安装/更新快捷键")
        self.install_button.clicked.connect(self.install_shortcuts)
        self.refresh_button = QPushButton("刷新状态")
        self.refresh_button.clicked.connect(self.refresh_all)
        actions.addWidget(self.test_button)
        actions.addWidget(self.install_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.overview_log = QPlainTextEdit()
        self.overview_log.setReadOnly(True)
        self.overview_log.setPlaceholderText("测试结果和安装输出会显示在这里。")
        layout.addWidget(self.overview_log, 1)

        self.tabs.addTab(tab, "概览")

    def _build_azure_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox("Azure Speech 配置")
        form = QFormLayout(form_box)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key = QCheckBox("显示 Key")
        self.show_key.toggled.connect(
            lambda checked: self.key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input, 1)
        key_row.addWidget(self.show_key)

        self.region_input = QLineEdit()
        self.endpoint_input = QLineEdit()
        self.language_input = QLineEdit()
        self.initial_silence_input = QLineEdit()
        self.end_silence_input = QLineEdit()
        self.max_seconds_input = QLineEdit()
        self.free_tier_input = QLineEdit()

        form.addRow("Speech Key", key_row)
        form.addRow("Region", self.region_input)
        form.addRow("Endpoint（可选）", self.endpoint_input)
        form.addRow("识别语言", self.language_input)
        form.addRow("起始静音超时 ms（可选）", self.initial_silence_input)
        form.addRow("句尾静音 ms", self.end_silence_input)
        form.addRow("单次最长秒数", self.max_seconds_input)
        form.addRow("免费层参考秒数", self.free_tier_input)
        layout.addWidget(form_box)

        buttons = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(lambda: self.save_settings(show_message=True))
        open_env_button = QPushButton("打开配置文件位置")
        open_env_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(PROJECT_DIR))))
        buttons.addWidget(save_button)
        buttons.addWidget(open_env_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        note = QLabel(
            "配置写入项目内 .env；该文件已被 git 忽略。Endpoint 通常不用填，Region 和 Key 必须来自同一个 Azure Speech 资源。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

        self.tabs.addTab(tab, "Azure")

    def _build_shortcut_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox("GNOME 快捷键")
        form = QFormLayout(form_box)
        self.terminal_shortcut_input = QLineEdit()
        self.gui_shortcut_input = QLineEdit()
        form.addRow("终端输入", self.terminal_shortcut_input)
        form.addRow("普通输入框", self.gui_shortcut_input)
        layout.addWidget(form_box)

        buttons = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(lambda: self.save_settings(show_message=True))
        install_button = QPushButton("安装/更新 GNOME 快捷键")
        install_button.clicked.connect(self.install_shortcuts)
        buttons.addWidget(save_button)
        buttons.addWidget(install_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        help_text = QTextBrowser()
        help_text.setMarkdown(
            """
常用写法：

```text
<Control><Alt>space
<Control><Alt>slash
<Super>space
```

GNOME 自定义快捷键通常不可靠区分左 Shift 和右 Shift。不要使用裸 `Shift+/`，它是正常输入 `?` 的按键组合。
"""
        )
        layout.addWidget(help_text, 1)
        self.tabs.addTab(tab, "快捷键")

    def _build_quota_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.quota_title = QLabel()
        self.quota_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.quota_bar = QProgressBar()
        self.quota_detail = QLabel()
        self.quota_detail.setWordWrap(True)

        layout.addWidget(self.quota_title)
        layout.addWidget(self.quota_bar)
        layout.addWidget(self.quota_detail)

        buttons = QHBoxLayout()
        refresh_button = QPushButton("刷新额度估算")
        refresh_button.clicked.connect(self.refresh_quota)
        open_usage_button = QPushButton("打开用量文件位置")
        open_usage_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(USAGE_PATH.parent))))
        buttons.addWidget(refresh_button)
        buttons.addWidget(open_usage_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        explanation = QTextBrowser()
        explanation.setMarkdown(
            """
当前额度页是**本地估算**：工具会记录每次 Azure 识别耗时，并按免费层参考秒数估算本月剩余量。

它不会读取 Azure 官方账单，也无法知道你是否在其他程序里使用了同一个 Speech 资源。后续可以接入 Azure Cost Management 或 Budget API 做官方同步，但通常需要额外 Azure 权限，而且账单数据会有延迟。
"""
        )
        layout.addWidget(explanation, 1)
        self.tabs.addTab(tab, "额度")

    def _build_diagnostics_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        buttons = QHBoxLayout()
        run_button = QPushButton("运行诊断")
        run_button.clicked.connect(self.refresh_diagnostics)
        buttons.addWidget(run_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.diagnostics_output = QPlainTextEdit()
        self.diagnostics_output.setReadOnly(True)
        layout.addWidget(self.diagnostics_output, 1)
        self.tabs.addTab(tab, "诊断")

    def _build_guide_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        guide.setMarkdown(
            """
# Azure Speech 开通教程

1. 打开 Azure 免费账号入口：<https://azure.microsoft.com/free>
2. 开通 Azure 订阅。创建 Speech 资源前，订阅下拉框必须有可选项。
3. 创建语音服务直达入口：<https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices>
4. 创建时选择 `Free F0` 定价层，区域建议 `eastasia`、`southeastasia` 或 `japaneast`。
5. 创建完成后进入资源，打开“密钥和终结点 / Keys and Endpoint”。
6. 将 `KEY 1` 填入本工具的 Speech Key，将资源 `Location/Region` 填入 Region。

常见问题：

- 订阅为空：需要先创建 Azure 免费订阅，或检查右上角目录是否选错。
- 认证失败：Key 和 Region 必须来自同一个 Speech 资源。
- 转写不结束：调小“句尾静音 ms”，例如 700。
- 普通输入框注入失败：确认使用的是 `Ctrl+Alt+/`，并且目标输入框已经聚焦。
"""
        )
        layout.addWidget(guide, 1)

        buttons = QHBoxLayout()
        for text, url in [
            ("Azure 免费账号", "https://azure.microsoft.com/free"),
            ("创建 Speech 资源", "https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices"),
            ("Speech 价格", "https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, link=url: QDesktopServices.openUrl(QUrl(link)))
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.tabs.addTab(tab, "教程")

    def append_log(self, text: str) -> None:
        self.overview_log.appendPlainText(text.rstrip())

    def load_settings(self) -> None:
        env = parse_env()
        self.key_input.setText(env.get("AZURE_SPEECH_KEY", ""))
        self.region_input.setText(env.get("AZURE_SPEECH_REGION", ""))
        self.endpoint_input.setText(env.get("AZURE_SPEECH_ENDPOINT", ""))
        self.language_input.setText(env.get("AZURE_SPEECH_LANGUAGE", DEFAULTS["AZURE_SPEECH_LANGUAGE"]))
        self.initial_silence_input.setText(env.get("AZURE_SPEECH_INITIAL_SILENCE_MS", ""))
        self.end_silence_input.setText(env.get("AZURE_SPEECH_END_SILENCE_MS", DEFAULTS["AZURE_SPEECH_END_SILENCE_MS"]))
        self.max_seconds_input.setText(env.get("VOICE_INPUT_MAX_SECONDS", DEFAULTS["VOICE_INPUT_MAX_SECONDS"]))
        self.free_tier_input.setText(env.get("AZURE_SPEECH_FREE_TIER_SECONDS", DEFAULTS["AZURE_SPEECH_FREE_TIER_SECONDS"]))
        self.terminal_shortcut_input.setText(env.get("VOICE_INPUT_TERMINAL_SHORTCUT", DEFAULTS["VOICE_INPUT_TERMINAL_SHORTCUT"]))
        self.gui_shortcut_input.setText(env.get("VOICE_INPUT_GUI_SHORTCUT", DEFAULTS["VOICE_INPUT_GUI_SHORTCUT"]))

    def current_settings(self) -> dict[str, str]:
        return {
            "AZURE_SPEECH_KEY": self.key_input.text(),
            "AZURE_SPEECH_REGION": self.region_input.text(),
            "AZURE_SPEECH_ENDPOINT": self.endpoint_input.text(),
            "AZURE_SPEECH_LANGUAGE": self.language_input.text(),
            "AZURE_SPEECH_INITIAL_SILENCE_MS": self.initial_silence_input.text(),
            "AZURE_SPEECH_END_SILENCE_MS": self.end_silence_input.text(),
            "VOICE_INPUT_MAX_SECONDS": self.max_seconds_input.text(),
            "AZURE_SPEECH_FREE_TIER_SECONDS": self.free_tier_input.text(),
            "VOICE_INPUT_TERMINAL_SHORTCUT": self.terminal_shortcut_input.text(),
            "VOICE_INPUT_GUI_SHORTCUT": self.gui_shortcut_input.text(),
        }

    def save_settings(self, *, show_message: bool = False) -> None:
        write_env(self.current_settings())
        self.append_log(f"Saved configuration to {ENV_PATH}")
        self.refresh_all()
        if show_message:
            QMessageBox.information(self, "Azure 语音输入", "配置已保存。")

    def refresh_all(self) -> None:
        self.load_settings()
        self.refresh_quota()
        self.refresh_diagnostics()
        env = parse_env()
        azure_ready = bool(env.get("AZURE_SPEECH_KEY")) and bool(
            env.get("AZURE_SPEECH_REGION") or env.get("AZURE_SPEECH_ENDPOINT")
        )
        self.azure_status.setText(
            f"{'已配置' if azure_ready else '未完整配置'}，Key: {masked_secret(env.get('AZURE_SPEECH_KEY', ''))}"
        )

        code, ydotoold, _ = run_text(["systemctl", "--user", "is-active", "ydotoold.service"])
        uinput_ok = Path("/dev/uinput").exists()
        self.inject_status.setText(
            f"ydotoold: {'active' if code == 0 and ydotoold == 'active' else ydotoold or 'unknown'}，/dev/uinput: {'存在' if uinput_ok else '缺失'}"
        )
        terminal_binding = self.get_binding(TERMINAL_BINDING_PATH)
        gui_binding = self.get_binding(GUI_BINDING_PATH)
        self.shortcut_status.setText(
            f"终端 {terminal_binding or '未安装'}；普通输入框 {gui_binding or '未安装'}"
        )

    def refresh_quota(self) -> None:
        summary = monthly_summary()
        self.quota_title.setText(f"{summary['month']} 本地额度估算")
        self.quota_bar.setValue(int(round(summary["percent"])))
        self.quota_detail.setText(
            "本地记录 "
            f"{summary['records']} 次；已用 {format_minutes(summary['used_seconds'])}；"
            f"参考额度 {format_minutes(summary['free_seconds'])}；"
            f"估算剩余 {format_minutes(summary['remaining_seconds'])}。\n"
            f"用量文件：{summary['path']}"
        )
        self.quota_status.setText(
            f"已用 {format_minutes(summary['used_seconds'])} / {format_minutes(summary['free_seconds'])}"
        )

    def get_binding(self, path: str) -> str:
        code, stdout, _ = run_text(
            [
                "gsettings",
                "get",
                f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}",
                "binding",
            ]
        )
        if code != 0:
            return ""
        return stdout.strip("'")

    def refresh_diagnostics(self) -> None:
        lines = []
        checks = [
            ("project", ["pwd"]),
            ("ydotool", ["bash", "-lc", "command -v ydotool || true"]),
            ("ydotoold", ["systemctl", "--user", "is-active", "ydotoold.service"]),
            ("uinput", ["bash", "-lc", "ls -l /dev/uinput 2>&1 || true"]),
            ("wl-copy", ["bash", "-lc", "command -v wl-copy || true"]),
            ("microphone", ["bash", "-lc", "pactl info 2>/dev/null | sed -n '1,18p' || true"]),
            ("custom shortcuts", ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]),
        ]
        for label, command in checks:
            code, stdout, stderr = run_text(command)
            lines.append(f"## {label} (exit {code})")
            lines.append(stdout or stderr or "(no output)")
            lines.append("")
        self.diagnostics_output.setPlainText("\n".join(lines))

    def test_transcription(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Azure 语音输入", "已有测试正在运行。")
            return
        self.save_settings()
        self.append_log("Starting Azure print-only transcription test. Speak now.")
        command = [
            str(RUN_AZURE),
            "--print-only",
            "--end-silence-ms",
            self.end_silence_input.text() or DEFAULTS["AZURE_SPEECH_END_SILENCE_MS"],
        ]
        self.worker = CommandThread(command, timeout=int(self.max_seconds_input.text() or "45") + 10)
        self.worker.finished_with_output.connect(self.handle_test_finished)
        self.test_button.setEnabled(False)
        self.worker.start()

    def handle_test_finished(self, code: int, stdout: str, stderr: str) -> None:
        self.test_button.setEnabled(True)
        self.append_log(f"$ {command_text([str(RUN_AZURE), '--print-only'])}")
        if stdout.strip():
            self.append_log(stdout.strip())
        if stderr.strip():
            self.append_log(stderr.strip())
        self.append_log(f"exit={code}\n")
        self.refresh_quota()
        if code == 0:
            QMessageBox.information(self, "Azure 语音输入", "测试完成。")
        else:
            QMessageBox.warning(self, "Azure 语音输入", "测试失败，请查看概览日志。")

    def install_shortcuts(self) -> None:
        self.save_settings()
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Azure 语音输入", "已有任务正在运行。")
            return
        self.worker = CommandThread([str(INSTALL_SHORTCUTS)], timeout=15)
        self.worker.finished_with_output.connect(self.handle_install_finished)
        self.install_button.setEnabled(False)
        self.worker.start()

    def handle_install_finished(self, code: int, stdout: str, stderr: str) -> None:
        self.install_button.setEnabled(True)
        if stdout.strip():
            self.append_log(stdout.strip())
        if stderr.strip():
            self.append_log(stderr.strip())
        self.append_log(f"install exit={code}\n")
        self.refresh_all()
        if code == 0:
            QMessageBox.information(self, "Azure 语音输入", "快捷键已安装/更新。")
        else:
            QMessageBox.warning(self, "Azure 语音输入", "快捷键安装失败，请查看概览日志。")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Azure 语音输入")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
