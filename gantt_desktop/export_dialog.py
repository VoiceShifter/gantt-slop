"""System-styled export configuration with a shared vector diagram preview."""
from __future__ import annotations

import math
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from .dialogs import EditorDialog
from .exporting import (
    PAPERS,
    SCALES,
    ExportDocument,
    ExportOptions,
    ExportSource,
    export_file,
)

if TYPE_CHECKING:
    from .controller import Controller

FORMATS_RU = {"pdf": ("PDF", "PDF (*.pdf)"), "png": ("PNG", "PNG (*.png)"),
              "xlsx": ("Excel (выбранные поля)", "Excel (*.xlsx)"), "xml": ("MS Project XML", "MS Project XML (*.xml)"),
              "csv": ("CSV (выбранные поля)", "CSV (*.csv)"), "ganttpro_csv": ("GanttPRO CSV · 23 поля", "CSV (*.csv)"),
              "ganttpro_xlsx": ("GanttPRO Excel · 23 поля", "Excel (*.xlsx)")}
FORMATS_EN = {"pdf": ("PDF", "PDF (*.pdf)"), "png": ("PNG", "PNG (*.png)"),
              "xlsx": ("Excel (selected fields)", "Excel (*.xlsx)"), "xml": ("MS Project XML", "MS Project XML (*.xml)"),
              "csv": ("CSV (selected fields)", "CSV (*.csv)"), "ganttpro_csv": ("GanttPRO CSV · 23 fields", "CSV (*.csv)"),
              "ganttpro_xlsx": ("GanttPRO Excel · 23 fields", "Excel (*.xlsx)")}
FORMATS = FORMATS_RU


class DiagramItem(QGraphicsItem):
    def __init__(self, document: ExportDocument):
        super().__init__()
        self.document = document

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.document.width, self.document.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        self.document.paint(painter)


