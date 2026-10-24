import QtQuick
import QtQuick.Controls

Item {
    id: view
    objectName: "ganttView"
    property real gridWidth: Math.min(716, Math.max(450, width * 0.48))
    property real pixelsPerDay: 10
    property real previousScale: 10
    property real scrollX: 0
    property real gridScroll: 0
    property int hoverRow: -1
    property bool showAssignee: true
    property bool showEffort: true
    property bool showCost: true
    property bool showStart: false
    property bool showEnd: false
    property bool showDuration: false
    property bool showProgress: false
    property bool showStatus: false
    property bool showPriority: false
    property var checkStates: controller.checkStates
    property var checkedIds: controller.checkedIds
    readonly property int rowHeight: 30
    readonly property int headerHeight: 44
    readonly property real sceneWidth: Math.max(width - gridWidth, controller.dayCount * pixelsPerDay)
    readonly property real timelineViewport: Math.max(50, width - gridWidth)
    property alias sceneItem: timelineScene
    property string linkSource: ""
    property bool linkDragging: false
    property real linkPointerX: 0
    property real linkPointerY: 0
    property string sourceEnd: "F"
    property real linkStartX: 0
    property real linkStartY: 0
    property real linkMouseX: 0
    property real linkMouseY: 0
    property var dayRecords: controller.days
    property var linkRecords: controller.links
    property string activeLinkId: ""
    onActiveLinkIdChanged: background.requestPaint()
    signal inspectTask(string taskId)
    signal taskMenuRequested(string taskId)
    signal linkEditRequested(string linkId)
    signal zoomRequested(int change)
    signal cancelDrags()

    property string rowDragId: ""
    property string rowDragLabel: ""
    property bool rowDragging: false
    property real rowPressX: 0
    property real rowPressY: 0
    property real rowPointerX: 0
    property real rowPointerY: 0
    property string rowPlanKey: ""
    property var rowPlan: ({})

    function cancelInteractions() { cancelLink(); cancelDrags(); cancelRowDrag() }
    function beginRowDrag(id, label, x, y) {
        controller.select(id)
        rowDragId=id; rowDragLabel=label; rowPressX=x; rowPressY=y
        rowPointerX=x; rowPointerY=y; rowDragging=false; rowPlanKey=""; rowPlan=({})
    }
    function updateRowDrag(x,y) {
        if (!rowDragId) return
        rowPointerX=x; rowPointerY=y
        if (Math.abs(x-rowPressX)+Math.abs(y-rowPressY)>=3) rowDragging=true
        if (rowDragging) updateRowPlan()
    }
    function updateRowPlan() {
        if (rowPointerX<0 || rowPointerX>gridWidth || rowPointerY<headerHeight || rowPointerY>headerHeight+body.height) {
            rowPlanKey=""; rowPlan=({valid:false,hint:"Отпустите строку в таблице."}); return
        }
        const offset=(rowPointerY-headerHeight+body.contentY)/rowHeight
        const row=Math.floor(offset), fraction=offset-row, inside=rowPointerX+gridScroll>=114
        const zone=fraction<0.25?0:fraction>0.75?3:fraction<0.5?1:2
        const key=row+":"+zone+":"+inside
        if (key!==rowPlanKey) {
            rowPlanKey=key
            rowPlan=controller.rowDropPreview(rowDragId,row,fraction,inside)
        }
    }
    function cancelRowDrag() { rowDragId=""; rowDragging=false; rowPlanKey=""; rowPlan=({}) }
    function finishRowDrag() {
        if (!rowDragId) return
        const id=rowDragId, plan=rowPlan, moved=rowDragging
        cancelRowDrag()
        if (!moved) return
        if (plan.valid) controller.relocateRow(id,plan.target,plan.placement)
        else controller.toast(plan.hint || "Нельзя переместить строку.")
    }

    property var columns: {
        let cols = []
        if (showAssignee) cols.push({key:"assignee", title:"Исполнитель", width:100})
        if (showEffort) cols.push({key:"effort", title:"Трудозатраты", width:100})
        if (showCost) cols.push({key:"cost", title:"Стоимость", width:100})
        if (showStart) cols.push({key:"start", title:"Начало", width:100})
        if (showEnd) cols.push({key:"end", title:"Завершение", width:100})
        if (showDuration) cols.push({key:"duration", title:"Длительность", width:100})
        if (showProgress) cols.push({key:"progress", title:"Прогресс", width:85})
        if (showStatus) cols.push({key:"status", title:"Статус", width:120})
        if (showPriority) cols.push({key:"priority", title:"Приоритет", width:125})
        let used = 0
        for (let c of cols) used += c.width
        cols.unshift({key:"name", title:"Задача", width:Math.max(250, gridWidth - used - 46)})
        let offset = 0
        for (let c of cols) { c.offset = offset; offset += c.width }
        return cols
    }
    readonly property real gridContentWidth: {
        let total = 46
        for (let c of columns) total += c.width
        return total
    }

    function clampScroll() { scrollX = Math.max(0, Math.min(scrollX, sceneWidth - timelineViewport)) }
    function centerDay(day) { scrollX = Math.max(0, Math.min(sceneWidth - timelineViewport, day * pixelsPerDay - timelineViewport * 0.25)) }
    function beginLink(id, end, x, y) {
        linkSource = id; sourceEnd = end; linkDragging = true
        linkStartX = x; linkStartY = y
        background.hoveredLink = ""
        updateLink(x, y)
    }
    function updateLink(x, y) {
        linkMouseX = x; linkMouseY = y
        linkPointerX = gridWidth + x - scrollX
        linkPointerY = headerHeight + y - body.contentY
        background.requestPaint()
    }
    function cancelLink() { linkSource = ""; linkDragging = false; background.requestPaint() }
    function finishLink(x, y) {
        const source = linkSource, end = sourceEnd
        cancelLink()
        if (x<scrollX || x>scrollX+timelineViewport || y<body.contentY || y>body.contentY+body.height) return
        const withinRow=y%rowHeight
        if (withinRow<(rowHeight-22)/2 || withinRow>(rowHeight+22)/2) return
        controller.linkAt(source, end, x / pixelsPerDay, Math.floor(y / rowHeight), pixelsPerDay)
    }
    function connectTo(target, end) {
        const source = linkSource, kind = sourceEnd + end
        cancelLink()
        controller.addDependency(source, target, kind, "0")
    }
    onPixelsPerDayChanged: {
        cancelLink()
        const middle = (scrollX + timelineViewport / 2) / previousScale
        scrollX = Math.max(0, middle * pixelsPerDay - timelineViewport / 2)
        previousScale = pixelsPerDay
        clampScroll()
        background.requestPaint()
    }
    onHoverRowChanged: background.requestPaint()
    onWidthChanged: clampScroll()
    Connections {
        target: controller
        function onViewChanged() { view.cancelLink(); view.cancelRowDrag(); view.clampScroll(); background.hoveredLink=""; background.requestPaint() }
        function onBulkChanged() { if (controller.bulkMode) view.cancelInteractions() }
        function onSelectionChanged() { background.requestPaint() }
        function onFocusRequested(day) { view.centerDay(day) }
    }

    Connections { target: appTheme; function onChanged() { background.requestPaint() } }

    Rectangle { anchors.fill: parent; color: appTheme.colors.surface }
    Item {
        width: view.gridWidth; height: view.headerHeight; clip: true
        Rectangle { anchors.fill: parent; color: appTheme.colors.panel }
        Item {
            x: -view.gridScroll; width: view.gridContentWidth; height: parent.height
            Repeater {
                model: view.columns
                delegate: Rectangle {
                    required property var modelData
                    x: modelData.offset; width: modelData.width; height: view.headerHeight
                    color: appTheme.colors.panel; border.color: appTheme.colors.border
                    Text { anchors.centerIn: parent; text: modelData.title; font.family: "Arial"; font.pixelSize: 12; color: appTheme.colors.text }
                }
            }
            Text { x: view.gridContentWidth - 40; width: 34; height: parent.height; text: "＋"; color: appTheme.colors.muted; font.pixelSize: 22; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        }
    }
    Item {
        x: view.gridWidth; width: view.timelineViewport; height: view.headerHeight; clip: true
        Rectangle { anchors.fill: parent; color: appTheme.colors.panel }
        Item {
            x: -view.scrollX; width: view.sceneWidth; height: parent.height
            Repeater {
                model: controller.months
                delegate: Rectangle {
                    required property var modelData
                    x: modelData.offset * view.pixelsPerDay
                    width: modelData.length * view.pixelsPerDay; height: 20
                    color: appTheme.colors.panel; border.color: appTheme.colors.border; clip: true
                    Text { anchors.centerIn: parent; text: modelData.label; color: appTheme.colors.text; font.pixelSize: 12 }
                }
            }
            Repeater {
                model: view.dayRecords
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool daily: view.pixelsPerDay >= 18
                    visible: daily || (view.pixelsPerDay >= 6 && modelData.monday)
                    x: modelData.offset * view.pixelsPerDay; y: 20
                    width: (daily ? 1 : 7) * view.pixelsPerDay; height: 24
                    color: daily && modelData.weekend ? appTheme.colors.weekend : appTheme.colors.panel
                    border.color: appTheme.colors.border
                    Text {
                        anchors.centerIn: parent
                        text: parent.daily ? String(modelData.number).padStart(2,"0") + "\n" + modelData.weekday
                              : modelData.number + "–" + view.dayRecords[Math.min(modelData.offset + 6, view.dayRecords.length - 1)].number + " (" + modelData.week + "н)"
                        color: parent.daily && modelData.weekend ? appTheme.colors.link : appTheme.colors.text
                        font.pixelSize: parent.daily ? 10 : 11
                        horizontalAlignment: Text.AlignHCenter
                        lineHeight: 0.9
                    }
                }
            }
        }
    }
    Flickable {
        id: body
        objectName: "bodyFlick"
        y: view.headerHeight; width: parent.width; height: parent.height - y - 16
        contentWidth: width
        contentHeight: Math.max(height, controller.rowCount * view.rowHeight)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 10 }

        Item {
            width: view.gridWidth; height: body.contentHeight; clip: true
            Rectangle { anchors.fill: parent; color: appTheme.colors.surface }
            Item {
                x: -view.gridScroll; width: view.gridContentWidth; height: body.contentHeight
                Repeater {
                    model: controller.model
                    delegate: Rectangle {
                        id: gridRow
                        required property var rowData
                        required property int index
                        readonly property bool marked: view.checkedIds.indexOf(rowData.taskId)>=0
                        readonly property real textOpacity: controller.bulkMode && !marked ? 0.45 : rowData.status==="closed" ? 0.55 : 1
                        objectName: "task-row-" + (rowData.taskId || "add")
                        x: 0; y: index * view.rowHeight
                        width: view.gridContentWidth; height: view.rowHeight
                        color: controller.bulkMode ? (marked?appTheme.colors.bulkSelection:appTheme.colors.surface) : rowData.taskId && controller.selectedId === rowData.taskId ? appTheme.colors.selection : view.hoverRow === index ? appTheme.colors.hover : appTheme.colors.surface
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: appTheme.colors.grid }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onEntered: view.hoverRow = gridRow.index
                            onExited: if (view.hoverRow === gridRow.index) view.hoverRow = -1
                            onClicked: function(mouse) {
                                if (gridRow.rowData.rowKind !== "task") return
                                controller.select(gridRow.rowData.taskId)
                                if (mouse.button === Qt.RightButton) view.taskMenuRequested(gridRow.rowData.taskId)
                            }
                            onDoubleClicked: if (gridRow.rowData.rowKind === "task") view.inspectTask(gridRow.rowData.taskId)
                        }
                        Item {
                            visible: gridRow.rowData.rowKind === "task"
                            opacity: gridRow.textOpacity
                            width: view.columns[0].width; height: parent.height
                            Text {
                                x: 30; width: 54; height: parent.height
                                text: gridRow.rowData.outline || ""
                                visible: !controller.bulkMode
                                color: appTheme.colors.text; font.pixelSize: 12
                                font.bold: gridRow.rowData.summary || false
                                verticalAlignment: Text.AlignVCenter
                            }
                            Rectangle {
                                x: 94 + (gridRow.rowData.level || 0) * 14; y: 11; width: 9; height: 9
                                visible: gridRow.rowData.summary || false
                                color: appTheme.colors.input; border.color: appTheme.colors.secondary; radius: 1
                                Rectangle { x: 2; y: 4; width: 5; height: 1; color: appTheme.colors.secondary }
                                Rectangle { x: 4; y: 2; width: 1; height: 5; color: appTheme.colors.secondary; visible: !gridRow.rowData.expanded }
                                MouseArea { anchors.fill: parent; anchors.margins: -7; onClicked: controller.toggleGroup(gridRow.rowData.taskId) }
                            }
                            CellEditor {
                                objectName: "task-name-" + (gridRow.rowData.taskId || "")
                                x: 114 + (gridRow.rowData.level || 0) * 14
                                width: Math.max(60, parent.width - x - 5); height: parent.height
                                text: gridRow.rowData.name || ""
                                font.bold: gridRow.rowData.summary || false
                                font.strikeout: gridRow.rowData.status === "closed"
                                onActiveFocusChanged: if (activeFocus && gridRow.rowData.rowKind === "task") controller.select(gridRow.rowData.taskId)
                                onEditingFinished: {
                                    if (gridRow.rowData.rowKind === "task" && text !== gridRow.rowData.name) {
                                        if (!controller.editField(gridRow.rowData.taskId, "name", text)) text = gridRow.rowData.name
                                    }
                                }
                            }
                        }
                        Repeater {
                            model: view.columns.slice(1)
                            delegate: Item {
                                id: columnCell
                                required property var modelData
                                readonly property bool metadata: ["status","priority"].indexOf(modelData.key)>=0 && gridRow.rowData.rowKind==="task" && !gridRow.rowData.summary
                                x: modelData.offset; width: modelData.width; height: view.rowHeight
                                opacity: gridRow.textOpacity
                                Rectangle { width: 1; height: parent.height; color: appTheme.colors.grid }
                                Rectangle {
                                    x: 9; y: 6; width: 18; height: 18; radius: 9
                                    visible: columnCell.modelData.key === "assignee" && !!gridRow.rowData.assignee
                                    color: gridRow.rowData.assigneeColor || "#829da7"
                                    Text { anchors.centerIn: parent; text: (gridRow.rowData.assignee || "").slice(0,1).toUpperCase(); color: "white"; font.pixelSize: 10 }
                                }
                                CellEditor {
                                    id: valueField
                                    readonly property string key: columnCell.modelData.key
                                    function displayValue() {
                                        const value = gridRow.rowData[key]
                                        if (value === undefined) return ""
                                        if (key === "duration") return value + "ч"
                                        if (key === "progress") return Math.round(value) + "%"
                                        if (key === "status") return gridRow.rowData.statusText || ""
                                        if (key === "priority") return gridRow.rowData.priorityText || ""
                                        return String(value)
                                    }
                                    x: key === "assignee" && !!gridRow.rowData.assignee ? 26 : 0
                                    width: parent.width - x; height: parent.height
                                    text: displayValue()
                                    visible: !columnCell.metadata
                                    horizontalAlignment: ["cost","effort","duration","progress"].indexOf(key) >= 0 ? Text.AlignRight : Text.AlignLeft
                                    color: gridRow.rowData.rowKind === "total" ? appTheme.colors.muted : appTheme.colors.text
                                    font.bold: gridRow.rowData.summary || false
                                    font.strikeout: gridRow.rowData.status === "closed"
                                    readOnly: gridRow.rowData.rowKind !== "task" ||
                                              (gridRow.rowData.summary && key !== "start") ||
                                              (key === "start" && !gridRow.rowData.canMove) ||
                                              (key === "end" && !gridRow.rowData.canResizeEnd) ||
                                              (key === "duration" && gridRow.rowData.milestone)
                                    onActiveFocusChanged: {
                                        if (activeFocus && gridRow.rowData.rowKind === "task") {
                                            controller.select(gridRow.rowData.taskId)
                                            if (key === "cost") text = String(gridRow.rowData.costValue)
                                        }
                                    }
                                    onEditingFinished: {
                                        if (readOnly) return
                                        if (text !== displayValue()) {
                                            const value = text.replace("%", "")
                                            if (!controller.editField(gridRow.rowData.taskId, key, value)) text = displayValue()
                                        }
                                    }
                                }
                                MetadataChoice {
                                    x:1; y:1; width:parent.width-2; height:28
                                    visible: columnCell.metadata
                                    enabled: !controller.bulkMode
                                    compact:true
                                    model: columnCell.metadata ? (columnCell.modelData.key==="status"?controller.statusChoices:controller.priorityChoices) : []
                                    currentIndex: indexOfValue(gridRow.rowData[columnCell.modelData.key] || "")
                                    onActivated: controller.editField(gridRow.rowData.taskId,columnCell.modelData.key,currentValue)
                                }
                            }
                        }
                        ActionButton {
                            x: view.gridContentWidth - 43; width: 40; height: view.rowHeight
                            text: "⋯"; font.pixelSize: 17
                            visible: !controller.bulkMode && gridRow.rowData.rowKind === "task" && (view.hoverRow === gridRow.index || controller.selectedId === gridRow.rowData.taskId)
                            hint: "Действия с задачей"
                            onClicked: view.taskMenuRequested(gridRow.rowData.taskId)
                        }
                        Item {
                            x:4; width:24; height:view.rowHeight
                            visible: !controller.bulkMode && gridRow.rowData.rowKind==="task"
                            opacity: view.hoverRow===gridRow.index || view.rowDragId===gridRow.rowData.taskId ? 1 : 0
                            Repeater {
                                model:6
                                delegate:Rectangle {
                                    required property int index
                                    x:8+(index%2)*4; y:10+Math.floor(index/2)*4
                                    width:2; height:2; radius:1; color:appTheme.colors.muted
                                }
                            }
                            MouseArea {
                                id:rowGrip
                                objectName:"row-grip-"+(gridRow.rowData.taskId||"")
                                anchors.fill:parent; hoverEnabled:true; preventStealing:true
                                cursorShape: view.rowDragging?Qt.ClosedHandCursor:Qt.SizeVerCursor
                                onEntered:view.hoverRow=gridRow.index
                                onPressed:function(mouse){const p=mapToItem(view,mouse.x,mouse.y);view.beginRowDrag(gridRow.rowData.taskId,gridRow.rowData.name,p.x,p.y)}
                                onPositionChanged:function(mouse){if(pressed){const p=mapToItem(view,mouse.x,mouse.y);view.updateRowDrag(p.x,p.y)}}
                                onReleased:function(mouse){const p=mapToItem(view,mouse.x,mouse.y);view.updateRowDrag(p.x,p.y);view.finishRowDrag()}
                                onCanceled:view.cancelRowDrag()
                            }
                        }
                        MouseArea {
                            anchors.fill:parent; z:3; hoverEnabled:true
                            visible:controller.bulkMode && gridRow.rowData.rowKind==="task"
                            acceptedButtons:Qt.LeftButton|Qt.RightButton
                            onEntered:view.hoverRow=gridRow.index
                            onClicked:function(mouse){if(mouse.button===Qt.LeftButton)controller.toggleChecked(gridRow.rowData.taskId)}
                        }
                        CheckBox {
                            objectName:"bulk-check-"+(gridRow.rowData.taskId||"")
                            x:4; width:24; height:view.rowHeight; z:4
                            visible:controller.bulkMode && gridRow.rowData.rowKind!=="add"
                            enabled:gridRow.rowData.rowKind==="task" || controller.taskCount>0
                            tristate:true
                            checkState:view.checkStates[gridRow.rowData.taskId]||0
                            nextCheckState:function(){return checkState}
                            onClicked: {
                                if(gridRow.rowData.rowKind==="total")controller.setAllChecked((view.checkStates.__total__||0)!==Qt.Checked)
                                else controller.toggleChecked(gridRow.rowData.taskId)
                            }
                            indicator:Rectangle {
                                x:3; anchors.verticalCenter:parent.verticalCenter
                                width:17; height:17; radius:1
                                color:parent.checkState===Qt.Checked?appTheme.colors.accent:parent.checkState===Qt.PartiallyChecked?appTheme.colors.secondary:appTheme.colors.input
                                border.color:parent.checkState===Qt.Unchecked?appTheme.colors.strongBorder:color
                                Text { anchors.centerIn:parent; text:parent.parent.checkState===Qt.Checked?"✓":parent.parent.checkState===Qt.PartiallyChecked?"−":"";color:"white";font.pixelSize:13 }
                            }
                        }
                        Row {
                            visible: gridRow.rowData.rowKind === "add"
                            enabled: !controller.bulkMode
                            x: 114 + (gridRow.rowData.level || 0) * 14; height: parent.height
                            ActionButton { text: "⊕  Добавить задачу"; palette.buttonText: appTheme.colors.link; onClicked: controller.addTask(gridRow.rowData.parentId, "task") }
                            Text { height: parent.height; text: " | "; color: appTheme.colors.muted; verticalAlignment: Text.AlignVCenter }
                            ActionButton { text: "Добавить веху"; palette.buttonText: appTheme.colors.link; onClicked: controller.addTask(gridRow.rowData.parentId, "milestone") }
                        }
                    }
                }
            }
        }
        Item {
            x: view.gridWidth; width: view.timelineViewport; height: body.contentHeight; clip: true
            Item {
                id: timelineScene
                x: -view.scrollX; width: view.sceneWidth; height: body.contentHeight
                Canvas {
                    id: background
                    objectName: "chartCanvas"
                    anchors.fill: parent
                    property var paths: []
                    property string hoveredLink: ""
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0,0,width,height)
                        ctx.fillStyle = appTheme.colors.surface; ctx.fillRect(0,0,width,height)
                        if (view.pixelsPerDay >= 18) {
                            ctx.fillStyle = appTheme.colors.weekend
                            for (let d of view.dayRecords) if (d.weekend) ctx.fillRect(d.offset * view.pixelsPerDay,0,view.pixelsPerDay,height)
                        }
                        const selected = controller.selectedId
                        for (let i = 0; i < controller.rowCount; i++) {
                            if (i === view.hoverRow) { ctx.fillStyle = appTheme.colors.hover; ctx.fillRect(0,i*view.rowHeight,width,view.rowHeight) }
                        }
                        ctx.strokeStyle = appTheme.colors.grid; ctx.lineWidth = 1
                        ctx.beginPath()
                        for (let d of view.dayRecords) {
                            if (view.pixelsPerDay >= 18 || (view.pixelsPerDay >= 6 && d.monday)) {
                                const x = Math.round(d.offset * view.pixelsPerDay) + 0.5
                                ctx.moveTo(x,0); ctx.lineTo(x,height)
                            }
                            if (d.today) { ctx.fillStyle = appTheme.colors.accent; ctx.fillRect(d.offset * view.pixelsPerDay,0,1,height) }
                        }
                        for (let i=0; i<=controller.rowCount; i++) { ctx.moveTo(0,i*view.rowHeight+0.5); ctx.lineTo(width,i*view.rowHeight+0.5) }
                        ctx.stroke()
                        let hitPaths = []
                        for (let link of view.linkRecords) {
                            const sx=link.sx*view.pixelsPerDay+(link.sourceMilestone?(link.sourceFinish?14:-14):link.sourceFinish?Math.max(0,6-link.sourceSpan*view.pixelsPerDay):0)
                            const tx=link.tx*view.pixelsPerDay+(link.targetMilestone?(link.targetFinish?14:-14):link.targetFinish?Math.max(0,6-link.targetSpan*view.pixelsPerDay):0)
                            const sy=(link.sourceRow+0.5)*view.rowHeight+(link.sourceSummary?8.5:0)
                            const ty=(link.targetRow+0.5)*view.rowHeight+(link.targetSummary?8.5:0)
                            const stubS=sx+(link.sourceFinish?12:-12), stubT=tx+(link.targetFinish?12:-12)
                            let points
                            if (link.sourceFinish && !link.targetFinish && stubS <= stubT) {
                                const middle=(stubS+stubT)/2
                                points=[[sx,sy],[middle,sy],[middle,ty],[tx,ty]]
                            } else {
                                const midY=sy+(ty>=sy?view.rowHeight/2:-view.rowHeight/2)
                                points=[[sx,sy],[stubS,sy],[stubS,midY],[stubT,midY],[stubT,ty],[tx,ty]]
                            }
                            const highlighted=hoveredLink===link.id || view.activeLinkId===link.id
                            const color=highlighted?appTheme.colors.link:"#ffa726"
                            ctx.strokeStyle=color; ctx.lineWidth=highlighted?2.5:1.4
                            ctx.beginPath(); ctx.moveTo(points[0][0],points[0][1])
                            for (let p of points.slice(1)) ctx.lineTo(p[0],p[1])
                            ctx.stroke()
                            const direction=link.targetFinish?-1:1
                            ctx.fillStyle=color; ctx.beginPath()
                            ctx.moveTo(tx,ty); ctx.lineTo(tx-direction*5,ty-3); ctx.lineTo(tx-direction*5,ty+3); ctx.closePath(); ctx.fill()
                            hitPaths.push({id:link.id,points:points,label:link.label})
                        }
                        paths=hitPaths
                        if (view.linkSource) {
                            ctx.strokeStyle=appTheme.colors.link; ctx.lineWidth=1.5; ctx.setLineDash([5,3])
                            ctx.beginPath(); ctx.moveTo(view.linkStartX,view.linkStartY); ctx.lineTo(view.linkMouseX,view.linkMouseY); ctx.stroke(); ctx.setLineDash([])
                        }
                    }
                    function linkAt(x,y) {
                        for (let path of paths) {
                            for (let i=1;i<path.points.length;i++) {
                                const a=path.points[i-1],b=path.points[i]
                                if (a[0]===b[0] && Math.abs(x-a[0])<6 && y>=Math.min(a[1],b[1])-4 && y<=Math.max(a[1],b[1])+4) return path
                                if (a[1]===b[1] && Math.abs(y-a[1])<6 && x>=Math.min(a[0],b[0])-4 && x<=Math.max(a[0],b[0])+4) return path
                            }
                        }
                        return null
                    }
                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true; preventStealing: true
                        property real downX: 0
                        property real downY: 0
                        property real oldX: 0
                        property real oldY: 0
                        property bool panned: false
                        property string hint: ""
                        cursorShape: background.hoveredLink ? Qt.PointingHandCursor : pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        onPressed: function(mouse) {
                            const point=mapToItem(view,mouse.x,mouse.y)
                            downX=point.x; downY=point.y; oldX=view.scrollX; oldY=body.contentY; panned=false
                        }
                        onPositionChanged: function(mouse) {
                            if (pressed) {
                                const point=mapToItem(view,mouse.x,mouse.y)
                                if (Math.abs(point.x-downX)+Math.abs(point.y-downY)>3) panned=true
                                if (panned) {
                                    view.scrollX=Math.max(0,Math.min(view.sceneWidth-view.timelineViewport,oldX-(point.x-downX)))
                                    body.contentY=Math.max(0,Math.min(body.contentHeight-body.height,oldY-(point.y-downY)))
                                }
                            } else {
                                const hit=background.linkAt(mouse.x,mouse.y)
                                background.hoveredLink=hit?hit.id:""; hint=hit?hit.label:""; background.requestPaint()
                            }
                        }
                        onExited: { background.hoveredLink=""; hint=""; background.requestPaint() }
                        onClicked: function(mouse) {
                            if (!panned) {
                                const hit=background.linkAt(mouse.x,mouse.y)
                                if (hit) view.linkEditRequested(hit.id)
                                else if (view.linkSource) view.cancelLink()
                                else controller.select("")
                            }
                        }
                        onWheel: function(wheel) {
                            if (wheel.modifiers & Qt.ControlModifier) {
                                view.zoomRequested(wheel.angleDelta.y>0?-1:1)
                            } else if (wheel.angleDelta.x || (wheel.modifiers & Qt.ShiftModifier)) {
                                const delta=wheel.pixelDelta.x || wheel.angleDelta.x || wheel.angleDelta.y
                                view.scrollX=Math.max(0,Math.min(view.sceneWidth-view.timelineViewport,view.scrollX-delta))
                            } else wheel.accepted=false
                        }
                        ToolTip.visible: hint.length>0 && containsMouse && !pressed
                        ToolTip.text: hint
                        ToolTip.delay: 500
                    }
                }
                HoverHandler {
                    enabled: !!view.linkSource
                    onPointChanged: if (view.linkSource) view.updateLink(point.position.x, point.position.y)
                }
                Repeater {
                    model: controller.model
                    delegate: Item {
                        id: barRow
                        required property var rowData
                        required property int index
                        Loader {
                            active: barRow.rowData.rowKind === "task"
                            sourceComponent: Component { TaskBar { task: barRow.rowData; rowIndex: barRow.index; workspace: view } }
                        }
                        Rectangle {
                            visible: barRow.rowData.rowKind === "total"
                            x: (barRow.rowData.startDay || 0)*view.pixelsPerDay
                            y: barRow.index*view.rowHeight+13
                            width: Math.max(0,((barRow.rowData.endDay||0)-(barRow.rowData.startDay||0))*view.pixelsPerDay)
                            height: 5; color: appTheme.colors.muted
                            Rectangle { x:0; y:-3; width:2; height:11; color:parent.color }
                            Rectangle { anchors.right:parent.right; y:-3; width:2; height:11; color:parent.color }
                        }
                    }
                }
            }
        }
    }
    Timer {
        interval:30; repeat:true; running:view.linkDragging && !!view.linkSource
        onTriggered: {
            const x=view.linkPointerX, y=view.linkPointerY
            if(x<view.gridWidth || x>view.width || y<view.headerHeight || y>view.headerHeight+body.height) return
            let dx=x<view.gridWidth+24?-12:x>view.width-24?12:0
            let dy=y<view.headerHeight+24?-12:y>view.headerHeight+body.height-24?12:0
            view.scrollX=Math.max(0,Math.min(view.sceneWidth-view.timelineViewport,view.scrollX+dx))
            body.contentY=Math.max(0,Math.min(body.contentHeight-body.height,body.contentY+dy))
            view.linkMouseX=x-view.gridWidth+view.scrollX
            view.linkMouseY=y-view.headerHeight+body.contentY
            background.requestPaint()
        }
    }
    Timer {
        interval:30; repeat:true; running:view.rowDragging
        onTriggered: {
            let next=body.contentY
            if(view.rowPointerY<view.headerHeight+24)next-=12
            else if(view.rowPointerY>view.headerHeight+body.height-24)next+=12
            next=Math.max(0,Math.min(body.contentHeight-body.height,next))
            if(next!==body.contentY){body.contentY=next;view.updateRowPlan()}
        }
    }
    Item {
        x:0; y:view.headerHeight; width:view.gridWidth; height:body.height; clip:true; z:20
        Rectangle {
            visible:view.rowDragging && !!view.rowPlan.valid
            x:30
            y:(view.rowPlan.row||0)*view.rowHeight-body.contentY+(view.rowPlan.edge>0?view.rowHeight:0)
            width:parent.width-x; height:view.rowPlan.edge===0?view.rowHeight:2
            color:view.rowPlan.edge===0?appTheme.colors.selectionTint:appTheme.colors.link
            border.width:view.rowPlan.edge===0?1:0; border.color:appTheme.colors.link
        }
    }
    Rectangle {
        objectName:"rowDragGhost"
        visible:view.rowDragging
        x:Math.max(10,Math.min(view.gridWidth-270,view.rowPointerX+12))
        y:Math.max(view.headerHeight,Math.min(view.height-60,view.rowPointerY+14))
        z:30; width:260; height:48; radius:4; color:appTheme.colors.raised
        border.color:view.rowPlan.valid?appTheme.colors.link:appTheme.colors.danger
        Column {
            x:10; y:7; width:parent.width-20; spacing:5
            Text { width:parent.width; text:view.rowDragLabel; textFormat:Text.PlainText; font.bold:true; font.pixelSize:12; elide:Text.ElideRight; color:appTheme.colors.text }
            Text { width:parent.width; text:view.rowPlan.hint||"";textFormat:Text.PlainText;font.pixelSize:11;elide:Text.ElideRight;color:appTheme.colors.secondary }
        }
    }
    Rectangle { x: view.gridWidth-1; width: 2; height: parent.height; color: appTheme.colors.border }
    MouseArea {
        objectName: "gridDivider"
        x: view.gridWidth-4; width: 8; height: parent.height
        cursorShape: Qt.SplitHCursor
        preventStealing: true
        onPositionChanged: function(mouse) {
            if (pressed) view.gridWidth=Math.max(380,Math.min(view.width-180,mapToItem(view,mouse.x,mouse.y).x))
        }
    }
    ScrollBar {
        id: horizontal
        objectName: "timelineScroll"
        x: view.gridWidth; y: parent.height-15; width: view.timelineViewport; height: 15
        orientation: Qt.Horizontal
        policy: ScrollBar.AlwaysOn
        size: Math.min(1,view.timelineViewport/view.sceneWidth)
        position: view.scrollX/view.sceneWidth
        onPositionChanged: if (pressed) view.scrollX=position*view.sceneWidth
    }
    ScrollBar {
        x:0; y:parent.height-15; width:view.gridWidth; height:15
        orientation: Qt.Horizontal
        policy: view.gridContentWidth>view.gridWidth ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        size:Math.min(1,view.gridWidth/view.gridContentWidth)
        position:view.gridScroll/view.gridContentWidth
        onPositionChanged: if (pressed) view.gridScroll=position*view.gridContentWidth
    }
    Text {
        anchors.centerIn: body
        visible: controller.taskCount===0 || controller.rowCount<=1
        text: controller.taskCount===0 ? "Начните с задачи или группы\nПеретащите блок, чтобы изменить даты" : "Нет задач по заданному фильтру"
        color:appTheme.colors.muted; font.pixelSize:16; lineHeight:1.6
        horizontalAlignment:Text.AlignHCenter
    }
}
