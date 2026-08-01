import shutil
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from videotrans.configure.config import app_cfg, params, tr
from videotrans.util.help_misc import show_error
from videotrans.util.production_project import (
    STAGES, episode_name, import_original_video, project_video, read_states, require_stage,
    scaffold_project, update_stage, validate_project,
)
from videotrans.util.production_markdown import (
    export_recognition_srt, export_translation_task, import_recognition_srt, import_translation_srt,
    set_document_status,
)
from videotrans.task.production_dubbing import (
    compose_project_video, confirm_calibrated_subtitle, run_project_dubbing,
)
from videotrans.task.production_stages import run_project_recognition, run_project_translation


class ProjectTaskThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        work = None
        try:
            result = self.callback(self._cancelled.is_set)
            if isinstance(result, tuple) and result and isinstance(result[0], Path):
                work = result[0]
                result = result[-1]
            self.done.emit(str(result))
        except Exception:
            self.failed.emit(traceback.format_exc())
        finally:
            if work:
                shutil.rmtree(work, ignore_errors=True)


class ProductionProjectWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task = None
        self.setWindowTitle(tr("Production project"))
        self.resize(900, 640)
        body, layout = QWidget(self), QVBoxLayout()
        body.setLayout(layout)

        project_row = QHBoxLayout()
        self.project = QLineEdit()
        self.project.setReadOnly(True)
        self.open_project, self.new_project = QPushButton(tr("Open project")), QPushButton(tr("New project"))
        project_row.addWidget(QLabel(tr("Project directory")))
        project_row.addWidget(self.project, 1)
        project_row.addWidget(self.open_project)
        project_row.addWidget(self.new_project)
        layout.addLayout(project_row)

        episode_row = QHBoxLayout()
        self.episode = QComboBox()
        self.episode.setEditable(True)
        self.episode.setMinimumWidth(130)
        self.add_episode, self.open_wiki = QPushButton(tr("Add episode")), QPushButton(tr("Open project Wiki"))
        episode_row.addWidget(QLabel(tr("Current episode")))
        episode_row.addWidget(self.episode)
        episode_row.addWidget(self.add_episode)
        episode_row.addStretch(1)
        episode_row.addWidget(self.open_wiki)
        layout.addLayout(episode_row)

        self.table = None
        self.stage_pages = QStackedWidget()
        self.task_buttons = []
        self.stage_block_reasons = {}

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("Stage"), tr("Status"), tr("Output"), tr("Action")])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 90)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMaximumHeight(260)
        self.table.cellClicked.connect(self.select_stage)
        self.table.cellDoubleClicked.connect(self.open_stage_output)
        layout.addWidget(self.table)

        self.stage_label = QLabel()
        layout.addWidget(self.stage_label)

        def add_page(*buttons):
            page, row = QWidget(), QHBoxLayout()
            page.setLayout(row)
            for button in buttons:
                row.addWidget(button)
            row.addStretch(1)
            self.stage_pages.addWidget(page)

        self.select_video = QPushButton(tr("Select a Video"))
        self.start_recognition = QPushButton(tr("Recognize Chinese transcript"))
        self.import_recognition = QPushButton(tr("Import recognition SRT"))
        self.export_recognition = QPushButton(tr("Export confirmed Chinese SRT"))
        add_page(self.select_video, self.start_recognition, self.import_recognition, self.export_recognition)

        self.start_translation = QPushButton(tr("Generate drama translation"))
        self.import_translation = QPushButton(tr("Import translated SRT"))
        self.export_translation = QPushButton(tr("Export dubbing task files"))
        add_page(self.start_translation, self.import_translation, self.export_translation)

        self.start_dubbing = QPushButton(tr("Generate English dubbing"))
        add_page(self.start_dubbing)
        self.confirm_subtitle = QPushButton(tr("Confirm calibrated SRT"))
        add_page(self.confirm_subtitle)
        self.compose = QPushButton(tr("Compose final video"))
        add_page(self.compose)
        self.task_buttons.extend((
            self.start_recognition, self.start_translation, self.start_dubbing, self.compose))

        layout.addWidget(self.stage_pages)

        self.cancel_task = QPushButton(tr("Cancel current task"))
        self.cancel_task.setDisabled(True)
        bottom = QHBoxLayout()
        self.message = QLabel(tr("Each stage runs independently and stops for confirmation"))
        bottom.addWidget(self.message, 1)
        bottom.addWidget(self.cancel_task)
        layout.addLayout(bottom)
        self.setCentralWidget(body)

        self.open_project.clicked.connect(self.select_project)
        self.new_project.clicked.connect(self.create_project)
        self.add_episode.clicked.connect(self.create_episode)
        self.open_wiki.clicked.connect(self.show_wiki)
        self.select_video.clicked.connect(self.select_source_video)
        self.start_recognition.clicked.connect(self.start_project_recognition)
        self.start_translation.clicked.connect(self.start_project_translation)
        self.import_recognition.clicked.connect(self.load_recognition_srt)
        self.export_recognition.clicked.connect(self.save_recognition_srt)
        self.import_translation.clicked.connect(self.load_translation_srt)
        self.export_translation.clicked.connect(self.save_translation_task)
        self.start_dubbing.clicked.connect(self.start_project_dubbing)
        self.confirm_subtitle.clicked.connect(self.confirm_project_subtitle)
        self.compose.clicked.connect(self.start_composition)
        self.cancel_task.clicked.connect(self.cancel_current_task)
        self.episode.currentTextChanged.connect(lambda _text: self.refresh())

        saved = params.get("production_project", "")
        if saved and (Path(saved) / "wiki").is_dir():
            try:
                self.load_project(saved)
            except ValueError:
                pass
        self.select_stage(0)
        self._refresh_stage_buttons({})

    def _selected_episode(self):
        return episode_name(self.episode.currentText() or "1")

    def select_project(self):
        folder = QFileDialog.getExistingDirectory(self, tr("Open project"), self.project.text())
        if not folder:
            return
        try:
            validate_project(folder)
        except (ValueError, OSError) as error:
            show_error(str(error))
            return
        self.load_project(folder)

    def create_project(self):
        folder = QFileDialog.getExistingDirectory(self, tr("New project"), self.project.text())
        if folder:
            scaffold_project(folder, 1)
            self.load_project(folder)

    def load_project(self, folder):
        root = validate_project(folder)
        self.project.setText(root.as_posix())
        params["production_project"] = root.as_posix()
        params.save()
        current = self.episode.currentText()
        self.episode.blockSignals(True)
        self.episode.clear()
        episodes = sorted(path.name for path in (root / "wiki/集数").glob("第*集"))
        self.episode.addItems(episodes or ["第01集"])
        if current in episodes:
            self.episode.setCurrentText(current)
        self.episode.blockSignals(False)
        processing = [
            (folder.name, stage)
            for folder in sorted((root / "wiki/集数").glob("第*集"))
            for stage, (status, _updated) in read_states(root, folder.name).items()
            if status == "处理中"
        ]
        if processing and QMessageBox.question(
                self, tr("Interrupted project tasks found"),
                tr("Mark interrupted tasks as failed and allow retry?"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            for episode, stage in processing:
                update_stage(root, episode, stage, "失败")
        self.refresh()

    def create_episode(self):
        if not self.project.text():
            show_error(tr("Open or create a project first"))
            return
        try:
            _, episode = scaffold_project(self.project.text(), self.episode.currentText())
        except ValueError as error:
            show_error(str(error))
            return
        self.load_project(self.project.text())
        self.episode.setCurrentText(episode)

    def refresh(self):
        if not self.project.text():
            return
        try:
            episode = self._selected_episode()
        except ValueError:
            return
        if self.table is None:
            return
        states = read_states(self.project.text(), episode)
        self.table.setRowCount(len(STAGES))
        for row, (stage, output) in enumerate(STAGES):
            values = stage, states.get(stage, (tr("Not started"), "-"))[0], output.format(episode=episode)
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            button = QPushButton(tr("Work on stage"))
            button.clicked.connect(lambda _checked=False, row=row: self.select_stage(row))
            self.table.setCellWidget(row, 3, button)
        self._refresh_stage_buttons(states)
        self.select_stage(self.stage_pages.currentIndex())

    def _refresh_stage_buttons(self, states):
        status = lambda stage: states.get(stage, ("未开始", "-"))[0]
        project = Path(self.project.text()) if self.project.text() else None
        episode = self._selected_episode() if project else ""
        video = project_video(project, episode) if project else None
        rules = (
            (0, self.start_recognition, bool(video and video.is_file()), "请先选择原视频"),
            (1, self.start_translation, status("中文识别") == "已确认", "请先校对并确认中文识别"),
            (2, self.start_dubbing, status("剧情翻译与轮次") == "已确认", "请先校对并确认剧情翻译与轮次"),
            (3, self.confirm_subtitle, status("英文克隆配音") == "已完成", "请先完成英文克隆配音"),
            (4, self.compose, status("英文克隆配音") == "已完成" and
             status("配音字幕校准") == "已确认", "请先完成配音并确认校准字幕"),
        )
        self.stage_block_reasons = {}
        busy = self.task is not None and self.task.isRunning()
        for row, button, ready, reason in rules:
            button.setDisabled(busy or not ready)
            button.setToolTip("" if ready else reason)
            if not ready:
                self.stage_block_reasons[row] = reason
        self.export_recognition.setDisabled(status("中文识别") != "待校对")
        self.import_translation.setDisabled(status("中文识别") != "已确认")
        self.export_translation.setDisabled(status("剧情翻译与轮次") != "待校对")

    def select_stage(self, row, _column=0):
        if self.table is None or row < 0 or row >= len(STAGES):
            return
        self.table.setCurrentCell(row, 0)
        self.stage_pages.setCurrentIndex(row)
        reason = self.stage_block_reasons.get(row)
        suffix = f" · {reason}" if reason else ""
        self.stage_label.setText(f"{tr('Current stage')}: {STAGES[row][0]}{suffix}")

    def show_wiki(self):
        if self.project.text():
            QDesktopServices.openUrl(QUrl.fromLocalFile((Path(self.project.text()) / "wiki/index.md").as_posix()))

    def open_stage_output(self, row, _column):
        if not self.project.text() or row < 0 or row >= len(STAGES):
            return
        episode = self._selected_episode()
        names = {
            "中文识别": "中文识别.md", "剧情翻译与轮次": "翻译与轮次.md",
            "英文克隆配音": "英文配音.md", "配音字幕校准": "字幕校准与合成.md",
            "最终合成": "字幕校准与合成.md",
        }
        stage = STAGES[row][0]
        path = Path(self.project.text()) / "wiki/集数" / episode / names.get(stage, "状态.md")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path.as_posix()))

    def select_source_video(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Select a Video"), params.get("last_opendir", ""), "Video (*.mp4 *.mov *.mkv *.avi *.webm)")
        if filename:
            try:
                project, episode = self._project_context()
                source = import_original_video(project, episode, filename)
                params["last_opendir"] = str(Path(filename).parent)
                params.save()
                self.message.setText(f"{tr('Completed')}: {source}")
                self.refresh()
            except Exception as error:
                show_error(str(error))

    def _project_context(self):
        if not self.project.text():
            raise ValueError(tr("Open or create a project first"))
        return Path(self.project.text()), self._selected_episode()

    def load_recognition_srt(self):
        filename, _ = QFileDialog.getOpenFileName(self, tr("Import recognition SRT"), "", "SRT (*.srt)")
        if not filename:
            return
        try:
            project, episode = self._project_context()
            import_recognition_srt(project, episode, filename)
            self.message.setText(tr("Recognition SRT imported; edit Chinese transcript in Wiki"))
            self.refresh()
        except Exception as error:
            show_error(str(error))

    def save_recognition_srt(self):
        try:
            project, episode = self._project_context()
            output = export_recognition_srt(project, episode)
            set_document_status(project / "wiki/集数" / episode / "中文识别.md", "已确认")
            update_stage(project, episode, "中文识别", "已确认", invalidate_downstream=True)
            self.message.setText(f"{tr('Completed')}: {output}")
            self.refresh()
        except Exception as error:
            show_error(str(error))

    def load_translation_srt(self):
        filename, _ = QFileDialog.getOpenFileName(self, tr("Import translated SRT"), "", "SRT (*.srt)")
        if not filename:
            return
        try:
            project, episode = self._project_context()
            require_stage(project, episode, "中文识别", ("已确认",))
            import_translation_srt(project, episode, filename)
            self.message.setText(tr("Translated SRT imported; edit roles, emotions and turns in Wiki"))
            self.refresh()
        except Exception as error:
            show_error(str(error))

    def save_translation_task(self):
        try:
            project, episode = self._project_context()
            output = export_translation_task(project, episode)
            set_document_status(project / "wiki/集数" / episode / "翻译与轮次.md", "已确认")
            update_stage(project, episode, "剧情翻译与轮次", "已确认", invalidate_downstream=True)
            self.message.setText(f"{tr('Completed')}: {output.parent}")
            self.refresh()
        except Exception as error:
            show_error(str(error))

    def _set_task_buttons(self, disabled):
        for button in self.task_buttons:
            button.setDisabled(disabled)
        self.cancel_task.setDisabled(not disabled)

    def start_project_recognition(self):
        try:
            project, episode = self._project_context()
            video = project_video(project, episode)
            if not video.is_file():
                raise FileNotFoundError(f"请先选择原视频：{video}")
        except Exception as error:
            show_error(str(error))
            return
        self._set_task_buttons(True)
        self.message.setText(tr("Recognizing Chinese transcript"))
        self.task = ProjectTaskThread(
            lambda cancelled: run_project_recognition(project, episode, video, cancelled), self)
        self.task.done.connect(self.project_task_done)
        self.task.failed.connect(lambda message: self.project_task_failed("中文识别", message))
        self.task.start()

    def start_project_translation(self):
        try:
            project, episode = self._project_context()
            require_stage(project, episode, "中文识别", ("已确认",))
        except Exception as error:
            show_error(str(error))
            return
        self._set_task_buttons(True)
        self.message.setText(tr("Generating drama translation"))
        self.task = ProjectTaskThread(
            lambda cancelled: run_project_translation(project, episode, cancelled), self)
        self.task.done.connect(self.project_task_done)
        self.task.failed.connect(lambda message: self.project_task_failed("剧情翻译与轮次", message))
        self.task.start()

    def start_project_dubbing(self):
        try:
            project, episode = self._project_context()
            video = project_video(project, episode)
            if not video.is_file():
                raise FileNotFoundError(f"缺少项目原视频：{video}")
            require_stage(project, episode, "剧情翻译与轮次", ("已确认",))
        except Exception as error:
            show_error(str(error))
            return
        self._set_task_buttons(True)
        self.message.setText(tr("Generating English dubbing"))
        self.task = ProjectTaskThread(
            lambda cancelled: run_project_dubbing(project, episode, video, cancelled), self)
        self.task.done.connect(self.project_task_done)
        self.task.failed.connect(lambda message: self.project_task_failed("英文克隆配音", message))
        self.task.start()

    def confirm_project_subtitle(self):
        filename, _ = QFileDialog.getOpenFileName(self, tr("Confirm calibrated SRT"), "", "SRT (*.srt)")
        if not filename:
            return
        try:
            project, episode = self._project_context()
            output = confirm_calibrated_subtitle(project, episode, filename)
            self.message.setText(f"{tr('Completed')}: {output}")
            self.refresh()
        except Exception as error:
            show_error(str(error))

    def start_composition(self):
        try:
            project, episode = self._project_context()
            require_stage(project, episode, "英文克隆配音", ("已完成",))
            require_stage(project, episode, "配音字幕校准", ("已确认",))
        except Exception as error:
            show_error(str(error))
            return
        self._set_task_buttons(True)
        self.message.setText(tr("Composing final video"))
        self.task = ProjectTaskThread(
            lambda cancelled: compose_project_video(project, episode, cancelled), self)
        self.task.done.connect(self.project_task_done)
        self.task.failed.connect(lambda message: self.project_task_failed("最终合成", message))
        self.task.start()

    def project_task_done(self, output):
        self._set_task_buttons(False)
        self.message.setText(f"{tr('Completed')}: {output}")
        self.refresh()

    def cancel_current_task(self):
        if self.task and self.task.isRunning():
            self.task.cancel()
            self.cancel_task.setDisabled(True)
            self.message.setText(tr("Cancellation requested; confirmed outputs will be preserved"))

    def project_task_failed(self, stage, message):
        try:
            project, episode = self._project_context()
            update_stage(project, episode, stage, "失败")
        except Exception:
            pass
        self._set_task_buttons(False)
        self.message.setText(tr("Failed"))
        self.refresh()
        show_error(message)

def openwin():
    window = ProductionProjectWindow()
    app_cfg.child_forms["fn_production_project"] = window
    window.show()
