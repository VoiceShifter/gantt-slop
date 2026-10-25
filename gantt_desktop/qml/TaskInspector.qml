import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Drawer {
    id: drawer
    objectName: "taskInspector"
    edge: Qt.RightEdge
    width: Math.min(800, parent.width - 340)
    y: 74
    height: parent.height - y
    padding: 0
    modal: false
    interactive: false
    signal dependencyRequested(string source, string target, string kind, string linkId)
    signal deleteRequested(string taskId)
    signal assignmentRequested(string taskId)
    signal assigneePickerRequested(string taskId, var anchor)
    background: Rectangle { color: appTheme.colors.surface; border.color: appTheme.colors.border }
    Connections {
        target: controller
        function onSelectionChanged() { if (!controller.selectedId) drawer.close() }
    }
    ColorDialog {
        id: colorDialog
        title: "Цвет задачи"
        onAccepted: controller.editField(controller.selectedId, "color", selectedColor.toString())
    }
    contentItem: ColumnLayout {
        spacing: 0
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 120
            Text { x: 32; y: 27; text: controller.projectName; color: appTheme.colors.muted; font.pixelSize: 12 }
            ActionButton { anchors.right: parent.right; anchors.rightMargin: 22; y: 21; text: "×"; font.pixelSize: 21; hint: "Закрыть"; onClicked: drawer.close() }
            Rectangle {
                x: 34; y: 65; width: 23; height: 23; radius: 3
                color: controller.selected.color || "#50c7d6"
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { colorDialog.selectedColor=controller.selected.color || "#50c7d6"; colorDialog.open() } }
            }
            CellEditor {
                x: 70; y: 57; width: parent.width-108; height: 40
                objectName: "inspectorName"
                text: controller.selected.name || ""
                font.pixelSize: 20; font.bold: true
                onEditingFinished: if (controller.selectedId && text !== controller.selected.name) controller.editField(controller.selectedId, "name", text)
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: appTheme.colors.border }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                width: parent.width
                spacing: 20
                RowLayout {
                    Layout.topMargin: 20; Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    Slider {
                        id: completion
                        objectName: "inspectorProgress"
                        from: 0; to: 100; stepSize: 1
                        Layout.preferredWidth: 120
                        Layout.preferredHeight: 26
                        padding: 0
                        value: controller.selected.progress || 0
                        enabled: !controller.selected.summary
                        background: Rectangle {
                            implicitWidth: 120; implicitHeight: 24
                            x:completion.leftPadding; y:(completion.height-height)/2
                            width:completion.availableWidth; height:24; radius:3; color:appTheme.colors.border
                            Rectangle { width:parent.width*completion.visualPosition; height:parent.height; radius:3; color:completion.enabled?appTheme.colors.accent:appTheme.colors.disabled }
                        }
                        handle: Rectangle {
                            width:3; height:22; radius:1
                            x:completion.leftPadding+completion.visualPosition*(completion.availableWidth-width)
                            y:(completion.height-height)/2
                            color:completion.enabled?appTheme.colors.link:appTheme.colors.disabled
                        }
                        onPressedChanged: if (!pressed && controller.selectedId && enabled && Math.round(value)!==Math.round(controller.selected.progress)) controller.editField(controller.selectedId, "progress", String(Math.round(value)))
                    }
                    CellEditor {
                        objectName:"inspectorProgressValue"
                        Layout.preferredWidth:36; Layout.preferredHeight:26
                        text:String(Math.round(controller.selected.progress||0))
                        horizontalAlignment:Text.AlignRight
                        enabled:!controller.selected.summary
                        validator:IntValidator { bottom:0; top:100 }
                        onEditingFinished:if(controller.selectedId && text!==String(Math.round(controller.selected.progress)))controller.editField(controller.selectedId,"progress",text)
                    }
                    Label { text: "%"; color: appTheme.colors.text }
                    MetadataChoice {
                        objectName: "inspectorStatus"
                        compact: true; Layout.preferredWidth: 118
                        visible: !controller.selected.summary
                        model: controller.statusChoices
                        currentIndex: indexOfValue(controller.selected.status || "open")
                        onActivated: controller.editField(controller.selectedId, "status", currentValue)
                    }
                    MetadataChoice {
                        objectName: "inspectorPriority"
                        compact: true; Layout.preferredWidth: 150
                        visible: !controller.selected.summary
                        model: controller.priorityChoices
                        currentIndex: indexOfValue(controller.selected.priority || "medium")
                        onActivated: controller.editField(controller.selectedId, "priority", currentValue)
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton {
                        text: drawer.width < 760 ? "＋ Связь" : "＋  Добавить зависимость"
                        hint: "Добавить зависимость"
                        enabled: !!controller.selectedId
                        onClicked: drawer.dependencyRequested("", controller.selectedId, "FS", "")
                    }
                }
                Label {
                    objectName: "inspectorTotalFloat"
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    visible: controller.criticalPath && !!controller.selectedId
                    textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.pixelSize: 12
                    text: controller.selected.totalFloat === null || controller.selected.totalFloat === undefined ? "Резерв не рассчитан: " + controller.criticalPathError :
                          (controller.selected.critical ? (controller.selected.summary ? "Критическая группа. " : "Критическая задача. ") : "") +
                          "Резерв: " + Number(controller.selected.totalFloat/60).toLocaleString(Qt.locale(),"g",6) + " рабочих ч."
                    color: controller.selected.critical ? appTheme.colors.danger : appTheme.colors.secondary
                }
                GridLayout {
                    columns: 4
                    columnSpacing: 12; rowSpacing: 9
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    Label { text: "Начало"; color: appTheme.colors.muted; font.pixelSize: 12; Layout.columnSpan: 2 }
                    Label { text: "Завершение"; color: appTheme.colors.muted; font.pixelSize: 12; Layout.columnSpan: 2 }
                    DateField {
                        objectName: "inspectorStart"
                        Layout.fillWidth: true; text: controller.selected.start || ""; enabled: controller.selected.canMove || false
                        onEditingFinished: if (text!==controller.selected.start) controller.editField(controller.selectedId,"start",text)
                        onCalendarRequested: nativeDialogs.showTaskDate(controller.selectedId,"start")
                    }
                    CellEditor { Layout.preferredWidth: 64; text: controller.selected.startTime || ""; enabled: (controller.selected.canMove || false) && !controller.selected.summary; onEditingFinished: if(text!==controller.selected.startTime) controller.editField(controller.selectedId,"startTime",text) }
                    DateField {
                        objectName: "inspectorEnd"
                        Layout.fillWidth: true; text: controller.selected.end || ""; enabled: controller.selected.canResizeEnd || false
                        onEditingFinished: if(text!==controller.selected.end) controller.editField(controller.selectedId,"end",text)
                        onCalendarRequested: nativeDialogs.showTaskDate(controller.selectedId,"end")
                    }
                    CellEditor { Layout.preferredWidth: 64; text: controller.selected.endTime || ""; enabled: controller.selected.canResizeEnd || false; onEditingFinished: if(text!==controller.selected.endTime) controller.editField(controller.selectedId,"endTime",text) }
                    Label { text: "Длительность, ч"; color: appTheme.colors.muted; Layout.columnSpan: 2; font.pixelSize: 12 }
                    Label { text: "Трудозатраты, ч"; color: appTheme.colors.muted; Layout.columnSpan: 2; font.pixelSize: 12 }
                    CellEditor {
                        objectName: "inspectorDuration"
                        Layout.columnSpan: 2; Layout.fillWidth: true
                        text: String(controller.selected.duration || 0)
                        enabled: !controller.selected.summary && !controller.selected.milestone
                        onEditingFinished: if(text!==String(controller.selected.duration)) controller.editField(controller.selectedId,"duration",text)
                    }
                    CellEditor {
                        Layout.columnSpan: 2; Layout.fillWidth: true
                        text: String(controller.selected.effortHours || 0); enabled: !controller.selected.summary
                        onEditingFinished: if(text!==String(controller.selected.effortHours)) controller.editField(controller.selectedId,"effort",text)
                    }
                    Label { text: "Исполнитель"; color: appTheme.colors.muted; Layout.columnSpan: 2; font.pixelSize: 12 }
                    Label { text: "Стоимость"; color: appTheme.colors.muted; Layout.columnSpan: 2; font.pixelSize: 12 }
                    RowLayout {
                        Layout.columnSpan:2; Layout.fillWidth:true
                        AssigneeField {
                            id: assigneeField
                            objectName:"inspectorAssignee"
                            Layout.fillWidth:true; framed:true
                            resourceIds:controller.selected.resourceIds||[]
                            enabled:!!controller.selectedId&&!controller.selected.summary
                            onClicked:drawer.assigneePickerRequested(controller.selectedId,assigneeField)
                        }
                        ActionButton { objectName:"chooseResourcesButton"; text:"⋯"; hint:"Выбрать ресурсы и распределить часы"; enabled:!!controller.selectedId&&!controller.selected.summary; onClicked:drawer.assignmentRequested(controller.selectedId) }
                    }
                    CellEditor {
                        Layout.columnSpan: 2; Layout.fillWidth: true
                        text: String(controller.selected.costValue || 0); enabled: !controller.selected.summary
                        onEditingFinished: if(text!==String(controller.selected.costValue)) controller.editField(controller.selectedId,"cost",text)
                    }
                }
                ColumnLayout {
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    visible: !!controller.baselineName && !!controller.selectedId
                    Label {
                        Layout.fillWidth: true; elide: Text.ElideRight
                        text: "Базовый план: " + controller.baselineName; textFormat: Text.PlainText
                        color: appTheme.colors.muted; font.pixelSize: 12
                    }
                    Label {
                        objectName: "inspectorBaseline"
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
                        text: controller.selected.hasBaseline ? "Начало: " + controller.selected.baselineStart + " · завершение: " + controller.selected.baselineEnd +
                              "\nΔ начала: " + controller.selected.startVariance + " · Δ завершения: " + controller.selected.endVariance + " календарных ч." : "Элемента нет в выбранном базовом плане."
                        color: controller.selected.endVarianceHours > 0 ? appTheme.colors.danger : appTheme.colors.secondary
                        font.pixelSize: 12
                    }
                }
                ColumnLayout {
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    Label { text: "Крайний срок"; color: appTheme.colors.muted; font.pixelSize: 12 }
                    RowLayout {
                        Layout.fillWidth: true
                        DateField {
                            objectName: "inspectorDeadline"
                            Layout.fillWidth: true
                            text: controller.selected.deadline || ""
                            placeholderText: "Не задан"
                            enabled: !!controller.selectedId
                            onEditingFinished: if (text!==controller.selected.deadline) controller.editField(controller.selectedId,"deadline",text)
                            onCalendarRequested: nativeDialogs.showTaskDate(controller.selectedId,"deadline")
                        }
                        ActionButton {
                            objectName: "clearDeadline"
                            text: "×"; hint: "Убрать крайний срок"
                            visible: !!controller.selected.deadline
                            onClicked: controller.editField(controller.selectedId,"deadline","")
                        }
                    }
                    Label {
                        objectName: "deadlineWarning"
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        visible: !!controller.selected.deadlineMissed || !!controller.selected.deadlineOverdue
                        text: controller.selected.deadlineMissed ? "Плановое завершение позже крайнего срока." : "Крайний срок прошёл, задача не завершена."
                        color: appTheme.colors.danger; font.pixelSize: 12
                    }
                }
                Label {
                    Layout.leftMargin: 40; Layout.rightMargin: 40; Layout.fillWidth: true
                    visible: !!controller.selectedId && !controller.selected.canMove
                    text: "Даты закреплены зависимостями. Чтобы сдвинуть задачу, измените связь или её лаг."
                    color: appTheme.colors.secondary; font.pixelSize: 12; wrapMode: Text.WordWrap
                }
                ColumnLayout {
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    Label { text: "Группа"; color: appTheme.colors.muted; font.pixelSize: 12 }
                    ComboBox {
                        Layout.fillWidth: true
                        model: controller.groupChoices; textRole: "name"; valueRole: "id"
                        currentIndex: indexOfValue(controller.selected.parentId || "")
                        onActivated: controller.editField(controller.selectedId,"parent",currentValue)
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: appTheme.colors.border }
                TextArea {
                    Layout.leftMargin: 32; Layout.rightMargin: 32; Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    text: controller.selected.notes || ""
                    placeholderText: "Добавить описание задачи"
                    wrapMode: TextEdit.Wrap
                    font.pixelSize: 14; color: appTheme.colors.text
                    placeholderTextColor: appTheme.colors.muted
                    selectionColor: appTheme.colors.accent
                    selectedTextColor: "white"
                    background: Rectangle { color: appTheme.colors.input }
                    onActiveFocusChanged: if (!activeFocus && controller.selectedId && text!==controller.selected.notes) controller.editField(controller.selectedId,"notes",text)
                }
                Label { Layout.leftMargin: 32; text: "Зависимости между задачами"; font.bold: true; color: appTheme.colors.text }
                Repeater {
                    model: controller.selected.dependencies || []
                    delegate: RowLayout {
                        required property var modelData
                        Layout.leftMargin: 32; Layout.rightMargin: 24; Layout.fillWidth: true
                        Label { text: modelData.incoming ? "←" : "→"; font.pixelSize: 20; color: appTheme.colors.muted }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Label { text: modelData.incoming ? modelData.sourceName : modelData.targetName; elide: Text.ElideRight; Layout.fillWidth: true; color: appTheme.colors.text }
                            Label { text: modelData.incoming ? "ПРЕДШЕСТВЕННИК" : "ПОСЛЕДОВАТЕЛЬ"; color: appTheme.colors.muted; font.pixelSize: 10 }
                        }
                        ActionButton { text: modelData.kind + " · Лаг: " + modelData.lag + "ч"; onClicked: drawer.dependencyRequested(modelData.source,modelData.target,modelData.kind,modelData.id) }
                        ActionButton { text: "×"; hint: "Удалить связь (можно отменить)"; onClicked: controller.removeDependency(modelData.id) }
                    }
                }
                Item { height: 20; Layout.fillWidth: true }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: appTheme.colors.border }
        RowLayout {
            Layout.fillWidth: true; Layout.margins: 20
            ActionButton { text: "Показать на диаграмме"; onClicked: { controller.focusTask(controller.selectedId); drawer.close() } }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Удалить задачу"; onClicked: drawer.deleteRequested(controller.selectedId) }
        }
    }
}
