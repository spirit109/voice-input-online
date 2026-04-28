#!/usr/bin/env python3

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QKeySequenceEdit,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from voice_config import DEFAULTS, ENV_PATH, PROJECT_DIR, masked_secret, parse_env, write_env
from voice_i18n import LANGUAGE_NAMES, normalize_language, tr
from voice_usage import USAGE_PATH, monthly_summary


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


KEY_TO_GNOME = {
    " ": "space",
    "Space": "space",
    "/": "slash",
    "\\": "backslash",
    ".": "period",
    ",": "comma",
    "-": "minus",
    "=": "equal",
    "'": "apostrophe",
    ";": "semicolon",
    "[": "bracketleft",
    "]": "bracketright",
    "`": "grave",
    "Esc": "Escape",
    "Del": "Delete",
    "PgUp": "Page_Up",
    "PgDown": "Page_Down",
}
GNOME_TO_KEY = {value.lower(): key for key, value in KEY_TO_GNOME.items()}
GNOME_TO_KEY.update(
    {
        "space": "Space",
        "slash": "/",
        "period": ".",
        "comma": ",",
        "minus": "-",
        "equal": "=",
        "semicolon": ";",
        "apostrophe": "'",
        "escape": "Esc",
        "page_up": "PgUp",
        "page_down": "PgDown",
    }
)
MODIFIER_ORDER = ["Control", "Shift", "Alt", "Super"]
MODIFIER_ALIASES = {
    "ctrl": "Control",
    "control": "Control",
    "primary": "Control",
    "shift": "Shift",
    "alt": "Alt",
    "meta": "Super",
    "super": "Super",
}


def split_gnome_accel(accel: str) -> tuple[tuple[str, ...], str]:
    accel = accel.strip().strip("'\"")
    modifiers = tuple(
        MODIFIER_ALIASES.get(item.lower(), item)
        for item in re.findall(r"<([^>]+)>", accel)
    )
    key = re.sub(r"<[^>]+>", "", accel).strip()
    ordered = tuple(mod for mod in MODIFIER_ORDER if mod in modifiers)
    return ordered, key


def normalize_accel(accel: str) -> str:
    modifiers, key = split_gnome_accel(accel)
    return "+".join([*modifiers, key.lower()])


def has_required_modifier(accel: str) -> bool:
    modifiers, _ = split_gnome_accel(accel)
    return any(modifier in modifiers for modifier in ("Control", "Alt", "Super"))


def gnome_accel_to_qt(accel: str) -> QKeySequence:
    modifiers, key = split_gnome_accel(accel)
    qt_mods = []
    for modifier in modifiers:
        if modifier == "Control":
            qt_mods.append("Ctrl")
        elif modifier == "Super":
            qt_mods.append("Meta")
        else:
            qt_mods.append(modifier)
    qt_key = GNOME_TO_KEY.get(key.lower(), key)
    return QKeySequence("+".join([*qt_mods, qt_key]))


def qt_sequence_to_gnome(sequence: QKeySequence) -> str:
    text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    first = text.split(",")[0].strip()
    if not first:
        return ""
    parts = [part.strip() for part in first.split("+") if part.strip()]
    if not parts:
        return ""
    key = parts[-1]
    modifiers = []
    for part in parts[:-1]:
        mapped = MODIFIER_ALIASES.get(part.lower())
        if mapped:
            modifiers.append(mapped)
    ordered = [modifier for modifier in MODIFIER_ORDER if modifier in modifiers]
    gnome_key = KEY_TO_GNOME.get(key, key)
    if len(gnome_key) == 1 and gnome_key.isalpha():
        gnome_key = gnome_key.lower()
    return "".join(f"<{modifier}>" for modifier in ordered) + gnome_key


def parse_gsettings_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("@as "):
        value = value[4:].strip()
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item)]
    return []


