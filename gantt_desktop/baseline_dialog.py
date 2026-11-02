"""Native baseline capture/selection manager; snapshots live in the project."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from .dialogs import EditorDialog

if TYPE_CHECKING:
    from .controller import Controller


class BaselineDialog(EditorDialog):
    def __init__(self, controller: Controller):
        is_en = controller.i18n.language == "en"
        super().__init__(controller, "baselineDialog", "Baselines" if is_en else "Базовые планы")
        self.resize(690, 450)
        note = QLabel(
            "A snapshot of all project dates is stored in the file, not in the Undo buffer. Selection does not alter schedule. "
            "Creation, selection, and deletion can be undone."
            if is_en
            else "Снимок дат всего проекта хранится в файле, а не в буфере Undo. Выбор не меняет расписание. "
                 "Создание, выбор и удаление — отменяемые изменения проекта."
        )
        note.setWordWrap(True)
        self.layout_root.addWidget(note)
        self.table = QTreeWidget()
        self.table.setObjectName("baselineList")
        self.table.setRootIsDecorated(False)
        self.table.setHeaderLabels(
            ["Name", "Created", "Items", "Comparison"]
            if is_en
            else ["Название", "Создан", "Элементов", "Сравнение"]
        )
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 110)
        self.table.currentItemChanged.connect(self.update_actions)
        self.table.itemDoubleClicked.connect(lambda *_args: self.activate())
        self.layout_root.addWidget(self.table)
        self.details = QLabel()
        self.details.setObjectName("baselineDetails")
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.layout_root.addWidget(self.details)
        capture = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setObjectName("baselineName")
        self.name.setPlaceholderText("Snapshot name" if is_en else "Название нового снимка")
        self.name.returnPressed.connect(self.capture)
        create = QPushButton("Capture snapshot" if is_en else "Создать снимок")
        create.setObjectName("createBaseline")
        create.setAutoDefault(False)
        create.clicked.connect(self.capture)
        capture.addWidget(self.name, 1)
        capture.addWidget(create)
        self.layout_root.addLayout(capture)
        actions = QHBoxLayout()
        self.use = QPushButton("Use" if is_en else "Использовать")
        self.hide_button = QPushButton("Do not show" if is_en else "Не показывать")
        self.remove = QPushButton("Delete…" if is_en else "Удалить…")
        for name, button, callback in (("useBaseline", self.use, self.activate),
                                       ("hideBaseline", self.hide_button, lambda: self.controller.selectBaseline("")),
                                       ("removeBaseline", self.remove, self.confirm_remove)):
            button.setObjectName(name)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        self.layout_root.addLayout(actions)
        self.layout_root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        close.setText("Close" if is_en else "Закрыть")
        close.setObjectName("closeBaselines")
        close.setAutoDefault(False)
        buttons.rejected.connect(self.reject)
        self.layout_root.addWidget(buttons)
        controller.viewChanged.connect(self.refresh)

    def selected(self) -> str:
        item = self.table.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item is not None else ""

    def next_name(self) -> str:
        is_en = self.controller.i18n.language == "en"
        names = {item.name.casefold() for item in self.controller.project.baselines.values()}
        number = 1
        prefix = "baseline" if is_en else "базовый план"
        while f"{prefix} {number}" in names:
            number += 1
        return f"Baseline {number}" if is_en else f"Базовый план {number}"

    def prepare(self) -> None:
        self.error.hide()
        self.refresh()
        self.name.setText(self.next_name())

    def refresh(self) -> None:
        selected = self.selected() or self.controller.project.active_baseline
        is_en = self.controller.i18n.language == "en"
        self.table.blockSignals(True)
        self.table.clear()
        selected_text = "Selected" if is_en else "Выбран"
        for baseline in self.controller.project.baselines.values():
            active = baseline.id == self.controller.project.active_baseline
            item = QTreeWidgetItem([baseline.name, baseline.created.strftime("%d.%m.%Y"), str(len(baseline.tasks)), selected_text if active else ""])
            item.setData(0, Qt.ItemDataRole.UserRole, baseline.id)
            self.table.addTopLevelItem(item)
            if baseline.id == selected:
                self.table.setCurrentItem(item)
        if self.table.currentItem() is None:
            first = self.table.topLevelItem(0)
            if first is not None:
                self.table.setCurrentItem(first)
        self.table.blockSignals(False)
        self.update_actions()

    def update_actions(self, *_args) -> None:
        is_en = self.controller.i18n.language == "en"
        baseline = self.controller.project.baselines.get(self.selected())
        self.use.setEnabled(baseline is not None and baseline.id != self.controller.project.active_baseline)
        self.remove.setEnabled(baseline is not None)
        self.hide_button.setEnabled(bool(self.controller.project.active_baseline))
        if baseline is None:
            self.details.setText("No baselines. Create a snapshot of current dates." if is_en else "Нет базовых планов. Создайте снимок текущих дат.")
        else:
            saved, current = set(baseline.tasks), set(self.controller.project.tasks)
            if is_en:
                self.details.setText(f"{baseline.name}: {len(saved & current)} match, {len(current-saved)} new, "
                                     f"{len(saved-current)} deleted. New items do not get artificial baseline dates.")
            else:
                self.details.setText(f"{baseline.name}: совпадает {len(saved & current)}, новых {len(current-saved)}, "
                                     f"удалённых {len(saved-current)}. Новые элементы не получают выдуманных базовых дат.")

    def capture(self) -> None:
        self.error.hide()
        key = self.controller.createBaseline(self.name.text())
        if key:
            self.name.setText(self.next_name())
            for index in range(self.table.topLevelItemCount()):
                item = self.table.topLevelItem(index)
                if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == key:
                    self.table.setCurrentItem(item)
                    break

    def activate(self) -> None:
        key = self.selected()
        if key:
            self.controller.selectBaseline(key)

    def confirm_remove(self) -> None:
        key = self.selected()
        if key:
            self.controller.dialogs.confirmBaselineDelete(key)
