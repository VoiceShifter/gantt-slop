import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Drawer {
    id: drawer
    objectName: "bulkEditor"
    edge: Qt.RightEdge
    width: Math.min(300, parent.width - 320)
    y: 114
    height: parent.height - y
    padding: 0
    modal: false
    interactive: false
    closePolicy: Popup.NoAutoClose
    property bool colorPending: false
    property string draftColor: "#50c7d6"
    signal deleteRequested()
    background: Rectangle { color: "white"; border.color: "#e0e3e7" }
    onAboutToShow: resetDraft()
    onClosed: if (controller.bulkMode) controller.setBulkMode(false)

    function resetDraft() {
        assign.checked = false
        assignee.text = ""
        status.currentIndex = 0
        priority.currentIndex = 0
        colorPending = false
    }
    ColorDialog {
        id: colorDialog
        title: "Цвет выбранных задач"
        onAccepted: { drawer.draftColor = selectedColor.toString(); drawer.colorPending = true }
    }
    contentItem: Item {
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 9
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Массовое изменение"; font.bold: true; font.pixelSize: 14; color: "#303438" }
                Item { Layout.fillWidth: true }
                ActionButton { text: "×"; hint: "Отменить неприменённые изменения"; onClicked: controller.setBulkMode(false) }
            }
            Label { objectName: "bulkCount"; text: "Выбрано: " + controller.checkedCount; color: "#888888"; font.pixelSize: 11 }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#eceef0" }
            CheckBox {
                id: assign
                objectName: "bulkAssignEnabled"
                text: "Исполнитель"
                enabled: controller.checkedLeafCount > 0
                font.pixelSize: 12
                implicitHeight: 26
                spacing: 7
                indicator: Rectangle {
                    implicitWidth: 18; implicitHeight: 18
                    y: (assign.height-height)/2
                    radius: 1
                    color: assign.checked ? "#1766cb" : "white"
                    border.color: assign.checked ? color : "#b9bec3"
                    Text { anchors.centerIn: parent; text: assign.checked ? "✓" : ""; color: "white"; font.pixelSize: 13 }
                }
                contentItem: Text {
                    leftPadding: assign.indicator.width + assign.spacing
                    text: assign.text; font: assign.font
                    color: assign.enabled ? "#555555" : "#aaaaaa"
                    verticalAlignment: Text.AlignVCenter
                }
            }
            CellEditor {
                id: assignee
                objectName: "bulkAssignee"
                Layout.fillWidth: true
                enabled: assign.checked && controller.checkedLeafCount > 0
                placeholderText: "Имя; пусто — снять назначение"
                background: Rectangle { radius: 3; color: "white"; border.color: assignee.activeFocus ? "#247edc" : "#d0d4d9" }
            }
            Label { text: "Статус"; font.pixelSize: 12; color: "#777777" }
            MetadataChoice {
                id: status
                objectName: "bulkStatus"
                Layout.fillWidth: true
                enabled: controller.checkedLeafCount > 0
                model: [{value:"",label:"Не менять",color:"#999999",symbol:""}].concat(controller.statusChoices)
            }
            Label { text: "Приоритет"; font.pixelSize: 12; color: "#777777" }
            MetadataChoice {
                id: priority
                objectName: "bulkPriority"
                Layout.fillWidth: true
                enabled: controller.checkedLeafCount > 0
                model: [{value:"",label:"Не менять",color:"#999999",symbol:""}].concat(controller.priorityChoices)
            }
            Label { text: "Цвет задачи"; font.pixelSize: 12; color: "#777777" }
            RowLayout {
                Layout.fillWidth: true
                Rectangle { width: 22; height: 22; radius: 3; color: drawer.colorPending ? drawer.draftColor : "white"; border.color: "#cdd1d6" }
                ActionButton {
                    objectName: "bulkColorButton"
                    Layout.fillWidth: true
                    text: drawer.colorPending ? drawer.draftColor : "Выбрать цвет…"
                    enabled: controller.checkedCount > 0
                    onClicked: { colorDialog.selectedColor=drawer.draftColor; colorDialog.open() }
                }
                ActionButton { text: "×"; visible: drawer.colorPending; hint: "Не менять цвет"; onClicked: drawer.colorPending=false }
            }
            Label {
                Layout.fillWidth: true
                text: "Отмечаются только нужные поля. Статус меняет процент выполнения; даты и трудозатраты сохраняются."
                wrapMode: Text.WordWrap
                color: "#999999"; font.pixelSize: 11
            }
            Item { Layout.fillHeight: true }
            ActionButton {
                objectName: "applyBulkButton"
                Layout.fillWidth: true
                implicitHeight: 36
                primary: true
                text: "Применить изменения"
                enabled: controller.checkedCount > 0 && (drawer.colorPending || (controller.checkedLeafCount > 0 && (assign.checked || status.currentIndex > 0 || priority.currentIndex > 0)))
                onClicked: {
                    drawer.contentItem.forceActiveFocus()
                    let changes = ({})
                    if (controller.checkedLeafCount > 0) {
                        if (assign.checked) changes.assignee = assignee.text
                        if (status.currentIndex > 0) changes.status = status.currentValue
                        if (priority.currentIndex > 0) changes.priority = priority.currentValue
                    }
                    if (drawer.colorPending) changes.color = drawer.draftColor
                    if (controller.applyBulk(changes)) drawer.resetDraft()
                }
            }
            ActionButton {
                objectName: "deleteBulkButton"
                Layout.fillWidth: true
                implicitHeight: 34
                palette.buttonText: "#e7767c"
                text: "Удалить задачи (" + controller.bulkDeleteCount + ")"
                enabled: controller.bulkDeleteCount > 0
                background: Rectangle { color: "white"; radius: 3; border.color: "#ed969b"; opacity: parent.enabled ? 1 : 0.4 }
                onClicked: drawer.deleteRequested()
            }
        }
    }
}