def collect_gnome_shortcuts() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for schema in [
        "org.gnome.desktop.wm.keybindings",
        "org.gnome.settings-daemon.plugins.media-keys",
    ]:
        code, stdout, _ = run_text(["gsettings", "list-recursively", schema], timeout=6)
        if code != 0:
            continue
        for line in stdout.splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) != 3:
                continue
            schema_name, key_name, value = parts
            for binding in parse_gsettings_list(value):
                entries.append(
                    {
                        "binding": binding,
                        "source": f"{schema_name}.{key_name}",
                        "name": key_name,
                        "path": "",
                    }
                )

    code, stdout, _ = run_text(
        ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"],
        timeout=4,
    )
    if code != 0:
        return entries

    for path in parse_gsettings_list(stdout):
        schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
        _, name, _ = run_text(["gsettings", "get", schema, "name"], timeout=4)
        _, command, _ = run_text(["gsettings", "get", schema, "command"], timeout=4)
        _, binding, _ = run_text(["gsettings", "get", schema, "binding"], timeout=4)
        binding = binding.strip("'")
        if binding:
            entries.append(
                {
                    "binding": binding,
                    "source": path,
                    "name": name.strip("'") or path,
                    "command": command.strip("'"),
                    "path": path,
                }
            )
    return entries


def shortcut_conflicts(accel: str, *, ignore_path: str = "") -> list[dict[str, str]]:
    normalized = normalize_accel(accel)
    conflicts = []
    for entry in collect_gnome_shortcuts():
        if ignore_path and entry.get("path") == ignore_path:
            continue
        if normalize_accel(entry["binding"]) == normalized:
            conflicts.append(entry)
    return conflicts


SYSTEM_BINDING_NAMES_ZH = {
    "close": "关闭窗口",
    "terminal": "打开终端",
    "show-desktop": "显示桌面",
    "switch-applications": "切换应用",
    "switch-windows": "切换窗口",
    "activate-window-menu": "窗口菜单",
    "logout": "注销",
    "screensaver": "锁屏",
    "magnifier": "放大镜",
    "screenreader": "屏幕阅读器",
}


def shortcut_display_name(entry: dict[str, str], language: str) -> str:
    name = entry.get("name") or entry.get("source") or ""
    if language == "zh-CN":
        return SYSTEM_BINDING_NAMES_ZH.get(name, name)
    return name


