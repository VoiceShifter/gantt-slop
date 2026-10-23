import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "dependencyDialog"
    property string linkId: ""
    property string sourceId: ""
    property string targetId: ""
    property string relation: "FS"
    property string lagHours: "0"
    title: linkId ? "Изменить зависимость" : "Добавить зависимость"
    modal: true
    anchors.centerIn: parent
    width: Math.min(620, parent.width - 50)
    padding: 24
    onOpened: {
        source.currentIndex = source.indexOfValue(sourceId)
        target.currentIndex = target.indexOfValue(targetId)
        kind.currentIndex = ["FS", "SS", "FF", "SF"].indexOf(relation)
        lag.text = lagHours
    }
    ColumnLayout {
        width: parent.width
        spacing: 12
        Label { text: "Предшественник"; color: "#777777" }
        ComboBox { id: source; objectName: "dependencySource"; Layout.fillWidth: true; model: controller.taskChoices; textRole: "name"; valueRole: "id" }
        Label { text: "Последователь"; color: "#777777" }
        ComboBox { id: target; objectName: "dependencyTarget"; Layout.fillWidth: true; model: controller.taskChoices; textRole: "name"; valueRole: "id" }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Тип связи"; color: "#777777" }
                ComboBox {
                    id: kind
                    objectName: "dependencyKind"
                    Accessible.name: "Тип связи"
                    Layout.fillWidth: true
                    model: ["FS · Окончание → Начало", "SS · Начало → Начало", "FF · Окончание → Окончание", "SF · Начало → Окончание"]
                }
            }
            ColumnLayout {
                Label { text: "Лаг, рабочие часы"; color: "#777777" }
                CellEditor { id: lag; objectName: "dependencyLag"; text: "0"; Layout.preferredWidth: 125; background: Rectangle { color: "white"; radius: 3; border.color: "#d1d5da" } }
            }
        }
        Label { text: "Отрицательный лаг разрешён. Циклические связи не допускаются."; font.pixelSize: 11; color: "#777777"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            ActionButton {
                objectName: "deleteDependency"
                visible: !!dialog.linkId
                text: "Удалить связь"
                palette.buttonText: "#cf535d"
                onClicked: { controller.removeDependency(dialog.linkId); dialog.close() }
            }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Отмена"; objectName: "cancelDependency"; onClicked: dialog.close() }
            ActionButton {
                text: "Сохранить"; primary: true; objectName: "saveDependency"
                enabled: !!source.currentValue && !!target.currentValue && source.currentValue !== target.currentValue
                onClicked: {
                    const relation = ["FS", "SS", "FF", "SF"][kind.currentIndex]
                    const ok = dialog.linkId
                        ? controller.updateDependency(dialog.linkId, source.currentValue || "", target.currentValue || "", relation, lag.text)
                        : controller.addDependency(source.currentValue || "", target.currentValue || "", relation, lag.text)
                    if (ok) dialog.close()
                }
            }
        }
    }
}
