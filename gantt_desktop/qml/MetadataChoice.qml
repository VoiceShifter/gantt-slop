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
        color: control.compact ? appTheme.colors.panel : appTheme.colors.input
        border.width: control.compact && !control.activeFocus ? 0 : 1
        border.color: control.activeFocus ? appTheme.colors.link : appTheme.colors.border
        opacity: control.enabled ? 1 : 0.45
    }
    contentItem: Item {
        implicitWidth: label.implicitWidth + 30
        Rectangle {
            x: 9; anchors.verticalCenter: parent.verticalCenter
            width: 7; height: 7; radius: 4
            visible: !!control.entry.value && !control.entry.symbol
            color: control.entry.color || appTheme.colors.muted
        }
        Text {
            x: 8; anchors.verticalCenter: parent.verticalCenter
            text: control.entry.symbol || ""
            color: control.entry.color || appTheme.colors.secondary
            font.pixelSize: 16
        }
        Text {
            id: label
            x: control.entry.value ? 24 : 9
            width: parent.width - x - 8
            anchors.verticalCenter: parent.verticalCenter
            text: control.compact ? control.displayText.toUpperCase() : control.displayText
            color: control.enabled ? appTheme.colors.text : appTheme.colors.disabled
            font.pixelSize: control.compact ? 11 : 12
            elide: Text.ElideRight
        }
    }
    indicator: Text {
        x: control.width - width - 8; anchors.verticalCenter: parent.verticalCenter
        text: "⌄"; color: appTheme.colors.muted; visible: !control.compact
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.popup.width
        implicitHeight: 32
        highlighted: control.highlightedIndex === index
        contentItem: Row {
            spacing: 8
            Text { text: modelData.symbol || "●"; color: modelData.color || appTheme.colors.muted; font.pixelSize: modelData.symbol ? 16 : 11; anchors.verticalCenter: parent.verticalCenter; visible: !!modelData.value }
            Text { text: modelData.label; color: appTheme.colors.text; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
        }
    }
}