class ExportPreview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.document: ExportDocument | None = None
        self.item_: DiagramItem | None = None
        self.setObjectName("exportPreview")

    def set_document(self, document: ExportDocument | None) -> None:
        self.document = document
        self.scene_.clear()
        self.item_ = None
        if document is not None:
            self.item_ = DiagramItem(document)
            self.scene_.addItem(self.item_)
        self.fit_width()

    def fit_width(self) -> None:
        self.resetTransform()
        if self.document is not None:
            factor = min(1.0, max(1, self.viewport().width()-16)/self.document.width)
            self.scale(factor, factor)
            self.verticalScrollBar().setValue(0)
            self.horizontalScrollBar().setValue(0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit_width()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.scale(1.2 if event.angleDelta().y() > 0 else 1/1.2, 1.2 if event.angleDelta().y() > 0 else 1/1.2)
            event.accept()
        else:
            super().wheelEvent(event)


class ExportDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "exportDialog", "Export Chart" if is_en else "Экспорт диаграммы")
        self.resize(1240, 780)
        self.source: ExportSource | None = None
        self.document: ExportDocument | None = None
        self._preparing = False
        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        fit = QPushButton("Fit to width" if is_en else "Вписать по ширине")
        fit.setObjectName("fitExportPreview")
        fit.setAutoDefault(False)
        toolbar.addWidget(fit)
        toolbar.addWidget(QLabel("Ctrl+Wheel — zoom; drag — scroll" if is_en else "Ctrl+колесо — масштаб; перетаскивание — прокрутка"))
        left_layout.addLayout(toolbar)
        self.preview = ExportPreview()
        fit.clicked.connect(self.preview.fit_width)
        left_layout.addWidget(self.preview)
        self.info = QLabel()
        self.info.setObjectName("exportInfo")
        self.info.setWordWrap(True)
        left_layout.addWidget(self.info)
        splitter.addWidget(left)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        settings = QWidget()
        form = QFormLayout(settings)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.format = QComboBox()
        self.format.setObjectName("exportFormat")
        formats_map = FORMATS_EN if is_en else FORMATS_RU
        for key, (label, _filter) in formats_map.items():
            self.format.addItem(label, key)
        self.site_import = QCheckBox("Prepare for GanttPRO import wizard" if is_en else "Подготовить для мастера импорта GanttPRO")
        self.site_import.setObjectName("exportSiteImport")
        self.table_headers = QCheckBox("Header row in file" if is_en else "Строка заголовков в файле")
        self.table_headers.setObjectName("exportTableHeaders")
        self.scope = QComboBox()
        self.scope.setObjectName("exportScope")
        self.scope.addItem("Entire project" if is_en else "Весь проект", "all")
        self.scope.addItem("Current rows: filter / collapsed groups" if is_en else "Текущие строки: фильтр/свёрнутые группы", "visible")
        self.content = QComboBox()
        self.content.setObjectName("exportContent")
        for label, key in (
            (("Table and chart", "both"), ("Chart only", "chart"), ("Table only", "table"))
            if is_en
            else (("Таблица и диаграмма", "both"), ("Только диаграмма", "chart"), ("Только таблица", "table"))
        ):
            self.content.addItem(label, key)
        self.scale = QComboBox()
        self.scale.setObjectName("exportScale")
        for label, value in SCALES.items():
            self.scale.addItem(label, value)
        self.paper = QComboBox()
        self.paper.setObjectName("exportPaper")
        self.paper.addItem("Full size" if is_en else "Полный размер", "Full")
        for key in PAPERS:
            self.paper.addItem(key, key)
        self.orientation = QComboBox()
        self.orientation.setObjectName("exportOrientation")
        self.orientation.addItem("Landscape" if is_en else "Альбомная", True)
        self.orientation.addItem("Portrait" if is_en else "Книжная", False)
        self.labels = QComboBox()
        self.labels.setObjectName("exportLabels")
        for label, key in (
            (("Inside", "inside"), ("Right", "right"), ("Do not show", "none"))
            if is_en
            else (("Внутри", "inside"), ("Справа", "right"), ("Не показывать", "none"))
        ):
            self.labels.addItem(label, key)
        self.range = QCheckBox("Custom date range" if is_en else "Свой диапазон дат")
        self.range.setObjectName("exportCustomRange")
        self.start = QDateEdit()
        self.end = QDateEdit()
        for widget, name in ((self.start, "exportStart"), (self.end, "exportEnd")):
            widget.setObjectName(name)
            widget.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
            widget.setDisplayFormat("dd.MM.yyyy")
            widget.setCalendarPopup(True)
        self.links = QCheckBox("Task dependencies" if is_en else "Связи задач")
        self.today = QCheckBox("Today marker" if is_en else "Маркер текущей даты")
        self.workload = QCheckBox("Resource workload" if is_en else "Загрузка ресурсов")
        self.critical = QCheckBox("Critical path (entire project)" if is_en else "Критический путь (весь проект)")
        self.baseline = QCheckBox("Selected baseline" if is_en else "Выбранный базовый план")
        self.strike = QCheckBox("Strikethrough closed" if is_en else "Зачёркивать закрытые")
        self.fade = QCheckBox("Dim closed" if is_en else "Обесцвечивать закрытые")
        for widget, name in ((self.links, "exportLinks"), (self.today, "exportToday"),
                             (self.workload, "exportWorkload"), (self.critical, "exportCritical"), (self.baseline, "exportBaseline"), (self.strike, "exportStrike"), (self.fade, "exportFade")):
            widget.setObjectName(name)
        self.fields = QListWidget()
        self.fields.setObjectName("exportFields")
        self.fields.setMinimumHeight(190)
        for label, widget in (
            (("Format" if is_en else "Формат"), self.format), ("", self.site_import), ("", self.table_headers),
            (("Tasks" if is_en else "Задачи"), self.scope), (("Content" if is_en else "Содержание"), self.content),
            (("Time scale" if is_en else "Шкала времени"), self.scale), (("Paper size" if is_en else "Размер бумаги"), self.paper), (("Orientation" if is_en else "Ориентация"), self.orientation),
            (("Task label" if is_en else "Имя задачи"), self.labels), ("", self.range), (("Start" if is_en else "Начало"), self.start), (("Finish" if is_en else "Завершение"), self.end),
            ("", self.links), ("", self.today), ("", self.workload), ("", self.critical), ("", self.baseline), ("", self.strike), ("", self.fade),
            (("Fields" if is_en else "Поля"), self.fields)
        ):
            form.addRow(label, widget)
        self.note = QLabel(
            "Export does not modify the project. PDF fits to width and paginates by rows; preview shows the entire document. XML exports the entire project, fields map to ExtendedAttribute."
            if is_en
            else "Экспорт не меняет проект. PDF с размером бумаги вписывается по ширине и разбивается по строкам; предпросмотр — весь документ. XML — весь проект, поля переносятся через ExtendedAttribute."
        )
        self.note.setWordWrap(True)
        form.addRow(self.note)
        for combo in (self.format, self.scope, self.content, self.scale, self.paper, self.orientation, self.labels):
            combo.setMinimumContentsLength(8)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        scroll.setWidget(settings)
        scroll.setMinimumWidth(330)
        splitter.addWidget(scroll)
        splitter.setSizes([870, 350])
        self.layout_root.addWidget(splitter, 1)
        self.transfer_warning = QLabel()
        self.transfer_warning.setObjectName("ganttproExportWarning")
        self.transfer_warning.setTextFormat(Qt.TextFormat.PlainText)
        self.transfer_warning.setWordWrap(True)
        self.transfer_warning.hide()
        self.layout_root.addWidget(self.transfer_warning)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Export…" if is_en else "Экспорт…")
        self.save_button.setObjectName("saveExport")
        self.save_button.setDefault(True)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName("closeExport")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Close" if is_en else "Закрыть")
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.update_preview)
        for widget in (self.format, self.scope, self.content, self.scale, self.paper, self.orientation, self.labels):
            widget.currentIndexChanged.connect(self.schedule)
        for widget in (self.range, self.links, self.today, self.workload, self.critical, self.baseline, self.strike, self.fade,
                       self.site_import, self.table_headers):
            widget.toggled.connect(self.schedule)
        self.start.dateChanged.connect(self.schedule)
        self.end.dateChanged.connect(self.schedule)
        self.fields.itemChanged.connect(self.schedule)

    def prepare(self, context: dict) -> None:
        self._preparing = True
        self.error.hide()
        self.document = None
        self.preview.set_document(None)
        self.source = ExportSource.capture(self.controller, context)
        self.format.setCurrentIndex(max(0, self.format.findData(context.get("format", "pdf"))))
        self.site_import.setChecked(False)
        self.table_headers.setChecked(True)
        self.scope.setCurrentIndex(0)
        self.content.setCurrentIndex(0)
        self.paper.setCurrentIndex(0)
        self.orientation.setCurrentIndex(0)
        self.labels.setCurrentIndex(0)
        target = context.get("pixelsPerDay", 10)
        self.scale.setCurrentIndex(min(range(self.scale.count()), key=lambda i: abs(self.scale.itemData(i)-target)))
        self.range.setChecked(False)
        dates = [row[key].date() for row in self.source.rows for key in ("startValue", "endValue")]
        first, last = (min(dates), max(dates)) if dates else (self.source.today, self.source.today)
        self.start.setDate(QDate(first.year, first.month, first.day))
        self.end.setDate(QDate(last.year, last.month, last.day))
        self.links.setChecked(True)
        self.today.setChecked(True)
        self.workload.setChecked(bool(context.get("workload", False)))
        self.critical.setChecked(bool(context.get("critical", False)))
        self.baseline.setChecked(bool(self.source.project.active_baseline))
        self.strike.setChecked(True)
        self.fade.setChecked(True)
        self.fields.blockSignals(True)
        self.fields.clear()
        for key, column in self.source.columns.items():
            item = QListWidgetItem(column["title"], self.fields)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in self.source.default_columns else Qt.CheckState.Unchecked)
        self.fields.blockSignals(False)
        self._preparing = False
        self.update_preview()

    def schedule(self, *_args) -> None:
        if not self._preparing:
            self.timer.start()

    def options(self) -> ExportOptions:
        assert self.source is not None
        format_ = self.format.currentData()
        visual = format_ in {"png", "pdf"}
        columns = tuple(self.fields.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.fields.count())
                        if self.fields.item(i).checkState() == Qt.CheckState.Checked)
        start, end = self.start.date(), self.end.date()
        fixed = format_ in {"xml", "ganttpro_csv", "ganttpro_xlsx"}
        return ExportOptions(format=format_, scope="all" if fixed else self.scope.currentData(),
                             columns=self.source.default_columns if fixed else columns,
                             content=self.content.currentData() if visual else "table",
                             pixels_per_day=self.scale.currentData(),
                             start=date(start.year(), start.month(), start.day()) if self.range.isChecked() and not fixed else None,
                             end=date(end.year(), end.month(), end.day()) if self.range.isChecked() and not fixed else None,
                             paper=self.paper.currentData(), landscape=self.orientation.currentData(),
                             labels=self.labels.currentData(), links=self.links.isChecked(), today=self.today.isChecked(),
                             workload=self.workload.isChecked() and format_ in {"pdf", "png", "xlsx"},
                             strike_closed=self.strike.isChecked(), fade_closed=self.fade.isChecked(),
                             critical=self.critical.isChecked() and visual and self.content.currentData() != "table",
                             baseline=self.baseline.isChecked() and visual and self.content.currentData() != "table",
                             site_import=self.site_import.isChecked() and format_ in {"ganttpro_csv", "ganttpro_xlsx"},
                             table_headers=self.table_headers.isChecked())

    def update_preview(self) -> None:
        if self.source is None:
            return
        self.error.hide()
        format_ = self.format.currentData()
        visual = format_ in {"pdf", "png"}
        task_table = format_ in {"ganttpro_csv", "ganttpro_xlsx"}
        fixed = task_table or format_ == "xml"
        self.site_import.setVisible(task_table)
        self.table_headers.setVisible(task_table)
        self.table_headers.setEnabled(task_table and self.site_import.isChecked())
        for widget, value in ((self.content, "table" if not visual else self.content.currentData()),
                              (self.scope, "all" if fixed else self.scope.currentData())):
            widget.blockSignals(True)
            widget.setCurrentIndex(widget.findData(value))
            widget.blockSignals(False)
        for widget in (self.content, self.scale, self.labels, self.links, self.today, self.strike, self.fade):
            widget.setEnabled(visual)
        self.paper.setEnabled(format_ == "pdf")
        self.orientation.setEnabled(format_ == "pdf" and self.paper.currentData() != "Full")
        self.scope.setEnabled(not fixed)
        self.fields.setEnabled(not fixed)
        self.range.setEnabled(not fixed)
        self.start.setEnabled(self.range.isChecked() and not fixed)
        self.end.setEnabled(self.range.isChecked() and not fixed)
        is_en = self.controller.i18n.language == "en"
        if task_table:
            if is_en:
                self.note.setText("GanttPRO table: 23 fields; Desktop restores arrows from 'Predecessor'. "
                                  "Calendars, resource capacities/shares, baselines and other custom fields are not part of the schema: save .gantt.json. "
                                  "Wizard mode: group name also in task name, dates DD.MM.YYYY and two separate time columns HH:MM; "
                                  "map duration and effort in hours. "
                                  "On the website arrows were not restored; milestone assignments, colors, deadlines, and original authors are not transferred by this wizard. "
                                  "If the website header preview is empty, disable the header row and select 'My file does not have a header row'. "
                                  "Desktop preview headers serve as a guide even for such a file; importing it back into Desktop requires headers.")
            else:
                self.note.setText("Таблица GanttPRO: 23 поля; Desktop восстанавливает стрелки из «Предшественник». "
                                  "Календари, ёмкости/доли ресурсов, базовые планы и прочие пользовательские поля не входят в схему: сохраните .gantt.json. "
                                  "Режим мастера: имя группы также в названии задачи, даты ДД.ММ.ГГГГ и два отдельных столбца времени ЧЧ:ММ; "
                                  "длительность и трудозатраты сопоставьте в часах. "
                                  "На сайте стрелки не восстановились; назначение на веху, цвета, сроки и исходные авторы не переносятся этим мастером. "
                                  "Если предпросмотр заголовков сайта пуст, отключите строку заголовков и выберите «В моем файле нет строки с заголовками». "
                                  "Заголовки предпросмотра Desktop служат подсказкой даже для такого файла; его обратный импорт в Desktop требует заголовков.")
        elif format_ == "xml":
            if is_en:
                self.note.setText("MSPDI XML: entire project, hierarchy, dates, dependencies, calendars, resources, and assignments. "
                                  "Text/Number/Date/Flag are typed fields; complex types become text. "
                                  "Color, status, fractional progress, and active baseline name/date are named XML fields. "
                                  "Resource color, other baselines, and deleted items archive are not transferred. "
                                  "For complete project data, save .gantt.json. GanttPRO does not accept XML; MS Project import is not separately verified.")
            else:
                self.note.setText("MSPDI XML: весь проект, дерево, даты, связи, календари, ресурсы и назначения. "
                                  "Text/Number/Date/Flag — типизированные поля; сложные типы становятся текстом. "
                                  "Цвет, статус, дробный прогресс и имя/дата выбранного базового плана — именованные XML-поля. "
                                  "Не переносятся цвет ресурса, остальные базовые планы и архив удалённых элементов. "
                                  "Для полного проекта сохраните .gantt.json. GanttPRO не принимает XML; приём MS Project отдельно не подтверждён.")
        else:
            self.note.setText(
                "Export does not modify the project. PDF fits to width and paginates by rows."
                if is_en
                else "Экспорт не меняет проект. PDF вписывается по ширине и разбивается по строкам."
            )
        transfer = fixed
        self.transfer_warning.setText(self.note.text() if transfer else "")
        self.transfer_warning.setVisible(transfer)
        self.note.setVisible(not transfer)
        self.workload.setEnabled(format_ == "xlsx" or (visual and self.content.currentData() != "table"))
        self.critical.setEnabled(visual and self.content.currentData() != "table")
        self.baseline.setEnabled(visual and self.content.currentData() != "table" and bool(self.source.project.active_baseline))
        try:
            document = ExportDocument(self.source, self.options())
            tasks_word = "tasks/groups" if is_en else "задач/групп"
            detail = f"{len(document.rows)} {tasks_word} · {math.ceil(document.width)} × {math.ceil(document.height)} px"
            if document.analysis is not None:
                detail += " · critical path across entire project" if is_en else " · критический путь по всему проекту"
            if document.options.baseline:
                detail += " · baseline" if is_en else " · базовый план"
            if format_ == "pdf":
                _size, _orientation, _scale, count = document.pdf_layout()
                pages_word = "pages" if is_en else "стр."
                detail += f" · {math.ceil(document.body_rows/count)} {pages_word}"
            elif format_ == "xml":
                detail += " · MS Project XML, entire project" if is_en else " · MS Project XML, весь проект"
            elif task_table:
                if is_en:
                    detail += (" · 25 GanttPRO fields" if self.site_import.isChecked() else " · 23 GanttPRO fields")
                    detail += f" · {len(self.source.project.dependencies)} links in 'Predecessor'"
                    if self.site_import.isChecked() and not self.table_headers.isChecked():
                        detail += " · file without headers"
                else:
                    detail += (" · 25 полей GanttPRO" if self.site_import.isChecked() else " · 23 поля GanttPRO")
                    detail += f" · {len(self.source.project.dependencies)} связей в «Предшественник»"
                    if self.site_import.isChecked() and not self.table_headers.isChecked():
                        detail += " · файл без заголовков"
            elif format_ == "xlsx":
                if is_en:
                    detail += " · Excel table" + (" + workload sheet" if self.workload.isChecked() else "")
                else:
                    detail += " · таблица Excel" + (" + лист загрузки" if self.workload.isChecked() else "")
            self.document = document
            self.preview.set_document(document)
            self.info.setText(detail)
            self.save_button.setEnabled(True)
        except (ValueError, TypeError, OverflowError) as error:
            self.document = None
            self.preview.set_document(None)
            self.info.clear()
            self.save_button.setEnabled(False)
            self.error.setText(str(error))
            self.error.show()

    def export_to(self, path: Path) -> bool:
        self.timer.stop()
        self.update_preview()
        if self.document is None:
            return False
        try:
            export_file(Path(path), self.document)
        except (OSError, ValueError, RuntimeError, OverflowError) as error:
            self.report_error(str(error))
            return False
        return True

    def apply(self) -> None:
        is_en = self.controller.i18n.language == "en"
        format_ = self.format.currentData()
        label, filter_ = (FORMATS_EN if is_en else FORMATS_RU)[format_]
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", self.controller.project.name).strip() or "project"
        extension = {"ganttpro_csv": "csv", "ganttpro_xlsx": "xlsx"}.get(format_, str(format_))
        title = ("Export " if is_en else "Экспорт ") + label
        path, _selected = QFileDialog.getSaveFileName(self, title, name + "." + extension, filter_)
        if not path:
            return
        if Path(path).suffix.lower() != "." + extension:
            self.report_error(("File extension must be ." + extension) if is_en else ("Расширение файла должно быть ." + extension))
            return
        if self.export_to(Path(path)):
            self.accept()
            self.controller.toast.emit("Export saved" if is_en else "Экспорт сохранён")