def suggest_shortcuts(preferred: list[str], *, avoid: set[str]) -> list[str]:
    suggestions = []
    normalized_avoid = {normalize_accel(item) for item in avoid if item}
    for accel in preferred:
        if normalize_accel(accel) in normalized_avoid:
            continue
        if shortcut_conflicts(accel):
            continue
        suggestions.append(accel)
        if len(suggestions) >= 3:
            break
    return suggestions


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker: CommandThread | None = None
        self.ui_language = normalize_language(parse_env().get("VOICE_INPUT_UI_LANGUAGE"))
        self.setWindowTitle(self.t("app_name"))
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

    def t(self, key: str, **kwargs) -> str:
        return tr(key, self.ui_language, **kwargs)

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.status_box = QGroupBox(self.t("status"))
        status_layout = QGridLayout(self.status_box)
        self.azure_status = QLabel()
        self.inject_status = QLabel()
        self.shortcut_status = QLabel()
        self.quota_status = QLabel()
        self.ui_language_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.ui_language_combo.addItem(name, code)
        self.ui_language_combo.setCurrentIndex(self.ui_language_combo.findData(self.ui_language))
        self.ui_language_combo.currentIndexChanged.connect(self.change_ui_language)
        status_layout.addWidget(QLabel(self.t("ui_language")), 0, 0)
        status_layout.addWidget(self.ui_language_combo, 0, 1)
        status_layout.addWidget(QLabel(self.t("azure_config")), 1, 0)
        status_layout.addWidget(self.azure_status, 1, 1)
        status_layout.addWidget(QLabel(self.t("injection")), 2, 0)
        status_layout.addWidget(self.inject_status, 2, 1)
        status_layout.addWidget(QLabel(self.t("shortcuts")), 3, 0)
        status_layout.addWidget(self.shortcut_status, 3, 1)
        status_layout.addWidget(QLabel(self.t("local_quota")), 4, 0)
        status_layout.addWidget(self.quota_status, 4, 1)
        layout.addWidget(self.status_box)

        actions = QHBoxLayout()
        self.test_button = QPushButton(self.t("test_transcription"))
        self.test_button.clicked.connect(self.test_transcription)
        self.install_button = QPushButton(self.t("install_shortcuts"))
        self.install_button.clicked.connect(self.install_shortcuts)
        self.refresh_button = QPushButton(self.t("refresh_status"))
        self.refresh_button.clicked.connect(self.refresh_all)
        actions.addWidget(self.test_button)
        actions.addWidget(self.install_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.overview_log = QPlainTextEdit()
        self.overview_log.setReadOnly(True)
        self.overview_log.setPlaceholderText(self.t("overview_log_placeholder"))
        layout.addWidget(self.overview_log, 1)

        self.tabs.addTab(tab, self.t("overview"))

    def _build_azure_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox(self.t("speech_config"))
        form = QFormLayout(form_box)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key = QCheckBox(self.t("show_key"))
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

        form.addRow(self.t("speech_key"), key_row)
        form.addRow(self.t("region"), self.region_input)
        form.addRow(self.t("endpoint_optional"), self.endpoint_input)
        form.addRow(self.t("recognition_language"), self.language_input)
        form.addRow(self.t("initial_silence_ms"), self.initial_silence_input)
        form.addRow(self.t("end_silence_ms"), self.end_silence_input)
        form.addRow(self.t("max_seconds"), self.max_seconds_input)
        form.addRow(self.t("free_tier_seconds"), self.free_tier_input)
        layout.addWidget(form_box)

        buttons = QHBoxLayout()
        save_button = QPushButton(self.t("save_config"))
        save_button.clicked.connect(lambda: self.save_settings(show_message=True))
        open_env_button = QPushButton(self.t("open_config_folder"))
        open_env_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(PROJECT_DIR))))
        buttons.addWidget(save_button)
        buttons.addWidget(open_env_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        note = QLabel(
            self.t("azure_note")
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

        self.tabs.addTab(tab, self.t("azure"))

    def _build_shortcut_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox(self.t("gnome_shortcuts"))
        form = QFormLayout(form_box)
        self.terminal_shortcut_input = QKeySequenceEdit()
        self.gui_shortcut_input = QKeySequenceEdit()
        for editor in (self.terminal_shortcut_input, self.gui_shortcut_input):
            editor.setClearButtonEnabled(True)
            if hasattr(editor, "setMaximumSequenceLength"):
                editor.setMaximumSequenceLength(1)
            editor.keySequenceChanged.connect(self.check_shortcut_conflicts)
        form.addRow(self.t("terminal_input"), self.terminal_shortcut_input)
        form.addRow(self.t("gui_input"), self.gui_shortcut_input)
        layout.addWidget(form_box)

        self.terminal_shortcut_status = QLabel()
        self.terminal_shortcut_status.setWordWrap(True)
        self.gui_shortcut_status = QLabel()
        self.gui_shortcut_status.setWordWrap(True)
        layout.addWidget(self.terminal_shortcut_status)
        layout.addWidget(self.gui_shortcut_status)

        buttons = QHBoxLayout()
        save_button = QPushButton(self.t("save_config"))
        save_button.clicked.connect(lambda: self.save_settings(show_message=True, validate_shortcuts=True))
        check_button = QPushButton(self.t("check_conflicts"))
        check_button.clicked.connect(lambda: self.check_shortcut_conflicts(show_message=True))
        install_button = QPushButton(self.t("install_shortcuts"))
        install_button.clicked.connect(self.install_shortcuts)
        buttons.addWidget(save_button)
        buttons.addWidget(check_button)
        buttons.addWidget(install_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        help_text = QTextBrowser()
        help_text.setMarkdown(
            self.t("shortcut_help")
        )
        layout.addWidget(help_text, 1)
        self.tabs.addTab(tab, self.t("shortcuts"))

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
        refresh_button = QPushButton(self.t("refresh_quota"))
        refresh_button.clicked.connect(self.refresh_quota)
        open_usage_button = QPushButton(self.t("open_usage_folder"))
        open_usage_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(USAGE_PATH.parent))))
        buttons.addWidget(refresh_button)
        buttons.addWidget(open_usage_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        explanation = QTextBrowser()
        explanation.setMarkdown(
            self.t("quota_explanation")
        )
        layout.addWidget(explanation, 1)
        self.tabs.addTab(tab, self.t("quota"))

    def _build_diagnostics_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        buttons = QHBoxLayout()
        run_button = QPushButton(self.t("run_diagnostics"))
        run_button.clicked.connect(self.refresh_diagnostics)
        buttons.addWidget(run_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.diagnostics_output = QPlainTextEdit()
        self.diagnostics_output.setReadOnly(True)
        layout.addWidget(self.diagnostics_output, 1)
        self.tabs.addTab(tab, self.t("diagnostics"))

    def _build_guide_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        guide.setMarkdown(
            self.t("guide_markdown")
        )
        layout.addWidget(guide, 1)

        buttons = QHBoxLayout()
        for text, url in [
            (self.t("azure_free_account"), "https://azure.microsoft.com/free"),
            (self.t("create_speech_resource"), "https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices"),
            (self.t("speech_pricing"), "https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, link=url: QDesktopServices.openUrl(QUrl(link)))
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.tabs.addTab(tab, self.t("guide"))

    def append_log(self, text: str) -> None:
        self.overview_log.appendPlainText(text.rstrip())

    def rebuild_tabs(self) -> None:
        self.tabs.clear()
        self.setWindowTitle(self.t("app_name"))
        self._build_overview_tab()
        self._build_azure_tab()
        self._build_shortcut_tab()
        self._build_quota_tab()
        self._build_diagnostics_tab()
        self._build_guide_tab()
        self.load_settings()
        self.refresh_all()

    def change_ui_language(self) -> None:
        selected = self.ui_language_combo.currentData()
        selected = normalize_language(selected)
        if selected == self.ui_language:
            return
        settings = self.current_settings()
        settings["VOICE_INPUT_UI_LANGUAGE"] = selected
        write_env(settings)
        self.ui_language = selected
        self.rebuild_tabs()

    def load_settings(self) -> None:
        env = parse_env()
        self.ui_language = normalize_language(env.get("VOICE_INPUT_UI_LANGUAGE"))
        self.key_input.setText(env.get("AZURE_SPEECH_KEY", ""))
        self.region_input.setText(env.get("AZURE_SPEECH_REGION", ""))
        self.endpoint_input.setText(env.get("AZURE_SPEECH_ENDPOINT", ""))
        self.language_input.setText(env.get("AZURE_SPEECH_LANGUAGE", DEFAULTS["AZURE_SPEECH_LANGUAGE"]))
        self.initial_silence_input.setText(env.get("AZURE_SPEECH_INITIAL_SILENCE_MS", ""))
        self.end_silence_input.setText(env.get("AZURE_SPEECH_END_SILENCE_MS", DEFAULTS["AZURE_SPEECH_END_SILENCE_MS"]))
        self.max_seconds_input.setText(env.get("VOICE_INPUT_MAX_SECONDS", DEFAULTS["VOICE_INPUT_MAX_SECONDS"]))
        self.free_tier_input.setText(env.get("AZURE_SPEECH_FREE_TIER_SECONDS", DEFAULTS["AZURE_SPEECH_FREE_TIER_SECONDS"]))
        self.terminal_shortcut_input.setKeySequence(
            gnome_accel_to_qt(env.get("VOICE_INPUT_TERMINAL_SHORTCUT", DEFAULTS["VOICE_INPUT_TERMINAL_SHORTCUT"]))
        )
        self.gui_shortcut_input.setKeySequence(
            gnome_accel_to_qt(env.get("VOICE_INPUT_GUI_SHORTCUT", DEFAULTS["VOICE_INPUT_GUI_SHORTCUT"]))
        )
        self.check_shortcut_conflicts()

    def current_settings(self) -> dict[str, str]:
        return {
            "AZURE_SPEECH_KEY": self.key_input.text(),
            "AZURE_SPEECH_REGION": self.region_input.text(),
            "AZURE_SPEECH_ENDPOINT": self.endpoint_input.text(),
            "AZURE_SPEECH_LANGUAGE": self.language_input.text(),
            "AZURE_SPEECH_INITIAL_SILENCE_MS": self.initial_silence_input.text(),
            "AZURE_SPEECH_END_SILENCE_MS": self.end_silence_input.text(),
            "VOICE_INPUT_MAX_SECONDS": self.max_seconds_input.text(),
            "VOICE_INPUT_UI_LANGUAGE": self.ui_language,
            "AZURE_SPEECH_FREE_TIER_SECONDS": self.free_tier_input.text(),
            "VOICE_INPUT_TERMINAL_SHORTCUT": qt_sequence_to_gnome(self.terminal_shortcut_input.keySequence()),
            "VOICE_INPUT_GUI_SHORTCUT": qt_sequence_to_gnome(self.gui_shortcut_input.keySequence()),
        }

    def save_settings(self, *, show_message: bool = False, validate_shortcuts: bool = False) -> bool:
        if validate_shortcuts and not self.check_shortcut_conflicts(show_message=True):
            return False
        write_env(self.current_settings())
        self.append_log(self.t("saved_to", path=ENV_PATH))
        self.refresh_all()
        if show_message:
            QMessageBox.information(self, self.t("app_name"), self.t("saved_config"))
        return True

    def preferred_shortcuts(self, mode: str) -> list[str]:
        if mode == "terminal":
            return [
                "<Control><Alt>space",
                "<Super>space",
                "<Control><Alt>F8",
                "<Shift><Control><Alt>space",
                "<Control><Alt>period",
                "<Control><Alt>comma",
            ]
        return [
            "<Control><Alt>slash",
            "<Super>slash",
            "<Control><Alt>F9",
            "<Shift><Control><Alt>slash",
            "<Control><Alt>period",
            "<Control><Alt>semicolon",
        ]

    def check_shortcut_conflicts(self, *_, show_message: bool = False) -> bool:
        terminal_accel = qt_sequence_to_gnome(self.terminal_shortcut_input.keySequence())
        gui_accel = qt_sequence_to_gnome(self.gui_shortcut_input.keySequence())
        issues: list[str] = []

        def status_for(
            label: QLabel,
            title: str,
            accel: str,
            ignore_path: str,
            other_accel: str,
            suggestions: list[str],
        ) -> None:
            local_issues = []
            if not accel:
                local_issues.append(self.t("shortcut_empty"))
            elif not has_required_modifier(accel):
                local_issues.append(self.t("shortcut_modifier_warning"))

            conflicts = shortcut_conflicts(accel, ignore_path=ignore_path) if accel else []
            if accel and other_accel and normalize_accel(accel) == normalize_accel(other_accel):
                local_issues.append(self.t("shortcut_same_as_other"))
            for conflict in conflicts[:4]:
                local_issues.append(
                    self.t(
                        "shortcut_conflicts_with",
                        name=shortcut_display_name(conflict, self.ui_language),
                        binding=conflict["binding"],
                    )
                )

            if local_issues:
                available = suggest_shortcuts(
                    suggestions,
                    avoid={terminal_accel, gui_accel} - {accel},
                )
                suggestion_text = (
                    self.t("shortcut_suggestion", suggestions=", ".join(available))
                    if available
                    else ""
                )
                label.setText(
                    self.t(
                        "shortcut_status_bad",
                        title=title,
                        accel=accel or self.t("not_configured"),
                        issues=" ".join(local_issues),
                        suggestion=suggestion_text,
                    )
                )
                label.setStyleSheet("color: #b00020;")
                issues.extend([f"{title}: {item}" for item in local_issues])
            else:
                label.setText(self.t("shortcut_status_good", title=title, accel=accel))
                label.setStyleSheet("color: #0b6b2b;")

        status_for(
            self.terminal_shortcut_status,
            self.t("terminal_input"),
            terminal_accel,
            TERMINAL_BINDING_PATH,
            gui_accel,
            self.preferred_shortcuts("terminal"),
        )
        status_for(
            self.gui_shortcut_status,
            self.t("gui_input"),
            gui_accel,
            GUI_BINDING_PATH,
            terminal_accel,
            self.preferred_shortcuts("gui"),
        )

        if issues and show_message:
            QMessageBox.warning(
                self,
                self.t("shortcut_conflict_title"),
                self.t("shortcut_cannot_install", issues="\n".join(issues[:8])),
            )
        elif show_message:
            QMessageBox.information(self, self.t("shortcut_check_title"), self.t("shortcut_no_conflict"))
        return not issues

    def refresh_all(self) -> None:
        self.load_settings()
        self.refresh_quota()
        self.refresh_diagnostics()
        env = parse_env()
        azure_ready = bool(env.get("AZURE_SPEECH_KEY")) and bool(
            env.get("AZURE_SPEECH_REGION") or env.get("AZURE_SPEECH_ENDPOINT")
        )
        self.azure_status.setText(
            f"{self.t('configured') if azure_ready else self.t('incomplete_config')}: {self.t('speech_key')} {masked_secret(env.get('AZURE_SPEECH_KEY', ''))}"
        )

        code, ydotoold, _ = run_text(["systemctl", "--user", "is-active", "ydotoold.service"])
        uinput_ok = Path("/dev/uinput").exists()
        self.inject_status.setText(
            f"ydotoold: {'active' if code == 0 and ydotoold == 'active' else ydotoold or 'unknown'}; /dev/uinput: {self.t('exists') if uinput_ok else self.t('missing')}"
        )
        terminal_binding = self.get_binding(TERMINAL_BINDING_PATH)
        gui_binding = self.get_binding(GUI_BINDING_PATH)
        self.shortcut_status.setText(
            f"{self.t('terminal_input')}: {terminal_binding or self.t('not_installed')}; {self.t('gui_input')}: {gui_binding or self.t('not_installed')}"
        )

    def fmt_minutes(self, seconds: float) -> str:
        return self.t("minutes", minutes=seconds / 60)

    def refresh_quota(self) -> None:
        summary = monthly_summary()
        self.quota_title.setText(self.t("month_quota", month=summary["month"]))
        self.quota_bar.setValue(int(round(summary["percent"])))
        self.quota_detail.setText(
            self.t(
                "quota_detail",
                records=summary["records"],
                used=self.fmt_minutes(summary["used_seconds"]),
                free=self.fmt_minutes(summary["free_seconds"]),
                remaining=self.fmt_minutes(summary["remaining_seconds"]),
                path=summary["path"],
            )
        )
        self.quota_status.setText(
            self.t(
                "quota_status",
                used=self.fmt_minutes(summary["used_seconds"]),
                free=self.fmt_minutes(summary["free_seconds"]),
            )
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
        if self.ui_language == "zh-CN":
            checks = [
                ("项目目录", ["pwd"]),
                ("ydotool 命令", ["bash", "-lc", "command -v ydotool || true"]),
                ("ydotoold 服务", ["systemctl", "--user", "is-active", "ydotoold.service"]),
                ("uinput 设备", ["bash", "-lc", "ls -l /dev/uinput 2>&1 || true"]),
                ("wl-copy 命令", ["bash", "-lc", "command -v wl-copy || true"]),
                ("麦克风", ["bash", "-lc", "pactl info 2>/dev/null | sed -n '1,18p' || true"]),
                ("自定义快捷键", ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]),
            ]
        else:
            checks = [
                ("Project Directory", ["pwd"]),
                ("ydotool Command", ["bash", "-lc", "command -v ydotool || true"]),
                ("ydotoold Service", ["systemctl", "--user", "is-active", "ydotoold.service"]),
                ("uinput Device", ["bash", "-lc", "ls -l /dev/uinput 2>&1 || true"]),
                ("wl-copy Command", ["bash", "-lc", "command -v wl-copy || true"]),
                ("Microphone", ["bash", "-lc", "pactl info 2>/dev/null | sed -n '1,18p' || true"]),
                ("Custom Shortcuts", ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"]),
            ]
        for label, command in checks:
            code, stdout, stderr = run_text(command)
            lines.append(f"## {label} (exit {code})")
            lines.append(stdout or stderr or "(no output)")
            lines.append("")
        self.diagnostics_output.setPlainText("\n".join(lines))

    def test_transcription(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, self.t("app_name"), self.t("test_running"))
            return
        self.save_settings()
        self.append_log(self.t("test_start"))
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
            QMessageBox.information(self, self.t("app_name"), self.t("test_done"))
        else:
            QMessageBox.warning(self, self.t("app_name"), self.t("test_failed"))

    def install_shortcuts(self) -> None:
        if not self.save_settings(validate_shortcuts=True):
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, self.t("app_name"), self.t("task_running"))
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
            QMessageBox.information(self, self.t("app_name"), self.t("shortcuts_installed"))
        else:
            QMessageBox.warning(self, self.t("app_name"), self.t("shortcuts_failed"))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(tr("app_name", parse_env().get("VOICE_INPUT_UI_LANGUAGE")))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
