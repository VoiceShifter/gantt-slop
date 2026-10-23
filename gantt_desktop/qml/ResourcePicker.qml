import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "resourcePicker"
    property string taskId: ""
    property var chosen: []
    property var hours: ({})
    property real totalEffort: 0
    signal manageRequested()
    title: "Исполнители и трудозатраты"
    modal: true
    anchors.centerIn: parent
    width: Math.min(580, parent.width-40)
    height: Math.min(470, parent.height-50)
    padding: 20
    onAboutToShow: {
        const task=controller.selected
        chosen=(task.resourceIds||[]).slice()
        totalEffort=task.effortHours||0
        let values={}
        for(let i=0;i<chosen.length;i++) values[chosen[i]]=totalEffort*(task.resourceShares.length?task.resourceShares[i]:1/chosen.length)
        hours=values
    }
    function toggle(id, enabled) {
        let ids=chosen.slice()
        if(enabled && ids.indexOf(id)<0)ids.push(id)
        if(!enabled)ids=ids.filter(value=>value!==id)
        let values={}
        for(let key of ids)values[key]=totalEffort/ids.length
        chosen=ids; hours=values
    }
    function setHours(id, value) {
        let values=Object.assign({},hours)
        values[id]=Number(value.replace(",","."))
        hours=values
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label { text: controller.selected.name||""; font.bold:true; Layout.fillWidth:true; elide:Text.ElideRight }
        Label { text:"Выберите людей. По умолчанию трудозатраты делятся поровну."; font.pixelSize:12; color:"#888888"; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        RowLayout {
            Layout.fillWidth:true
            Label { text:"Ресурс"; color:"#999999"; Layout.fillWidth:true }
            Label { text:"Всего часов"; color:"#999999"; Layout.preferredWidth:100 }
        }
        ScrollView {
            Layout.fillWidth:true; Layout.fillHeight:true
            contentWidth:availableWidth; clip:true
            ColumnLayout {
                width:parent.width; spacing:4
                Repeater {
                    model:controller.resourceCatalog
                    delegate:RowLayout {
                        required property var modelData
                        Layout.fillWidth:true
                        CheckBox {
                            id:choose
                            objectName:"assign-resource-"+modelData.id
                            checked:dialog.chosen.indexOf(modelData.id)>=0
                            indicator:Rectangle {
                                implicitWidth:18; implicitHeight:18; radius:1
                                x:choose.leftPadding; y:(choose.height-height)/2
                                color:choose.checked?"#1766cb":"white"; border.color:choose.checked?color:"#b9bec3"
                                Text { anchors.centerIn:parent; text:choose.checked?"✓":""; color:"white"; font.pixelSize:13 }
                            }
                            onClicked:dialog.toggle(modelData.id,checked)
                        }
                        Rectangle {
                            width:20; height:20; radius:10; color:modelData.color
                            Text { anchors.centerIn:parent; text:modelData.name.slice(0,1).toUpperCase(); color:"white"; font.pixelSize:10 }
                        }
                        Label { text:modelData.name; Layout.fillWidth:true; elide:Text.ElideRight }
                        CellEditor {
                            objectName:"assignmentHours-"+modelData.id
                            Layout.preferredWidth:100
                            enabled:dialog.chosen.indexOf(modelData.id)>=0
                            text:String(Math.round((dialog.hours[modelData.id]===undefined?0:dialog.hours[modelData.id])*100)/100)
                            background:Rectangle { color:"white"; radius:3; border.color:"#d4d9df" }
                            onEditingFinished:if(enabled && text!==String(Math.round((dialog.hours[modelData.id]||0)*100)/100))dialog.setHours(modelData.id,text)
                        }
                    }
                }
                Label { visible:controller.resourceCatalog.length===0; text:"Создайте людей в списке ресурсов."; color:"#999999" }
            }
        }
        RowLayout {
            Layout.fillWidth:true
            ActionButton { text:"Ресурсы…"; onClicked:{dialog.close();dialog.manageRequested()} }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Отмена"; objectName:"cancelResourceAssignment"; onClicked:dialog.close() }
            ActionButton {
                text:"Применить"; primary:true; objectName:"applyResourceAssignment"
                onClicked:{
                    dialog.contentItem.forceActiveFocus()
                    const values=dialog.chosen.map(id=>dialog.hours[id])
                    if(controller.assignResources(dialog.taskId,dialog.chosen,values))dialog.close()
                }
            }
        }
    }
}
