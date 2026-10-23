import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    property bool compact: false
    readonly property var entry: currentIndex >= 0 && model ? (model[currentIndex] || ({})) : ({})
    implicitWidth: 125
    implicitHeight: compact ? 28 : 34
    textRole: "label"
    valueRole: "value"
    popup.width: Math.max(control.width, 190)
    ToolTip.visible: hovered && compact
    ToolTip.text: displayText
    ToolTip.delay: 500
    font.family: "Arial"
    font.pixelSize: 12
    background: Rectangle {
        radius: 3
        color: control.compact ? "#f3f3f3" : "white"
        border.width: control.compact && !control.activeFocus ? 0 : 1
        border.color: control.activeFocus ? "#247edc" : "#cdd1d6"
        opacity: control.enabled ? 1 : 0.45
    }
    contentItem: Item {
        implicitWidth: label.implicitWidth + 30
        Rectangle {
            x: 9; anchors.verticalCenter: parent.verticalCenter
            width: 7; height: 7; radius: 4
            visible: !!control.entry.value && !control.entry.symbol
            color: control.entry.color || "#999999"
        }
        Text {
            x: 8; anchors.verticalCenter: parent.verticalCenter
            text: control.entry.symbol || ""
            color: control.entry.color || "#777777"
            font.pixelSize: 16
        }
        Text {
            id: label
            x: control.entry.value ? 24 : 9
            width: parent.width - x - 8
            anchors.verticalCenter: parent.verticalCenter
            text: control.compact ? control.displayText.toUpperCase() : control.displayText
            color: control.enabled ? "#444444" : "#aaaaaa"
            font.pixelSize: control.compact ? 11 : 12
            elide: Text.ElideRight
        }
    }
    indicator: Text {
        x: control.width - width - 8; anchors.verticalCenter: parent.verticalCenter
        text: "⌄"; color: "#999999"; visible: !control.compact
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.popup.width
        implicitHeight: 32
        highlighted: control.highlightedIndex === index
        contentItem: Row {
            spacing: 8
            Text { text: modelData.symbol || "●"; color: modelData.color || "#999999"; font.pixelSize: modelData.symbol ? 16 : 11; anchors.verticalCenter: parent.verticalCenter; visible: !!modelData.value }
            Text { text: modelData.label; color: "#303438"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
        }
    }
}
