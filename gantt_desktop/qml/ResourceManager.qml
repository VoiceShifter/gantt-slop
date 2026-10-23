import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "resourceManager"
    property string resourceId: ""
    property var days: [0,1,2,3,4]
    property var projectDays: [0,1,2,3,4]
    readonly property var dayNames: ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    title: "Люди и доступность ресурсов"
    modal: true
    anchors.centerIn: parent
    width: Math.min(790,parent.width-40)
    height: Math.min(600,parent.height-40)
    padding: 20
    onAboutToShow: {
        projectDays=controller.projectWorkdays.slice()
        const catalog=controller.resourceCatalog
        load(resourceId || (catalog.length?catalog[0].id:""))
    }
    function load(id) {
        const resource=controller.resourceCatalog.find(r=>r.id===id)
        resourceId=resource?resource.id:""
        personName.text=resource?resource.name:""
        capacity.text=String(resource?resource.capacity:8)
        days=resource?resource.workdays.slice():[0,1,2,3,4]
    }
    function toggleDay(day, checked, project) {
        let values=(project?projectDays:days).slice()
        if(checked&&values.indexOf(day)<0)values.push(day)
        if(!checked)values=values.filter(value=>value!==day)
        if(project)projectDays=values
        else days=values
    }
    Dialog {
        id: removeDialog
        objectName:"deleteResourceDialog"
        anchors.centerIn:parent
        width:Math.min(430,dialog.width-30)
        title:"Удалить ресурс?"
        implicitHeight:210
        modal:true
        standardButtons:Dialog.Ok|Dialog.Cancel
        contentItem:Label {
            wrapMode:Text.WordWrap
            text:"Ресурс будет удалён из проекта, его назначения сняты. Задачи и их общие трудозатраты сохранятся. Действие можно отменить."
        }
        onAccepted:if(controller.removeResource(dialog.resourceId))dialog.load("")
    }
    ColumnLayout {
        anchors.fill:parent
        spacing:12
        Label { text:"Локальные ресурсы проекта. Без приглашений и учётных записей."; color:"#888888"; font.pixelSize:12 }
        RowLayout {
            Layout.fillWidth:true; Layout.fillHeight:true; spacing:20
            ColumnLayout {
                Layout.preferredWidth:220; Layout.fillHeight:true
                ListView {
                    Layout.fillWidth:true; Layout.fillHeight:true
                    clip:true; model:controller.resourceCatalog
                    delegate:Rectangle {
                        required property var modelData
                        objectName:"resource-list-"+modelData.id
                        width:ListView.view.width; height:39
                        color:modelData.id===dialog.resourceId?"#e7f2fd":"white"
                        Rectangle {
                            x:8; y:9; width:20; height:20; radius:10; color:modelData.color
                            Text { anchors.centerIn:parent; color:"white"; font.pixelSize:10; text:modelData.name.slice(0,1).toUpperCase() }
                        }
                        Text { x:37; width:parent.width-44; height:parent.height; verticalAlignment:Text.AlignVCenter; text:modelData.name; elide:Text.ElideRight; color:"#333333"; font.pixelSize:12 }
                        MouseArea { anchors.fill:parent; onClicked:dialog.load(modelData.id) }
                    }
                    ScrollBar.vertical:ScrollBar {}
                }
                ActionButton { text:"＋ Добавить человека"; objectName:"newResourceButton"; Layout.fillWidth:true; onClicked:dialog.load("") }
            }
            Rectangle { Layout.fillHeight:true; width:1; color:"#e8ebef" }
            ColumnLayout {
                Layout.fillWidth:true; Layout.fillHeight:true; spacing:10
                Label { text:dialog.resourceId?"Календарь ресурса":"Новый ресурс"; font.bold:true }
                Label { text:"Имя"; color:"#888888" }
                CellEditor {
                    id:personName; objectName:"resourceName"
                    Layout.fillWidth:true
                    placeholderText:"Имя или роль"
                    background:Rectangle { color:"white"; border.color:"#ccd4dc"; radius:3 }
                }
                Label { text:"Доступно рабочих часов в день"; color:"#888888" }
                CellEditor {
                    id:capacity; objectName:"resourceCapacity"
                    Layout.preferredWidth:100; text:"8"
                    background:Rectangle { color:"white"; border.color:"#ccd4dc"; radius:3 }
                }
                Label { text:"Рабочие дни ресурса"; color:"#888888" }
                RowLayout {
                    spacing:2
                    Repeater {
                        model:7
                        delegate:Button {
                            required property int index
                            objectName:"resourceDay-"+index
                            text:dialog.dayNames[index]
                            implicitWidth:39; implicitHeight:30
                            checkable:true; checked:dialog.days.indexOf(index)>=0
                            onClicked:dialog.toggleDay(index,checked,false)
                            background:Rectangle { radius:2; color:parent.checked?"#1766cb":"#e6e7e8" }
                            contentItem:Text { text:parent.text; color:parent.checked?"white":"#777777"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter; font.pixelSize:12 }
                        }
                    }
                }
                Label { text:"Доступность влияет на предупреждения, а не переносит задачи."; font.pixelSize:11; color:"#999999"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                Item { Layout.fillHeight:true }
                RowLayout {
                    ActionButton { text:"Удалить"; objectName:"removeResourceButton"; enabled:!!dialog.resourceId; palette.buttonText:"#b93d30"; onClicked:removeDialog.open() }
                    Item { Layout.fillWidth:true }
                    ActionButton {
                        text:"Сохранить ресурс"; primary:true; objectName:"saveResourceButton"
                        onClicked:{
                            const id=controller.saveResource(dialog.resourceId,personName.text,capacity.text,dialog.days)
                            if(id)dialog.load(id)
                        }
                    }
                }
            }
        }
        Rectangle { Layout.fillWidth:true; height:1; color:"#e5e8ec" }
        Label { text:"Рабочие дни проекта · планирование задач"; font.bold:true }
        RowLayout {
            spacing:2
            Repeater {
                model:7
                delegate:Button {
                    required property int index
                    objectName:"projectDay-"+index
                    text:dialog.dayNames[index]; implicitWidth:39; implicitHeight:28
                    checkable:true; checked:dialog.projectDays.indexOf(index)>=0
                    onClicked:dialog.toggleDay(index,checked,true)
                    background:Rectangle { radius:2; color:parent.checked?"#1766cb":"#e6e7e8" }
                    contentItem:Text { text:parent.text; color:parent.checked?"white":"#777777"; horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter; font.pixelSize:12 }
                }
            }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Применить календарь"; objectName:"applyProjectCalendar"; onClicked:controller.setProjectWorkdays(dialog.projectDays) }
        }
        Label {
            Layout.fillWidth:true; wrapMode:Text.WordWrap; color:"#999999"; font.pixelSize:11
            text:"Работа задач в субботу/воскресенье разрешается календарём проекта. Его изменение пересчитывает сроки одной отменяемой операцией. Календарь человека остаётся независимым."
        }
        ActionButton { Layout.alignment:Qt.AlignRight; text:"Закрыть"; objectName:"closeResourcesButton"; onClicked:dialog.close() }
    }
}
