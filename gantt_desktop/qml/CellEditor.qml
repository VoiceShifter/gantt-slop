import QtQuick
import QtQuick.Controls

TextField {
    id: field
    implicitHeight: 30
    leftPadding: 8
    rightPadding: 8
    topPadding: 2
    bottomPadding: 2
    font.family: "Arial"
    font.pixelSize: 12
    color: enabled ? appTheme.colors.text : appTheme.colors.disabled
    placeholderTextColor: appTheme.colors.muted
    selectByMouse: true
    autoScroll: activeFocus
    clip: true
    selectionColor: appTheme.colors.accent
    selectedTextColor: "white"
    background: Rectangle {
        color: field.activeFocus ? appTheme.colors.input : "transparent"
        border.width: field.activeFocus ? 1 : 0
        border.color: appTheme.colors.link
        radius: 2
    }
}
