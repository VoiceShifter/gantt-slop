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
    color: enabled ? "#303438" : "#9b9b9b"
    selectByMouse: true
    autoScroll: activeFocus
    clip: true
    selectionColor: "#cfe6ff"
    selectedTextColor: "#20262c"
    background: Rectangle {
        color: field.activeFocus ? "white" : "transparent"
        border.width: field.activeFocus ? 1 : 0
        border.color: "#287ad6"
        radius: 2
    }
}
