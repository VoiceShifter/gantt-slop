import QtQuick
import QtQuick.Controls

Item {
    id: view
    objectName: "resourceWorkload"
    property real gridWidth: 716
    property real pixelsPerDay: 10
    property real scrollX: 0
    property real sceneWidth: 1800
    property int mode: 0
    property var rows: controller.workloadRows
    property var expanded: ({})
    property var dayRecords: controller.days
    property var monthRecords: controller.months
    property var columns: {
        let result=[]
        if(pixelsPerDay>=18)for(let d of dayRecords)result.push({offset:d.offset,length:1})
        else if(pixelsPerDay>=6)for(let i=0;i<dayRecords.length;i+=7)result.push({offset:i,length:Math.min(7,dayRecords.length-i)})
        else for(let m of monthRecords)result.push({offset:m.offset,length:m.length})
        return result
    }
    property var layoutRows: {
        let result=[], y=0
        for(let resource of rows){
            let ends=[], bars=[]
            const tasks=resource.tasks.slice().sort((a,b)=>a.startDay-b.startDay)
            for(let task of tasks){
                let lane=ends.findIndex(end=>end<=task.startDay)
                if(lane<0)lane=ends.length
                ends[lane]=task.endDay
                bars.push(Object.assign({lane:lane},task))
            }
            const height=30+(expanded[resource.id]?ends.length*26:0)
            result.push({resource:resource,y:y,height:height,bars:bars})
            y+=height
        }
        return result
    }
    readonly property real contentHeight:layoutRows.length?layoutRows[layoutRows.length-1].y+layoutRows[layoutRows.length-1].height:0
    signal manageResource(string id)
    signal inspectTask(string id)
    signal horizontalScroll(real delta)
    signal zoomRequested(int change)
    signal closeRequested()
    onRowsChanged:canvas.requestPaint()
    onColumnsChanged:canvas.requestPaint()
    onPixelsPerDayChanged:canvas.requestPaint()
    onModeChanged:canvas.requestPaint()
    onLayoutRowsChanged:canvas.requestPaint()
    function number(value){return String(Math.round(value*100)/100)}
    function aggregate(resource,column){
        let hours=0,capacity=0,warning=false,weekend=false,ids=[],names=[]
        for(let i=column.offset;i<column.offset+column.length&&i<resource.days.length;i++){
            const day=resource.days[i]
            hours+=day.hours;capacity+=day.capacity
            warning=warning||day.overloaded;weekend=weekend||day.weekendWork
            for(let task of day.tasks)if(ids.indexOf(task.id)<0){ids.push(task.id);names.push(task.name)}
        }
        return {hours:hours,capacity:capacity,warning:warning,weekend:weekend,count:ids.length,names:names}
    }
    function toggle(id){let values=Object.assign({},expanded);values[id]=!values[id];expanded=values}
    component ModeChoice: RadioButton {
        id:choice
        padding:0; spacing:5; implicitHeight:24
        indicator:Rectangle {
            implicitWidth:13; implicitHeight:13; radius:7
            y:(choice.height-height)/2
            color:choice.checked?"#005c51":"#eeeeee"
            border.color:choice.checked?color:"#cccccc"
            Rectangle { anchors.centerIn:parent; width:5; height:5; radius:3; color:"white"; visible:choice.checked }
        }
        contentItem:Text { text:choice.text; leftPadding:choice.indicator.width+choice.spacing; color:"#555555"; font.pixelSize:11; verticalAlignment:Text.AlignVCenter }
    }
    Rectangle { anchors.fill:parent; color:"white" }
    Rectangle { width:parent.width; height:44; color:"white"; border.color:"#dfe3e8" }
    Text { x:24; y:15; text:"Загрузка ресурсов"; font.bold:true; font.pixelSize:13; color:"#333333" }
    ActionButton { x:180; y:7; text:"Люди…"; objectName:"manageResourcesButton"; onClicked:view.manageResource("") }
    Text { x:265; y:16; width:Math.max(0,view.gridWidth-x-15); text:controller.projectName; elide:Text.ElideRight; font.pixelSize:11; color:"#999999" }
    Row {
        x:view.gridWidth+Math.max(12,(view.width-view.gridWidth-width)/2); y:10; spacing:16
        ModeChoice { objectName:"workloadHoursMode"; text:"Часы"; checked:view.mode===0; onClicked:view.mode=0 }
        ModeChoice { objectName:"workloadPercentMode"; text:"Проценты"; checked:view.mode===1; onClicked:view.mode=1 }
        ModeChoice { objectName:"workloadTasksMode"; text:"Задачи"; checked:view.mode===2; onClicked:view.mode=2 }
    }
    ActionButton { anchors.right:parent.right; y:7; text:"×"; hint:"Скрыть загрузку ресурсов"; onClicked:view.closeRequested() }
    Flickable {
        id:body
        objectName:"workloadFlick"
        y:44; width:parent.width; height:parent.height-y
        contentWidth:width; contentHeight:Math.max(height,view.contentHeight)
        clip:true; boundsBehavior:Flickable.StopAtBounds; flickableDirection:Flickable.VerticalFlick
        ScrollBar.vertical:ScrollBar { width:10; policy:ScrollBar.AsNeeded }
        Item {
            width:view.gridWidth; height:body.contentHeight; clip:true
            Repeater {
                model:view.layoutRows
                delegate:Rectangle {
                    required property var modelData
                    objectName:"resource-row-"+modelData.resource.id
                    y:modelData.y; width:view.gridWidth; height:modelData.height
                    color:"white"
                    Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:"#dedede" }
                    Text { x:10; y:9; text:view.expanded[modelData.resource.id]?"▴":"▾"; color:"#7c858a"; font.pixelSize:11 }
                    Rectangle {
                        x:32; y:7; width:16; height:16; radius:8; color:modelData.resource.color
                        Text { anchors.centerIn:parent; text:modelData.resource.name.slice(0,1).toUpperCase(); color:"white"; font.pixelSize:9 }
                    }
                    Text { x:60; y:8; width:parent.width-112; text:modelData.resource.name+(modelData.resource.warningDays?"  ⚠ "+modelData.resource.warningDays:""); font.pixelSize:12; color:"#555555"; font.bold:!!view.expanded[modelData.resource.id]; elide:Text.ElideRight }
                    MouseArea { width:parent.width-36; height:30; cursorShape:Qt.PointingHandCursor; onClicked:view.toggle(modelData.resource.id) }
                    ActionButton { x:parent.width-34; y:2; width:30; text:"▦"; hint:"Календарь ресурса"; objectName:"resource-calendar-"+modelData.resource.id; onClicked:view.manageResource(modelData.resource.id) }
                }
            }
        }
        Item {
            x:view.gridWidth; width:Math.max(0,view.width-x); height:body.contentHeight; clip:true
            Item {
                x:-view.scrollX; width:view.sceneWidth; height:body.contentHeight
                Canvas {
                    id:canvas
                    objectName:"workloadCanvas"
                    anchors.fill:parent
                    onWidthChanged:requestPaint()
                    onHeightChanged:requestPaint()
                    onPaint:{
                        const ctx=getContext("2d")
                        ctx.clearRect(0,0,width,height);ctx.fillStyle="white";ctx.fillRect(0,0,width,height)
                        ctx.font="11px Arial";ctx.textAlign="center";ctx.textBaseline="middle"
                        for(let row of view.layoutRows){
                            const r=row.resource
                            for(let col of view.columns){
                                const data=view.aggregate(r,col), x=col.offset*view.pixelsPerDay,w=col.length*view.pixelsPerDay
                                const day=r.days[col.offset]
                                if(col.length===1&&day&&(day.weekend||data.capacity===0)){ctx.fillStyle="#f3faff";ctx.fillRect(x,row.y,w,30)}
                                if(data.hours>0){
                                    const h=Math.max(1,Math.min(1,data.capacity?data.hours/data.capacity:1)*29)
                                    ctx.fillStyle=data.warning?"rgba(231,76,60,0.1)":data.weekend?"rgba(244,184,61,0.14)":"rgba(80,199,134,0.14)"
                                    ctx.fillRect(x,row.y+30-h,w,h)
                                }
                                let label=view.mode===2?String(data.count):view.mode===1?(data.capacity?view.number(data.hours/data.capacity*100)+"%":data.hours?"!":""):view.number(data.hours)
                                if(data.capacity===0&&data.hours===0&&view.mode!==2)label=""
                                ctx.save();ctx.beginPath();ctx.rect(x,row.y,w,30);ctx.clip()
                                ctx.fillStyle=data.warning?"#b93d30":data.weekend?"#ad7a16":"#129534"
                                ctx.fillText(label,x+w/2,row.y+15);ctx.restore()
                            }
                            ctx.strokeStyle="#dedede";ctx.beginPath();ctx.moveTo(0,row.y+row.height-0.5);ctx.lineTo(width,row.y+row.height-0.5);ctx.stroke()
                        }
                        ctx.strokeStyle="#e8e8e8";ctx.lineWidth=1;ctx.beginPath()
                        for(let col of view.columns){const x=col.offset*view.pixelsPerDay+0.5;ctx.moveTo(x,0);ctx.lineTo(x,height)}
                        ctx.stroke()
                    }
                    MouseArea {
                        anchors.fill:parent; hoverEnabled:true
                        property string hint:""
                        function describe(x,y){
                            const row=view.layoutRows.find(r=>y>=r.y&&y<r.y+30)
                            const col=view.columns.find(c=>x>=c.offset*view.pixelsPerDay&&x<(c.offset+c.length)*view.pixelsPerDay)
                            if(!row||!col)return ""
                            const d=view.aggregate(row.resource,col),date=row.resource.days[col.offset].date
                            return row.resource.name+" · "+date+"\n"+view.number(d.hours)+"ч / "+view.number(d.capacity)+"ч"+(d.warning?" · Перегрузка":"")+(d.weekend?" · Работа в выходной":"")+(d.names.length?"\n"+d.names.join("\n"):"")
                        }
                        onPositionChanged:function(mouse){hint=describe(mouse.x,mouse.y)}
                        onExited:hint=""
                        onClicked:function(mouse){
                            hint=describe(mouse.x,mouse.y)
                            if(!hint)return
                            detail.text=hint;detailPopup.x=Math.max(0,Math.min(view.width-detailPopup.width,view.gridWidth+mouse.x-view.scrollX));detailPopup.y=0;detailPopup.open()
                        }
                        onWheel:function(wheel){
                            if(wheel.modifiers&Qt.ControlModifier)view.zoomRequested(wheel.angleDelta.y>0?-1:1)
                            else if(wheel.angleDelta.x||(wheel.modifiers&Qt.ShiftModifier))view.horizontalScroll(-(wheel.pixelDelta.x||wheel.angleDelta.x||wheel.angleDelta.y))
                            else wheel.accepted=false
                        }
                        ToolTip.visible:containsMouse&&hint.length>0&&!pressed
                        ToolTip.text:hint;ToolTip.delay:400
                    }
                }
                Repeater {
                    model:view.layoutRows
                    delegate:Item {
                        required property var modelData
                        readonly property var row:modelData
                        visible:!!view.expanded[row.resource.id]
                        Repeater {
                            model:row.bars
                            delegate:Item {
                                required property var modelData
                                readonly property var task:modelData
                                objectName:"workload-task-"+row.resource.id+"-"+task.id
                                x:(task.startDay+(task.milestone?0.5:0))*view.pixelsPerDay-(task.milestone?10:0)
                                y:row.y+30+task.lane*26+3
                                width:task.milestone?20:Math.max(6,(task.endDay-task.startDay)*view.pixelsPerDay);height:20
                                Rectangle { anchors.fill:parent; visible:!task.milestone; radius:2; color:task.color }
                                Rectangle { anchors.centerIn:parent; width:14; height:14; rotation:45; color:task.color; visible:task.milestone }
                                Text { anchors.fill:parent; anchors.leftMargin:3; text:task.milestone?"":task.name; color:"white"; font.pixelSize:11; elide:Text.ElideRight; verticalAlignment:Text.AlignVCenter }
                                MouseArea { anchors.fill:parent; cursorShape:Qt.PointingHandCursor; onClicked:view.inspectTask(task.id); ToolTip.visible:containsMouse; hoverEnabled:true; ToolTip.text:task.name }
                            }
                        }
                    }
                }
            }
        }
    }
    Rectangle { x:view.gridWidth-1; y:44; width:1; height:parent.height-44; color:"#d7dce0" }
    Text { anchors.centerIn:body; visible:view.rows.length===0; text:"Добавьте людей и назначьте их задачам"; font.pixelSize:13; color:"#999999" }
    Popup {
        id:detailPopup
        objectName:"workloadDetail"
        width:Math.min(380,view.width-20);padding:14
        background:Rectangle { color:"white"; border.color:"#dce2e8"; radius:3 }
        contentItem:Label { id:detail; objectName:"workloadDetailText"; wrapMode:Text.WordWrap; font.pixelSize:12 }
    }
    Connections { target:controller; function onViewChanged(){detailPopup.close();canvas.requestPaint()} }
}
