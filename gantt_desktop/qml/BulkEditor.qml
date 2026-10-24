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
    property var draftResourceIds: []
    signal deleteRequested()
    signal assigneePickerRequested(var ids, var anchor)
    background: Rectangle { color: appTheme.colors.surface; border.color: appTheme.colors.border }
    onAboutToShow: resetDraft()
    onClosed: if (controller.bulkMode) controller.setBulkMode(false)

    function resetDraft() {
        assign.checked = false
        draftResourceIds = []
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
                Label { text: "Массовое изменение"; font.bold: true; font.pixelSize: 14; color: appTheme.colors.text }
                Item { Layout.fillWidth: true }
                ActionButton { text: "×"; hint: "Отменить неприменённые изменения"; onClicked: controller.setBulkMode(false) }
            }
            Label { objectName: "bulkCount"; text: "Выбрано: " + controller.checkedCount; color: appTheme.colors.muted; font.pixelSize: 11 }
            Rectangle { Layout.fillWidth: true; height: 1; color: appTheme.colors.border }
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
                    color: assign.checked ? appTheme.colors.accent : appTheme.colors.input
                    border.color: assign.checked ? color : appTheme.colors.strongBorder
                    Text { anchors.centerIn: parent; text: assign.checked ? "✓" : ""; color: "white"; font.pixelSize: 13 }
                }
                contentItem: Text {
                    leftPadding: assign.indicator.width + assign.spacing
                    text: assign.text; font: assign.font
                    color: assign.enabled ? appTheme.colors.text : appTheme.colors.disabled
                    verticalAlignment: Text.AlignVCenter
                }
            }
            AssigneeField {
                id: assignee
                objectName: "bulkAssignee"
                Layout.fillWidth: true; framed: true
                enabled: assign.checked && controller.checkedLeafCount > 0
                resourceIds: drawer.draftResourceIds
                placeholderText: "Снять назначение"
                onClicked: drawer.assigneePickerRequested(drawer.draftResourceIds,assignee)
            }
            Label { text: "Статус"; font.pixelSize: 12; color: appTheme.colors.secondary }
            MetadataChoice {
                id: status
                objectName: "bulkStatus"
                Layout.fillWidth: true
                enabled: controller.checkedLeafCount > 0
                model: [{value:"",label:"Не менять",color:"#999999",symbol:""}].concat(controller.statusChoices)
            }
            Label { text: "Приоритет"; font.pixelSize: 12; color: appTheme.colors.secondary }
            MetadataChoice {
                id: priority
                objectName: "bulkPriority"
                Layout.fillWidth: true
                enabled: controller.checkedLeafCount > 0
                model: [{value:"",label:"Не менять",color:"#999999",symbol:""}].concat(controller.priorityChoices)
            }
            Label { text: "Цвет задачи"; font.pixelSize: 12; color: appTheme.colors.secondary }
            RowLayout {
                Layout.fillWidth: true
                Rectangle { width: 22; height: 22; radius: 3; color: drawer.colorPending ? drawer.draftColor : appTheme.colors.input; border.color: appTheme.colors.border }
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
                color: appTheme.colors.muted; font.pixelSize: 11
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
                        if (assign.checked) changes.resourceIds = drawer.draftResourceIds
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
                palette.buttonText: appTheme.colors.danger
                text: "Удалить задачи (" + controller.bulkDeleteCount + ")"
                enabled: controller.bulkDeleteCount > 0
                background: Rectangle { color: appTheme.colors.surface; radius: 3; border.color: appTheme.colors.danger; opacity: parent.enabled ? 1 : 0.4 }
                onClicked: drawer.deleteRequested()
            }
        }
    }
}
