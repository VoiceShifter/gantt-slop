import QtQuick
import QtQuick.Controls

Item {
    id: cell
    property var definition: ({})
    property var value: null
    property string displayText: ""
    property string taskId: ""
    property bool editable: false
    property bool summary: false
    signal editRequested()
    CheckBox {
        objectName: "custom-check-" + (cell.definition.customId || "") + "-" + cell.taskId
        visible: cell.definition.kind === "checkbox"
        x: 2; width: 30; height: parent.height
        enabled: cell.editable
        tristate: true
        checkState: cell.value === true ? Qt.Checked : cell.value === false ? Qt.Unchecked : Qt.PartiallyChecked
        nextCheckState: function() { return checkState }
        onClicked: controller.toggleCustomValue(cell.taskId, cell.definition.customId)
        Accessible.name: cell.definition.title || i18n.tr.checkbox_field
    }
    Button {
        id: button
        objectName: "custom-value-" + (cell.definition.customId || "") + "-" + cell.taskId
        x: cell.definition.kind === "checkbox" ? 30 : 1
        width: parent.width-x; height: parent.height
        hoverEnabled: true
        onClicked: if (cell.editable) cell.editRequested()
        Accessible.name: (cell.definition.title || i18n.tr.field_label) + ": " + cell.displayText
        background: Rectangle { color: button.hovered && cell.editable ? appTheme.colors.hover : "transparent" }
        contentItem: Item {
            Rectangle {
                x: 7; anchors.verticalCenter: parent.verticalCenter
                width: 15; height: 15; radius: 2
                visible: cell.definition.kind === "color" && !!cell.value
                color: cell.definition.kind === "color" && typeof cell.value === "string" ? cell.value : "transparent"
                border.color: appTheme.colors.strongBorder
            }
            Text {
                x: cell.definition.kind === "color" && cell.value ? 28 : 7
                width: Math.max(0,parent.width-x-6); height: parent.height
                text: cell.displayText; textFormat: Text.PlainText
                color: appTheme.colors.text; font.pixelSize: 12; font.bold: cell.summary
                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                horizontalAlignment: cell.definition.kind === "number" ? Text.AlignRight : Text.AlignLeft
            }
        }
        ToolTip.visible: hovered
        ToolTip.text: cell.editable ? i18n.tr.change_field_value : i18n.tr.value_read_only
        ToolTip.delay: 600
    }
}
