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

FORMATS = {"pdf": ("PDF", "PDF (*.pdf)"), "png": ("PNG", "PNG (*.png)"),
           "xlsx": ("Excel", "Excel (*.xlsx)"), "xml": ("MS Project XML", "MS Project XML (*.xml)"),
           "csv": ("CSV (выбранные поля)", "CSV (*.csv)"), "ganttpro_csv": ("GanttPRO CSV · 23 поля", "CSV (*.csv)")}


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
        super().__init__(controller, "exportDialog", "Экспорт диаграммы")
        self.resize(1240, 780)
        self.source: ExportSource | None = None
        self.document: ExportDocument | None = None
        self._preparing = False
        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        fit = QPushButton("Вписать по ширине")
        fit.setObjectName("fitExportPreview")
        fit.setAutoDefault(False)
        toolbar.addWidget(fit)
        toolbar.addWidget(QLabel("Ctrl+колесо — масштаб; перетаскивание — прокрутка"))
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
        for key, (label, _filter) in FORMATS.items():
            self.format.addItem(label, key)
        self.scope = QComboBox()
        self.scope.setObjectName("exportScope")
        self.scope.addItem("Весь проект", "all")
        self.scope.addItem("Текущие строки: фильтр/свёрнутые группы", "visible")
        self.content = QComboBox()
        self.content.setObjectName("exportContent")
        for label, key in (("Таблица и диаграмма", "both"), ("Только диаграмма", "chart"), ("Только таблица", "table")):
            self.content.addItem(label, key)
        self.scale = QComboBox()
        self.scale.setObjectName("exportScale")
        for label, value in SCALES.items():
            self.scale.addItem(label, value)
        self.paper = QComboBox()
        self.paper.setObjectName("exportPaper")
        self.paper.addItem("Полный размер", "Full")
        for key in PAPERS:
            self.paper.addItem(key, key)
        self.orientation = QComboBox()
        self.orientation.setObjectName("exportOrientation")
        self.orientation.addItem("Альбомная", True)
        self.orientation.addItem("Книжная", False)
        self.labels = QComboBox()
        self.labels.setObjectName("exportLabels")
        for label, key in (("Внутри", "inside"), ("Справа", "right"), ("Не показывать", "none")):
            self.labels.addItem(label, key)
        self.range = QCheckBox("Свой диапазон дат")
        self.range.setObjectName("exportCustomRange")
        self.start = QDateEdit()
        self.end = QDateEdit()
        for widget, name in ((self.start, "exportStart"), (self.end, "exportEnd")):
            widget.setObjectName(name)
            widget.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
            widget.setDisplayFormat("dd.MM.yyyy")
            widget.setCalendarPopup(True)
        self.links = QCheckBox("Связи задач")
        self.today = QCheckBox("Маркер текущей даты")
        self.workload = QCheckBox("Загрузка ресурсов")
        self.critical = QCheckBox("Критический путь (весь проект)")
        self.baseline = QCheckBox("Выбранный базовый план")
        self.strike = QCheckBox("Зачёркивать закрытые")
        self.fade = QCheckBox("Обесцвечивать закрытые")
        for widget, name in ((self.links, "exportLinks"), (self.today, "exportToday"),
                             (self.workload, "exportWorkload"), (self.critical, "exportCritical"), (self.baseline, "exportBaseline"), (self.strike, "exportStrike"), (self.fade, "exportFade")):
            widget.setObjectName(name)
        self.fields = QListWidget()
        self.fields.setObjectName("exportFields")
        self.fields.setMinimumHeight(190)
        for label, widget in (("Формат", self.format), ("Задачи", self.scope), ("Содержание", self.content),
                              ("Шкала времени", self.scale), ("Размер бумаги", self.paper), ("Ориентация", self.orientation),
                              ("Имя задачи", self.labels), ("", self.range), ("Начало", self.start), ("Завершение", self.end),
                              ("", self.links), ("", self.today), ("", self.workload), ("", self.critical), ("", self.baseline), ("", self.strike), ("", self.fade),
                              ("Поля", self.fields)):
            form.addRow(label, widget)
        self.note = QLabel("Экспорт не меняет проект. PDF с размером бумаги вписывается по ширине и разбивается по строкам; "
                           "предпросмотр — весь документ. XML — весь проект, метаданные полей сохраняются в Notes.")
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
        self.save_button.setText("Экспорт…")
        self.save_button.setObjectName("saveExport")
        self.save_button.setDefault(True)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName("closeExport")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.update_preview)
        for widget in (self.format, self.scope, self.content, self.scale, self.paper, self.orientation, self.labels):
            widget.currentIndexChanged.connect(self.schedule)
        for widget in (self.range, self.links, self.today, self.workload, self.critical, self.baseline, self.strike, self.fade):
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
        return ExportOptions(format=format_, scope="all" if format_ in {"xml", "ganttpro_csv"} else self.scope.currentData(),
                             columns=self.source.default_columns if format_ in {"xml", "ganttpro_csv"} else columns,
                             content=self.content.currentData() if visual else "table",
                             pixels_per_day=self.scale.currentData(),
                             start=date(start.year(), start.month(), start.day()) if self.range.isChecked() and format_ not in {"xml", "ganttpro_csv"} else None,
                             end=date(end.year(), end.month(), end.day()) if self.range.isChecked() and format_ not in {"xml", "ganttpro_csv"} else None,
                             paper=self.paper.currentData(), landscape=self.orientation.currentData(),
                             labels=self.labels.currentData(), links=self.links.isChecked(), today=self.today.isChecked(),
                             workload=self.workload.isChecked() and format_ in {"pdf", "png", "xlsx"},
                             strike_closed=self.strike.isChecked(), fade_closed=self.fade.isChecked(),
                             critical=self.critical.isChecked() and visual and self.content.currentData() != "table",
                             baseline=self.baseline.isChecked() and visual and self.content.currentData() != "table")

    def update_preview(self) -> None:
        if self.source is None:
            return
        self.error.hide()
        format_ = self.format.currentData()
        visual = format_ in {"pdf", "png"}
        for widget, value in ((self.content, "table" if not visual else self.content.currentData()),
                              (self.scope, "all" if format_ in {"xml", "ganttpro_csv"} else self.scope.currentData())):
            widget.blockSignals(True)
            widget.setCurrentIndex(widget.findData(value))
            widget.blockSignals(False)
        for widget in (self.content, self.scale, self.labels, self.links, self.today, self.strike, self.fade):
            widget.setEnabled(visual)
        self.paper.setEnabled(format_ == "pdf")
        self.orientation.setEnabled(format_ == "pdf" and self.paper.currentData() != "Full")
        self.scope.setEnabled(format_ not in {"xml", "ganttpro_csv"})
        self.fields.setEnabled(format_ not in {"xml", "ganttpro_csv"})
        self.range.setEnabled(format_ not in {"xml", "ganttpro_csv"})
        self.start.setEnabled(self.range.isChecked() and format_ not in {"xml", "ganttpro_csv"})
        self.end.setEnabled(self.range.isChecked() and format_ not in {"xml", "ganttpro_csv"})
        if format_ == "ganttpro_csv":
            self.note.setText("Таблица GanttPRO из 23 полей с заголовками. «Предшественник» сохраняет ссылки: Desktop создаёт стрелки при импорте CSV. "
                              "Простые номера — FS/0; остальные связи записаны с типом и лагом в рабочих минутах. "
                              "Имена исполнителей и общий объём переносятся, но календарь, ёмкость/цвет/доли ресурсов, базовые планы и прочие пользовательские поля "
                              "не входят в схему. Для полного проекта сохраните .gantt.json. Полный перенос через импорт самого сайта не подтверждён.")
        else:
            self.note.setText("Экспорт не меняет проект. PDF вписывается по ширине и разбивается по строкам. "
                              "XML не принимается сайтом GanttPRO для обратного импорта.")
        self.transfer_warning.setText(self.note.text() if format_ == "ganttpro_csv" else "")
        self.transfer_warning.setVisible(format_ == "ganttpro_csv")
        self.note.setVisible(format_ != "ganttpro_csv")
        self.workload.setEnabled(format_ == "xlsx" or (visual and self.content.currentData() != "table"))
        self.critical.setEnabled(visual and self.content.currentData() != "table")
        self.baseline.setEnabled(visual and self.content.currentData() != "table" and bool(self.source.project.active_baseline))
        try:
            document = ExportDocument(self.source, self.options())
            detail = f"{len(document.rows)} задач/групп · {math.ceil(document.width)} × {math.ceil(document.height)} px"
            if document.analysis is not None:
                detail += " · критический путь по всему проекту"
            if document.options.baseline:
                detail += " · базовый план"
            if format_ == "pdf":
                _size, _orientation, _scale, count = document.pdf_layout()
                detail += f" · {math.ceil(document.body_rows/count)} стр."
            elif format_ == "xml":
                detail += " · MS Project XML, весь проект"
            elif format_ == "ganttpro_csv":
                detail += f" · 23 поля GanttPRO · {len(self.source.project.dependencies)} связей в «Предшественник»"
            elif format_ == "xlsx":
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
        format_ = self.format.currentData()
        label, filter_ = FORMATS[format_]
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", self.controller.project.name).strip() or "project"
        extension = "csv" if format_ == "ganttpro_csv" else format_
        path, _selected = QFileDialog.getSaveFileName(self, "Экспорт " + label, name + "." + extension, filter_)
        if not path:
            return
        if Path(path).suffix.lower() != "." + extension:
            self.report_error("Расширение файла должно быть ." + extension)
            return
        if self.export_to(Path(path)):
            self.accept()
            self.controller.toast.emit("Экспорт сохранён")
