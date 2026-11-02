import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: view
    objectName: "ganttView"
    property real gridWidth: Math.min(716, Math.max(450, width * 0.48))
    property real pixelsPerDay: 10
    property real previousScale: 10
    property real scrollX: 0
    property real gridScroll: 0
    property var columnWidths: ({})
    property var hiddenCustomFields: []
    property var customFields: controller.customFields
    property bool viewportReady: false
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
    property bool showDeadline: false
    property bool showBaselineStart: false
    property bool showBaselineEnd: false
    property bool showStartVariance: false
    property bool showEndVariance: false
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
    signal fieldsRequested()
    signal assigneePickerRequested(string taskId, var anchor)

    property string rowDragId: ""
    property string rowDragLabel: ""
    property bool rowDragging: false
    property real rowPressX: 0
    property real rowPressY: 0
    property real rowPointerX: 0
    property real rowPointerY: 0
    property string rowPlanKey: ""
    property var rowPlan: ({})

    function cancelInteractions() { columnResizer.cancelResize(); cancelLink(); cancelDrags(); cancelRowDrag() }
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
            rowPlanKey=""; rowPlan=({valid:false,hint:i18n.tr.drop_row_hint}); return
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
        else controller.toast(plan.hint || i18n.tr.cannot_move_row)
    }

    property var columns: {
        let cols = []
        if (showAssignee) cols.push({key:"assignee", title:i18n.tr.col_assignee, width:100})
        if (showEffort) cols.push({key:"effort", title:i18n.tr.col_effort, width:100})
        if (showCost) cols.push({key:"cost", title:i18n.tr.col_cost, width:100})
        if (showStart) cols.push({key:"start", title:i18n.tr.col_start, width:100})
        if (showEnd) cols.push({key:"end", title:i18n.tr.col_end, width:100})
        if (showDeadline) cols.push({key:"deadline", title:i18n.tr.col_deadline, width:120})
        if (showDuration) cols.push({key:"duration", title:i18n.tr.col_duration, width:100})
        if (showProgress) cols.push({key:"progress", title:i18n.tr.col_progress, width:85})
        if (showStatus) cols.push({key:"status", title:i18n.tr.col_status, width:120})
        if (showPriority) cols.push({key:"priority", title:i18n.tr.col_priority, width:125})
        if (showBaselineStart) cols.push({key:"baselineStart", title:i18n.tr.col_baseline_start, width:150})
        if (showBaselineEnd) cols.push({key:"baselineEnd", title:i18n.tr.col_baseline_end, width:160})
        if (showStartVariance) cols.push({key:"startVariance", title:i18n.tr.col_start_variance, width:140})
        if (showEndVariance) cols.push({key:"endVariance", title:i18n.tr.col_end_variance, width:160})
        for (let f of customFields) if (hiddenCustomFields.indexOf(f.id)<0)
            cols.push({key:f.key, title:f.name, width:160, customId:f.id, kind:f.kind})
        let used = 0
        for (let c of cols) { c.width = columnWidths[c.key] || c.width; used += c.width }
        cols.unshift({key:"name", title:i18n.tr.col_name, width:columnWidths.name || Math.max(250, gridWidth - used - 46)})
        let offset = 0
        for (let c of cols) { c.offset = offset; offset += c.width }
        return cols
    }
    readonly property real gridContentWidth: {
        let total = 46
        for (let c of columns) total += c.width
        return total
    }

    function columnVisibility() {
        const shown={assignee:showAssignee,effort:showEffort,cost:showCost,start:showStart,end:showEnd,
                     duration:showDuration,progress:showProgress,status:showStatus,priority:showPriority,deadline:showDeadline,baselineStart:showBaselineStart,baselineEnd:showBaselineEnd,
                     startVariance:showStartVariance,endVariance:showEndVariance}
        for (let f of customFields) shown[f.key]=hiddenCustomFields.indexOf(f.id)<0
        return shown
    }
    function setColumnVisible(key, shown) {
        if (key.indexOf("custom:")===0) {
            const id=key.slice(7)
            hiddenCustomFields=shown?hiddenCustomFields.filter(value=>value!==id):hiddenCustomFields.concat([id])
        } else {
            const properties={assignee:"showAssignee",effort:"showEffort",cost:"showCost",start:"showStart",
                              end:"showEnd",duration:"showDuration",progress:"showProgress",status:"showStatus",priority:"showPriority",deadline:"showDeadline",baselineStart:"showBaselineStart",baselineEnd:"showBaselineEnd",
                              startVariance:"showStartVariance",endVariance:"showEndVariance"}
            view[properties[key]]=shown
        }
    }
    function revealColumn(key) {
        const column=columns.find(c=>c.key===key)
        if (column) { gridScroll=Math.max(0,column.offset+column.width+46-gridWidth); clampGridScroll() }
    }
    function clampGridScroll() { gridScroll = Math.max(0, Math.min(gridScroll, gridContentWidth - gridWidth)) }
    function boundedGridWidth(value) { return Math.min(Math.max(180,width-180),Math.max(380,value)) }
    function fitGridViewport() {
        if (width>0 && gridWidth>Math.max(180,width-180)) gridWidth=Math.max(180,width-180)
        clampGridScroll(); clampScroll()
    }
    function resetColumnWidths() {
        columnResizer.cancelResize()
        columnWidths = ({})
        gridWidth = boundedGridWidth(Math.min(716, Math.max(450, width * 0.48)))
        gridScroll = 0
    }
    function columnEdgeAt(x) {
        for (let i=0; i<columns.length; i++) if (Math.abs(x-columns[i].offset-columns[i].width)<=5) return i
        return -1
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
    onWidthChanged: if (viewportReady) Qt.callLater(fitGridViewport)
    onGridWidthChanged: { clampGridScroll(); clampScroll() }
    onGridContentWidthChanged: clampGridScroll()
    // Enforce the viewport ceiling only after the initial layouts have settled.
    Connections {
        target: view.Window.window
        function onFrameSwapped() {
            if (!view.viewportReady) { view.viewportReady=true; view.fitGridViewport() }
        }
    }
    Connections {
        target: controller
        function onViewChanged() { view.cancelLink(); view.cancelRowDrag(); view.clampScroll(); background.hoveredLink=""; background.requestPaint() }
        function onBulkChanged() { if (controller.bulkMode) view.cancelInteractions() }
        function onSelectionChanged() { background.requestPaint() }
        function onFocusRequested(day) { view.centerDay(day) }
        function onCustomFieldCreated(id) { Qt.callLater(function() { view.revealColumn("custom:"+id) }) }
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
                    objectName: "column-header-" + modelData.key
                    x: modelData.offset; width: modelData.width; height: view.headerHeight
                    color: appTheme.colors.panel; border.color: appTheme.colors.border
                    Text {
                        anchors.fill: parent; anchors.margins: 8
                        text: modelData.title; font.family: "Arial"; font.pixelSize: 12; color: appTheme.colors.text
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight; clip: true
                    }
                }
            }
        }
        Rectangle {
            id: addColumnSlot
            x: Math.max(0,Math.min(view.gridWidth,view.gridContentWidth)-46)
            width: 46; height: parent.height; color: appTheme.colors.panel
            ActionButton {
                objectName: "addColumnButton"
                x: 6; width: 34; height: parent.height
                text: "＋"; font.pixelSize: 22; hint: i18n.tr.add_fields_hint
                onClicked: view.fieldsRequested()
            }
        }
        MouseArea {
            id: columnResizer
            objectName: "columnResizer"
            anchors.fill: parent; hoverEnabled: true; preventStealing: true
            property int hoveredIndex: -1
            property string key: ""
            property real downX: 0
            property real startWidth: 0
            property real startGridWidth: 0
            property real startScroll: 0
            property var savedWidths: ({})
            property var frozenWidths: ({})
            property bool moved: false
            cursorShape: key || hoveredIndex>=0 ? Qt.SplitHCursor : Qt.ArrowCursor
            function hitIndex(x) { return x<=addColumnSlot.x+5 ? view.columnEdgeAt(x+view.gridScroll) : -1 }
            function resizeAt(x) {
                if (!key) return
                const size=Math.max(key==="name"?250:64,Math.round(startWidth+x-downX))
                if (size===startWidth && !moved) return
                moved=true
                const widths=Object.assign({},frozenWidths)
                widths[key]=size
                const grid=view.boundedGridWidth(startGridWidth+size-startWidth)
                if (grid<view.gridWidth) view.gridWidth=grid
                view.columnWidths=widths
                view.gridWidth=grid
            }
            function cancelResize() {
                if (!key) return
                key=""
                view.columnWidths=savedWidths
                view.gridWidth=startGridWidth
                view.gridScroll=startScroll
                view.clampGridScroll()
                hoveredIndex=-1
            }
            onPressed: function(mouse) {
                const index=hitIndex(mouse.x)
                if (index<0) { mouse.accepted=false; return }
                view.cancelInteractions(); view.forceActiveFocus()
                key=view.columns[index].key; startWidth=view.columns[index].width
                downX=mouse.x; startGridWidth=view.gridWidth; startScroll=view.gridScroll
                savedWidths=view.columnWidths
                const widths=Object.assign({},savedWidths)
                for (let column of view.columns) widths[column.key]=column.width
                frozenWidths=widths; moved=false; hoveredIndex=index
            }
            onPositionChanged: function(mouse) {
                if (pressed && key) resizeAt(mouse.x)
                else hoveredIndex=hitIndex(mouse.x)
            }
            onReleased: function(mouse) { resizeAt(mouse.x); key=""; hoveredIndex=hitIndex(mouse.x) }
            onCanceled: cancelResize()
            onExited: if (!pressed) hoveredIndex=-1
            Rectangle {
                readonly property var column: columnResizer.hoveredIndex>=0 ? view.columns[columnResizer.hoveredIndex] : null
                visible: !!column
                x: column ? column.offset+column.width-view.gridScroll-1 : 0
                width: 2; height: parent.height; color: appTheme.colors.link
            }
            ToolTip.visible: containsMouse && hoveredIndex>=0 && !pressed
            ToolTip.text: i18n.tr.resize_col_tooltip
            ToolTip.delay: 500
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
                              : modelData.number + "–" + view.dayRecords[Math.min(modelData.offset + 6, view.dayRecords.length - 1)].number + " (" + modelData.week + i18n.tr.week_unit + ")"
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
                            width: view.columns[0].width; height: parent.height; clip: true
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
                                readonly property bool custom: !!modelData.customId
                                readonly property bool metadata: ["status","priority"].indexOf(modelData.key)>=0 && gridRow.rowData.rowKind==="task" && !gridRow.rowData.summary
                                objectName: "column-cell-" + modelData.key + "-" + gridRow.index
                                x: modelData.offset; width: modelData.width; height: view.rowHeight; clip: true
                                opacity: gridRow.textOpacity
                                Rectangle { width: 1; height: parent.height; color: appTheme.colors.grid }
                                DateField {
                                    id: valueField
                                    readonly property string key: columnCell.modelData.key
                                    objectName: "task-" + key + "-" + (gridRow.rowData.taskId || "")
                                    calendarVisible: ["start","end","deadline"].indexOf(key)>=0 && gridRow.rowData.rowKind==="task"
                                    onCalendarRequested: { controller.select(gridRow.rowData.taskId); nativeDialogs.showTaskDate(gridRow.rowData.taskId,key) }
                                    function displayValue() {
                                        const value = gridRow.rowData[key]
                                        if (value === undefined) return ""
                                        if (key === "duration") return value + i18n.tr.hour_unit
                                        if (key === "progress") return Math.round(value) + "%"
                                        if (key === "status") return gridRow.rowData.statusText || ""
                                        if (key === "priority") return gridRow.rowData.priorityText || ""
                                        return String(value)
                                    }
                                    width: parent.width; height: parent.height
                                    text: displayValue()
                                    visible: !columnCell.metadata && !columnCell.custom && key!=="assignee"
                                    horizontalAlignment: ["cost","effort","duration","progress","startVariance","endVariance"].indexOf(key) >= 0 ? Text.AlignRight : Text.AlignLeft
                                    color: key === "deadline" && (gridRow.rowData.deadlineMissed || gridRow.rowData.deadlineOverdue) ? appTheme.colors.danger : gridRow.rowData.rowKind === "total" ? appTheme.colors.muted : appTheme.colors.text
                                    font.bold: gridRow.rowData.summary || false
                                    font.strikeout: gridRow.rowData.status === "closed"
                                    readOnly: gridRow.rowData.rowKind !== "task" ||
                                              ["baselineStart","baselineEnd","startVariance","endVariance"].indexOf(key)>=0 ||
                                              (gridRow.rowData.summary && key !== "start" && key !== "deadline") ||
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
                                Loader {
                                    anchors.fill: parent
                                    active: columnCell.modelData.key==="assignee" && gridRow.rowData.rowKind==="task" && !gridRow.rowData.summary
                                    sourceComponent: Component {
                                        AssigneeField {
                                            id: assigneeField
                                            objectName: "assignee-" + gridRow.rowData.taskId
                                            resourceIds: gridRow.rowData.resourceIds || []
                                            enabled: !controller.bulkMode
                                            onClicked: view.assigneePickerRequested(gridRow.rowData.taskId,assigneeField)
                                        }
                                    }
                                }
                                Loader {
                                    anchors.fill: parent
                                    active: columnCell.custom && (gridRow.rowData.rowKind==="task" || (gridRow.rowData.rowKind==="total" && columnCell.modelData.kind==="number"))
                                    sourceComponent: Component {
                                        CustomCell {
                                            definition: columnCell.modelData
                                            taskId: gridRow.rowData.taskId || ""
                                            value: (gridRow.rowData.customValues || ({}))[columnCell.modelData.customId] ?? null
                                            displayText: (gridRow.rowData.customTexts || ({}))[columnCell.modelData.customId] || ""
                                            summary: !!gridRow.rowData.summary || gridRow.rowData.rowKind==="total"
                                            editable: gridRow.rowData.rowKind==="task" && !controller.bulkMode && !(gridRow.rowData.summary && columnCell.modelData.kind==="number")
                                            onEditRequested: { controller.select(taskId); nativeDialogs.showFieldValue(taskId,definition.customId) }
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
                            hint: i18n.tr.task_actions
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
                        Item {
                            objectName: "add-cell-" + gridRow.index
                            visible: gridRow.rowData.rowKind === "add"
                            enabled: !controller.bulkMode
                            width: view.columns[0].width; height: parent.height; clip: true
                            Row {
                                objectName: "add-actions-" + gridRow.index
                                anchors.centerIn: parent; height: parent.height
                                ActionButton {
                                    objectName: "inline-add-task-" + gridRow.index
                                    text: i18n.tr.add_task_inline; palette.buttonText: appTheme.colors.link
                                    implicitWidth: contentItem.implicitWidth+8; leftPadding: 4; rightPadding: 4
                                    onClicked: controller.addTask(gridRow.rowData.parentId, "task")
                                }
                                Text { height: parent.height; text: " | "; color: appTheme.colors.muted; verticalAlignment: Text.AlignVCenter }
                                ActionButton {
                                    objectName: "inline-add-milestone-" + gridRow.index
                                    text: i18n.tr.add_milestone_inline; palette.buttonText: appTheme.colors.link
                                    implicitWidth: contentItem.implicitWidth+8; leftPadding: 4; rightPadding: 4
                                    onClicked: controller.addTask(gridRow.rowData.parentId, "milestone")
                                }
                            }
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
                            if (link.sourceFinish && !link.targetFinish && sx < tx) {
                                const middle=(sx+tx)/2
                                points=[[sx,sy],[middle,sy],[middle,ty],[tx,ty]]
                            } else {
                                const midY=sy+(ty>=sy?view.rowHeight/2:-view.rowHeight/2)
                                points=[[sx,sy],[stubS,sy],[stubS,midY],[stubT,midY],[stubT,ty],[tx,ty]]
                            }
                            const highlighted=hoveredLink===link.id || view.activeLinkId===link.id
                            const color=highlighted?appTheme.colors.link:link.critical?"#c93b3b":"#ffa726"
                            ctx.strokeStyle=color; ctx.lineWidth=highlighted?2.5:link.critical?2:1.4
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
                        Item {
                            id: baselineMark
                            objectName: "baseline-bar-" + (barRow.rowData.taskId || "")
                            visible: barRow.rowData.rowKind === "task" && !!barRow.rowData.hasBaseline
                            readonly property bool point: barRow.rowData.baselineKind === "milestone"
                            x: ((barRow.rowData.baselineStartDay || 0)+(point?0.5:0))*view.pixelsPerDay-(point?3:0)
                            y: barRow.index*view.rowHeight+26
                            width: point?6:Math.max(2,((barRow.rowData.baselineEndDay||0)-(barRow.rowData.baselineStartDay||0))*view.pixelsPerDay)
                            height: 4
                            Rectangle {
                                x: baselineMark.point?1:0; y: baselineMark.point?-1:1
                                width: baselineMark.point?4:parent.width; height: baselineMark.point?4:2
                                rotation: baselineMark.point?45:0; color: appTheme.colors.secondary
                            }
                            Rectangle { width:1; height:4; color:appTheme.colors.secondary; visible:barRow.rowData.baselineKind==="group" }
                            Rectangle { anchors.right:parent.right; width:1; height:4; color:appTheme.colors.secondary; visible:barRow.rowData.baselineKind==="group" }
                        }
                        Rectangle {
                            objectName: "deadline-marker-" + (barRow.rowData.taskId || "")
                            visible: barRow.rowData.rowKind === "task" && !!barRow.rowData.deadline
                            x: ((barRow.rowData.deadlineDay || 0)+1)*view.pixelsPerDay-1
                            y: barRow.index*view.rowHeight+3
                            width: 1; height: 24
                            color: barRow.rowData.deadlineMissed || barRow.rowData.deadlineOverdue ? appTheme.colors.danger : appTheme.colors.secondary
                            Rectangle { width: 6; height: 5; color: parent.color }
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
            if (pressed) view.gridWidth=view.boundedGridWidth(mapToItem(view,mouse.x,mouse.y).x)
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
        objectName: "tableScroll"
        x:0; y:parent.height-15; width:view.gridWidth; height:15
        orientation: Qt.Horizontal
        policy: view.gridContentWidth>view.gridWidth ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        size:Math.min(1,view.gridWidth/view.gridContentWidth)
        position:view.gridScroll/view.gridContentWidth
        onPositionChanged: if (pressed) { view.gridScroll=position*view.gridContentWidth; view.clampGridScroll() }
    }
    Text {
        objectName: "emptyStateHint"
        x: 0
        width: view.gridWidth
        anchors.verticalCenter: body.verticalCenter
        visible: controller.taskCount===0 || controller.rowCount<=1
        text: controller.taskCount===0 ? i18n.tr.empty_start_hint : i18n.tr.empty_filter_hint
        color: appTheme.colors.muted
        font.pixelSize: 15
        lineHeight: 1.5
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        leftPadding: 24
        rightPadding: 24
    }
}
