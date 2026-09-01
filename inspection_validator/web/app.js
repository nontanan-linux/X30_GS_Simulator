// Robotics CAT Inspection Result Validator App Logic
document.addEventListener('DOMContentLoaded', () => {
    
    // Application State
    const state = {
        missions: [],
        templates: [],
        selectedMission: null,
        selectedTemplate: null,
        importedData: null,
        results: [],
        filteredResults: [],
        validationReport: null,
        activeFilters: {
            search: '',
            level: 'all',
            type: 'all'
        },
        activeIssueFilter: 'all'
    };

    // DOM Elements
    const elements = {
        // Nav tabs
        navTabs: document.querySelectorAll('.nav-tab'),
        tabContents: document.querySelectorAll('.tab-content'),
        
        // Header status
        currentMissionText: document.getElementById('currentMissionText'),
        currentTemplateText: document.getElementById('currentTemplateText'),
        
        // Process 1: Import
        selectMission: document.getElementById('selectMission'),
        selectTemplate: document.getElementById('selectTemplate'),
        badgeMissionCount: document.getElementById('badgeMissionCount'),
        badgeTemplateCount: document.getElementById('badgeTemplateCount'),
        
        // Meta boxes
        mMetaCsv: document.getElementById('mMetaCsv'),
        mMetaMedia: document.getElementById('mMetaMedia'),
        mMetaImages: document.getElementById('mMetaImages'),
        mMetaVideos: document.getElementById('mMetaVideos'),
        mMetaAudio: document.getElementById('mMetaAudio'),
        
        tMetaFile: document.getElementById('tMetaFile'),
        tMetaWaypoints: document.getElementById('tMetaWaypoints'),
        tMetaInspections: document.getElementById('tMetaInspections'),
        tMetaVia: document.getElementById('tMetaVia'),
        tMetaSize: document.getElementById('tMetaSize'),
        
        btnImportSubmit: document.getElementById('btnImportSubmit'),
        importedSummaryCard: document.getElementById('importedSummaryCard'),
        statCsvRows: document.getElementById('statCsvRows'),
        statTemplatePoints: document.getElementById('statTemplatePoints'),
        statTotalMedia: document.getElementById('statTotalMedia'),
        btnGoResults: document.getElementById('btnGoResults'),
        
        // Process 2: Results Table & Summary Report
        inputResultSearch: document.getElementById('inputResultSearch'),
        levelFilterBtns: document.querySelectorAll('[data-filter-level]'),
        typeFilterBtns: document.querySelectorAll('[data-filter-type]'),
        lblVisibleCount: document.getElementById('lblVisibleCount'),
        lblTotalCount: document.getElementById('lblTotalCount'),
        tbodyResults: document.getElementById('tbodyResults'),
        kpiTotalPoints: document.getElementById('kpiTotalPoints'),
        kpiTotalPass: document.getElementById('kpiTotalPass'),
        kpiNotifications: document.getElementById('kpiNotifications'),
        kpiMissingData: document.getElementById('kpiMissingData'),
        tbodySummaryBreakdown: document.getElementById('tbodySummaryBreakdown'),
        tfootSummaryBreakdown: document.getElementById('tfootSummaryBreakdown'),
        
        // Process 3: Validate
        btnRunValidation: document.getElementById('btnRunValidation'),
        validationEmptyState: document.getElementById('validationEmptyState'),
        validationResultArea: document.getElementById('validationResultArea'),
        
        healthBanner: document.getElementById('healthBanner'),
        healthBadge: document.getElementById('healthBadge'),
        healthTitle: document.getElementById('healthTitle'),
        healthSubtitle: document.getElementById('healthSubtitle'),
        lblCoveragePct: document.getElementById('lblCoveragePct'),
        
        mValTemplateTotal: document.getElementById('mValTemplateTotal'),
        mSubMatched: document.getElementById('mSubMatched'),
        mValMissing: document.getElementById('mValMissing'),
        mValMediaOk: document.getElementById('mValMediaOk'),
        mSubMediaErrors: document.getElementById('mSubMediaErrors'),
        mValTotalIssues: document.getElementById('mValTotalIssues'),
        mSubIssuesBreakdown: document.getElementById('mSubIssuesBreakdown'),
        
        subTabs: document.querySelectorAll('.sub-tab'),
        subtabContents: document.querySelectorAll('.subtab-content'),
        
        cntIssues: document.getElementById('cntIssues'),
        cntOrphaned: document.getElementById('cntOrphaned'),
        issueFilterBtns: document.querySelectorAll('[data-filter-issue]'),
        issuesList: document.getElementById('issuesList'),
        
        cntMissingPoints: document.getElementById('cntMissingPoints'),
        cntExtraPoints: document.getElementById('cntExtraPoints'),
        listMissingPoints: document.getElementById('listMissingPoints'),
        listExtraPoints: document.getElementById('listExtraPoints'),
        listOrphanedFiles: document.getElementById('listOrphanedFiles'),
        
        // Modal
        detailModal: document.getElementById('detailModal'),
        btnModalClose: document.getElementById('btnModalClose'),
        modalPointTitle: document.getElementById('modalPointTitle'),
        modalLevelBadge: document.getElementById('modalLevelBadge'),
        mCellAction: document.getElementById('mCellAction'),
        mCellIndex: document.getElementById('mCellIndex'),
        mCellTimestamp: document.getElementById('mCellTimestamp'),
        mCellLevel: document.getElementById('mCellLevel'),
        mCodeResult: document.getElementById('mCodeResult'),
        modalMediaTabs: document.getElementById('modalMediaTabs'),
        modalMediaContainer: document.getElementById('modalMediaContainer')
    };

    // --- Tab Navigation Setup ---
    function switchTab(tabId) {
        elements.navTabs.forEach(tab => {
            if (tab.dataset.tab === tabId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        elements.tabContents.forEach(content => {
            if (content.id === tabId) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });

        if (tabId === 'tab-validate') {
            updateConfusionMatrixFromState();
        }
    }

    elements.navTabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    elements.btnGoResults.addEventListener('click', () => switchTab('tab-results'));

    // --- KPI Box Click Filters ---
    document.querySelectorAll('.clickable-kpi').forEach(box => {
        box.addEventListener('click', () => {
            const levelFilter = box.dataset.filterLevel || 'all';

            state.activeFilters.level = levelFilter;

            elements.levelFilterBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.filterLevel === levelFilter);
            });

            applyFilters();

            const tableCard = document.querySelector('.table-card');
            if (tableCard) {
                tableCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // --- Subtab Navigation Setup in Validate ---
    elements.subTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            elements.subTabs.forEach(t => t.classList.remove('active'));
            elements.subtabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.subtab).classList.add('active');
        });
    });

    // --- Fetch Initial Data from Python Server ---
    async function loadMissionsAndTemplates() {
        try {
            const [resM, resT] = await Promise.all([
                fetch('/api/missions').then(r => r.json()),
                fetch('/api/templates').then(r => r.json())
            ]);

            state.missions = resM.missions || [];
            state.templates = resT.templates || [];

            renderMissionDropdown();
            renderTemplateDropdown();
        } catch (err) {
            console.error("Failed to load initial metadata:", err);
        }
    }

    function renderMissionDropdown() {
        elements.selectMission.innerHTML = '<option value="">-- Choose Mission Folder --</option>';
        state.missions.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.folder_name;
            opt.textContent = `${m.folder_name} (${m.media_count} media files)`;
            elements.selectMission.appendChild(opt);
        });
        elements.badgeMissionCount.textContent = `${state.missions.length} Missions Found`;
    }

    function renderTemplateDropdown() {
        elements.selectTemplate.innerHTML = '<option value="">-- Choose Template JSON --</option>';
        state.templates.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.rel_path;
            opt.textContent = `${t.filename} (${t.inspection_points_count} inspections / ${t.total_waypoints} total pts)`;
            elements.selectTemplate.appendChild(opt);
        });
        elements.badgeTemplateCount.textContent = `${state.templates.length} Templates Found`;
    }

    // --- Process 1 Event Handlers ---
    elements.selectMission.addEventListener('change', (e) => {
        const folderName = e.target.value;
        const m = state.missions.find(x => x.folder_name === folderName);
        if (m) {
            state.selectedMission = m;
            elements.mMetaCsv.textContent = m.csv_file || 'None';
            elements.mMetaMedia.textContent = m.media_count;
            elements.mMetaImages.textContent = m.images_count;
            elements.mMetaVideos.textContent = m.videos_count;
            elements.mMetaAudio.textContent = m.audio_count;
        } else {
            state.selectedMission = null;
            elements.mMetaCsv.textContent = '-';
            elements.mMetaMedia.textContent = '-';
            elements.mMetaImages.textContent = '-';
            elements.mMetaVideos.textContent = '-';
            elements.mMetaAudio.textContent = '-';
        }
    });

    elements.selectTemplate.addEventListener('change', (e) => {
        const relPath = e.target.value;
        const t = state.templates.find(x => x.rel_path === relPath);
        if (t) {
            state.selectedTemplate = t;
            elements.tMetaFile.textContent = t.filename;
            elements.tMetaWaypoints.textContent = t.total_waypoints;
            elements.tMetaInspections.textContent = t.inspection_points_count;
            elements.tMetaVia.textContent = t.total_waypoints - t.inspection_points_count;
            elements.tMetaSize.textContent = (t.file_size / 1024).toFixed(1) + ' KB';
        } else {
            state.selectedTemplate = null;
            elements.tMetaFile.textContent = '-';
            elements.tMetaWaypoints.textContent = '-';
            elements.tMetaInspections.textContent = '-';
            elements.tMetaVia.textContent = '-';
            elements.tMetaSize.textContent = '-';
        }
    });

    elements.btnImportSubmit.addEventListener('click', async () => {
        if (!state.selectedMission || !state.selectedTemplate) {
            alert('Please select both a mission folder and an inspection template.');
            return;
        }

        try {
            elements.btnImportSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...';
            
            const res = await fetch('/api/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mission_folder: state.selectedMission.folder_name,
                    template_path: state.selectedTemplate.rel_path
                })
            });

            const data = await res.json();
            if (res.ok) {
                state.importedData = data;
                elements.currentMissionText.textContent = data.mission.folder_name;
                elements.currentTemplateText.textContent = data.template.filename;

                elements.statCsvRows.textContent = data.mission.record_count;
                elements.statTemplatePoints.textContent = data.template.inspection_count;
                elements.statTotalMedia.textContent = data.mission.physical_files_count;

                elements.importedSummaryCard.style.display = 'block';

                // Fetch results for Process 2
                await fetchResults();
            } else {
                alert('Import Error: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Network error while importing: ' + err.message);
        } finally {
            elements.btnImportSubmit.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Import & Load Mission Data';
        }
    });

    // --- Process 2: Fetch & Render Inspection Results ---
    async function fetchResults() {
        try {
            const res = await fetch('/api/results');
            const data = await res.json();
            if (res.ok) {
                state.results = data.results || [];
                applyFilters();
                if (data.summary_report) {
                    renderSummaryReport(data.summary_report);
                }
            }
        } catch (err) {
            console.error("Error fetching results:", err);
        }
    }

    function renderSummaryReport(rep) {
        if (!rep || !rep.kpi) return;

        // KPI Numbers
        elements.kpiTotalPoints.textContent = rep.kpi.total_points;
        elements.kpiTotalPass.textContent = rep.kpi.total_pass;
        elements.kpiNotifications.textContent = rep.kpi.notifications;
        elements.kpiMissingData.textContent = rep.kpi.missing_data;

        // Breakdown Table Rows
        const breakdown = rep.breakdown || [];
        if (breakdown.length === 0) {
            elements.tbodySummaryBreakdown.innerHTML = '<tr><td colspan="5" class="empty-state">No summary data available.</td></tr>';
            elements.tfootSummaryBreakdown.innerHTML = '';
            return;
        }

        let tbodyHtml = '';
        breakdown.forEach(row => {
            const rawType = row.inspection_type.replace(' Inspection', '').toLowerCase();
            tbodyHtml += `
                <tr>
                    <td><strong>${row.inspection_type}</strong></td>
                    <td style="text-align: center;" class="cell-clickable" data-type="${rawType}" data-level="pass" title="Filter by ${row.inspection_type} Pass">${row.pass_count}</td>
                    <td style="text-align: center;" class="cell-clickable" data-type="${rawType}" data-level="notification" title="Filter by ${row.inspection_type} Notifications">${row.notification}</td>
                    <td style="text-align: center;" class="cell-clickable" data-type="${rawType}" data-level="missing" title="Filter by ${row.inspection_type} Missing">${row.missing}</td>
                    <td style="text-align: center;" class="cell-clickable" data-type="${rawType}" data-level="all" title="Filter by ${row.inspection_type} All"><strong>${row.total}</strong></td>
                </tr>
            `;
        });
        elements.tbodySummaryBreakdown.innerHTML = tbodyHtml;

        // Totals Row
        const tot = rep.totals_row || {};
        elements.tfootSummaryBreakdown.innerHTML = `
            <tr>
                <td><strong>${tot.inspection_type || 'Total'}</strong></td>
                <td style="text-align: center;" class="cell-clickable" data-type="all" data-level="pass" title="Filter all Pass">${tot.pass_count || 0}</td>
                <td style="text-align: center;" class="cell-clickable" data-type="all" data-level="notification" title="Filter all Notifications">${tot.notification || 0}</td>
                <td style="text-align: center;" class="cell-clickable" data-type="all" data-level="missing" title="Filter all Missing">${tot.missing || 0}</td>
                <td style="text-align: center;" class="total-highlight-cell cell-clickable" data-type="all" data-level="all" title="Show all points">${tot.total || 0}</td>
            </tr>
        `;

        // Attach click listeners to breakdown cells
        document.querySelectorAll('.summary-report-card .cell-clickable').forEach(cell => {
            cell.addEventListener('click', () => {
                const type = cell.dataset.type || 'all';
                const level = cell.dataset.level || 'all';

                state.activeFilters.type = type;
                state.activeFilters.level = level;

                // Update filter buttons UI
                elements.levelFilterBtns.forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.filterLevel === level);
                });
                elements.typeFilterBtns.forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.filterType === type);
                });

                applyFilters();

                const tableCard = document.querySelector('.table-card');
                if (tableCard) {
                    tableCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        updateConfusionMatrixFromState();
    }

    function updateConfusionMatrixFromState() {
        if (!state.results || state.results.length === 0) return;
        let tp = 0, tn = 0, fp = 0, fn = 0;
        state.results.forEach(r => {
            const ev = (r.dev_eval || 'N/A').toUpperCase();
            if (ev === 'N/A' || ev === 'NONE' || ev === 'MISSING' || ev === 'NULL') {
                return; // Exclude points with missing data from Confusion Matrix
            }
            if (ev === 'TP') tp++;
            else if (ev === 'TN') tn++;
            else if (ev === 'FP') fp++;
            else if (ev === 'FN') fn++;
        });

        const total = tp + tn + fp + fn;
        const accuracy = total > 0 ? (((tp + tn) / total) * 100).toFixed(1) : '0.0';
        const precision = (tp + fp) > 0 ? ((tp / (tp + fp)) * 100).toFixed(1) : '0.0';
        const recall = (tp + fn) > 0 ? ((tp / (tp + fn)) * 100).toFixed(1) : '0.0';
        const f1 = (parseFloat(precision) + parseFloat(recall)) > 0 
            ? ((2 * parseFloat(precision) * parseFloat(recall)) / (parseFloat(precision) + parseFloat(recall))).toFixed(1) 
            : '0.0';

        document.querySelectorAll('.cmValAccuracy').forEach(el => el.textContent = `${accuracy}%`);
        document.querySelectorAll('.cmValTP').forEach(el => el.textContent = tp);
        document.querySelectorAll('.cmValTN').forEach(el => el.textContent = tn);
        document.querySelectorAll('.cmValFP').forEach(el => el.textContent = fp);
        document.querySelectorAll('.cmValFN').forEach(el => el.textContent = fn);

        document.querySelectorAll('.barAccuracy').forEach(el => el.style.width = `${accuracy}%`);
        document.querySelectorAll('.cmValPrecision').forEach(el => el.textContent = `${precision}%`);
        document.querySelectorAll('.cmValRecall').forEach(el => el.textContent = `${recall}%`);
        document.querySelectorAll('.cmValF1Score').forEach(el => el.textContent = `${f1}%`);

        document.querySelectorAll('.barPrecision').forEach(el => el.style.width = `${precision}%`);
        document.querySelectorAll('.barRecall').forEach(el => el.style.width = `${recall}%`);
        document.querySelectorAll('.barF1Score').forEach(el => el.style.width = `${f1}%`);

        // Update Equation Substitutions
        document.querySelectorAll('.eqAccSub').forEach(el => el.textContent = `${tp} + ${tn}`);
        document.querySelectorAll('.eqAccDenomSub').forEach(el => el.textContent = `${tp} + ${tn} + ${fp} + ${fn}`);

        document.querySelectorAll('.eqPrecSub').forEach(el => el.textContent = tp);
        document.querySelectorAll('.eqPrecDenomSub').forEach(el => el.textContent = `${tp} + ${fp}`);

        document.querySelectorAll('.eqRecSub').forEach(el => el.textContent = tp);
        document.querySelectorAll('.eqRecDenomSub').forEach(el => el.textContent = `${tp} + ${fn}`);

        document.querySelectorAll('.eqF1NumSub').forEach(el => el.textContent = `${precision}% × ${recall}%`);
        document.querySelectorAll('.eqF1DenomSub').forEach(el => el.textContent = `${precision}% + ${recall}%`);
    }

    function getInspectionType(actionName) {
        if (!actionName) return 'Other';
        const name = actionName.toLowerCase();
        if (name.includes('thermal')) return 'Thermal';
        if (name.includes('leakage')) return 'Leakage';
        if (name.includes('vibration')) return 'Vibration';
        if (name.includes('gauge')) return 'Gauge';
        if (name.includes('loto')) return 'LOTO';
        if (name.includes('asset')) return 'Asset';
        return 'Other';
    }

    function formatResultTags(resParsed) {
        if (!resParsed) return '<span class="text-muted">-</span>';
        if (typeof resParsed === 'object') {
            const entries = Object.entries(resParsed);
            if (entries.length === 0) return '<span class="text-muted">Empty</span>';
            return '<div class="result-tag-group">' + entries.map(([k, v]) => `
                <span class="result-tag"><span class="result-tag-key">${k}:</span><span class="result-tag-val">${v}</span></span>
            `).join('') + '</div>';
        }
        return `<span class="result-tag-val">${resParsed}</span>`;
    }

    function applyFilters() {
        const search = state.activeFilters.search.toLowerCase();
        const level = state.activeFilters.level;
        const type = state.activeFilters.type;

        state.filteredResults = state.results.filter(r => {
            const action = (r.action_name || '').toLowerCase();
            const lvl = (r.notification_level || '').toLowerCase();
            const resStr = JSON.stringify(r.result_parsed || '').toLowerCase();
            const insType = getInspectionType(r.action_name).toLowerCase();

            if (search && !action.includes(search) && !resStr.includes(search) && !lvl.includes(search)) {
                return false;
            }

            if (level !== 'all') {
                if (level === 'pass' && lvl !== 'pass') return false;
                if (level === 'notification' && (lvl === 'pass' || lvl === 'missing')) return false;
                if (level === 'missing' && lvl !== 'missing') return false;
                if (level === 'critical' && lvl !== 'critical') return false;
                if (level === 'warning' && lvl !== 'warning') return false;
            }

            if (type !== 'all' && insType !== type) {
                return false;
            }

            return true;
        });

        renderResultsTable();
    }

    function renderResultsTable() {
        elements.lblVisibleCount.textContent = state.filteredResults.length;
        elements.lblTotalCount.textContent = state.results.length;

        if (state.filteredResults.length === 0) {
            elements.tbodyResults.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">No matching inspection records found.</td>
                </tr>
            `;
            return;
        }

        let html = '';
        state.filteredResults.forEach((r, idx) => {
            const level = (r.notification_level || 'info').toLowerCase();
            let badgeClass = 'badge-info';
            if (level === 'pass') badgeClass = 'badge-success';
            if (level === 'critical') badgeClass = 'badge-danger';
            if (level === 'warning') badgeClass = 'badge-warning';

            const isMissing = !r.result_parsed || level === 'missing' || level === 'n/a' || level === 'none' || (r.dev_eval && r.dev_eval.toUpperCase() === 'N/A');
            const devEval = (r.dev_eval || (isMissing ? 'N/A' : 'TN')).toUpperCase();
            const selectClass = 'select-' + devEval.toLowerCase().replace('/', '-');

            const devSelectHtml = `
                <select class="dev-eval-select ${selectClass}" data-idx="${idx}">
                    <option value="TP" ${devEval === 'TP' ? 'selected' : ''}>TP</option>
                    <option value="TN" ${devEval === 'TN' ? 'selected' : ''}>TN</option>
                    <option value="FP" ${devEval === 'FP' ? 'selected' : ''}>FP</option>
                    <option value="FN" ${devEval === 'FN' ? 'selected' : ''}>FN</option>
                    <option value="N/A" ${devEval === 'N/A' ? 'selected' : ''}>N/A</option>
                </select>
            `;

            const mediaCount = Array.isArray(r.files_parsed) ? r.files_parsed.length : 0;
            const drawerId = `media-drawer-${idx}`;

            html += `
                <tr class="main-result-row" data-drawer="${drawerId}" data-idx="${idx}">
                    <td><strong>${idx + 1}</strong></td>
                    <td class="font-code">${r.timestamp || '-'}</td>
                    <td>
                        <strong>${r.action_name}</strong>
                        <span class="file-tag" style="margin-left: 8px; font-size: 11px;">
                            <i class="fa-solid fa-photo-film text-accent"></i> ${mediaCount}
                        </span>
                        <i class="fa-solid fa-chevron-down row-expand-icon"></i>
                    </td>
                    <td>${formatResultTags(r.result_parsed)}</td>
                    <td><span class="badge ${badgeClass}">${r.notification_level}</span></td>
                    <td style="text-align: center;">${devSelectHtml}</td>
                </tr>
                <tr class="inline-media-row" id="${drawerId}" style="display: none;">
                    <td colspan="6">
                        <div class="inline-media-container">
                            <div class="inline-media-header">
                                <span><i class="fa-solid fa-photo-film text-accent"></i> Inspection Media Evidence: <strong>${r.action_name}</strong> (${r.timestamp || ''})</span>
                                <button class="btn-view-detail" data-action="${r.action_name}">
                                    <i class="fa-solid fa-expand"></i> Raw JSON & Details
                                </button>
                            </div>
                            <div class="inline-media-grid" id="grid-${drawerId}">
                                <div class="text-muted">Loading media...</div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        });

        elements.tbodyResults.innerHTML = html;

        // Dev Eval Select Event Handlers
        elements.tbodyResults.querySelectorAll('.dev-eval-select').forEach(sel => {
            sel.addEventListener('click', (e) => {
                e.stopPropagation();
            });

            sel.addEventListener('change', (e) => {
                e.stopPropagation();
                const idx = parseInt(sel.dataset.idx, 10);
                const newVal = sel.value;
                if (state.filteredResults[idx]) {
                    state.filteredResults[idx].dev_eval = newVal;
                }
                sel.className = `dev-eval-select select-${newVal.toLowerCase().replace('/', '-')}`;
                updateConfusionMatrixFromState();
            });
        });

        // Attach click listeners to Main Rows
        elements.tbodyResults.querySelectorAll('.main-result-row').forEach(row => {
            row.addEventListener('click', () => {
                const drawerId = row.dataset.drawer;
                const idx = parseInt(row.dataset.idx, 10);
                const drawerRow = document.getElementById(drawerId);
                const record = state.filteredResults[idx];

                if (drawerRow.style.display === 'none' || !drawerRow.style.display) {
                    drawerRow.style.display = 'table-row';
                    row.classList.add('expanded');
                    
                    // Render media content inside drawer
                    const gridEl = document.getElementById(`grid-${drawerId}`);
                    renderInlineMediaCards(record, gridEl);
                } else {
                    drawerRow.style.display = 'none';
                    row.classList.remove('expanded');
                }
            });
        });

        // Attach click listeners to Raw JSON View buttons inside drawers
        elements.tbodyResults.querySelectorAll('.btn-view-detail').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent toggling row closed
                const action = btn.dataset.action;
                const record = state.results.find(x => x.action_name === action);
                if (record) openDetailModal(record);
            });
        });
    }

    function renderInlineMediaCards(r, container) {
        const files = r.files_parsed || [];
        if (!Array.isArray(files) || files.length === 0) {
            container.innerHTML = '<div class="text-muted" style="padding: 12px;"><i class="fa-solid fa-circle-info"></i> No media files attached to this inspection point.</div>';
            return;
        }

        const folderName = state.selectedMission ? state.selectedMission.folder_name : '';
        let html = '';

        files.forEach(f => {
            const fileUrl = typeof f === 'object' ? f.file_url : String(f);
            const fileName = fileUrl.split('/').pop();
            const mediaSrc = `/api/media?path=${encodeURIComponent(folderName + '/' + fileName)}`;
            const lower = fileName.toLowerCase();

            if (lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png')) {
                html += `
                    <div class="inline-media-card">
                        <div class="inline-media-title"><i class="fa-solid fa-image text-accent"></i> ${fileName}</div>
                        <a href="${mediaSrc}" target="_blank" title="Click to open full size">
                            <img src="${mediaSrc}" alt="${fileName}" loading="lazy">
                        </a>
                    </div>
                `;
            } else if (lower.endsWith('.mp4') || lower.endsWith('.avi')) {
                html += `
                    <div class="inline-media-card">
                        <div class="inline-media-title"><i class="fa-solid fa-video text-accent"></i> ${fileName}</div>
                        <video controls preload="metadata">
                            <source src="${mediaSrc}" type="video/mp4">
                            Browser video playback not supported.
                        </video>
                    </div>
                `;
            } else if (lower.endsWith('.wav')) {
                html += `
                    <div class="inline-media-card">
                        <div class="inline-media-title"><i class="fa-solid fa-volume-high text-accent"></i> ${fileName}</div>
                        <audio controls preload="metadata" style="margin-top: 16px;">
                            <source src="${mediaSrc}" type="audio/wav">
                            Browser audio playback not supported.
                        </audio>
                    </div>
                `;
            } else {
                html += `
                    <div class="inline-media-card">
                        <div class="inline-media-title"><i class="fa-solid fa-file text-muted"></i> ${fileName}</div>
                        <a href="${mediaSrc}" download class="btn btn-secondary" style="font-size:12px;">Download File</a>
                    </div>
                `;
            }
        });

        container.innerHTML = html;
    }

    // Filter Listeners
    elements.inputResultSearch.addEventListener('input', (e) => {
        state.activeFilters.search = e.target.value;
        applyFilters();
    });

    elements.levelFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.levelFilterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeFilters.level = btn.dataset.filterLevel;
            applyFilters();
        });
    });

    elements.typeFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.typeFilterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeFilters.type = btn.dataset.filterType;
            applyFilters();
        });
    });

    // --- Modal & Media Viewer Logic ---
    function openDetailModal(r) {
        elements.modalPointTitle.textContent = r.action_name;
        
        const level = (r.notification_level || 'info').toLowerCase();
        let badgeClass = 'badge-info';
        if (level === 'pass') badgeClass = 'badge-success';
        if (level === 'critical') badgeClass = 'badge-danger';
        if (level === 'warning') badgeClass = 'badge-warning';

        elements.modalLevelBadge.className = `badge ${badgeClass}`;
        elements.modalLevelBadge.textContent = r.notification_level;

        elements.mCellAction.textContent = r.action_name;
        elements.mCellIndex.textContent = r.inspection_index;
        elements.mCellTimestamp.textContent = r.timestamp || '-';
        elements.mCellLevel.textContent = r.notification_level;

        elements.mCodeResult.textContent = JSON.stringify(r.result_parsed, null, 2);

        // Render Media Files Tabs & Preview
        renderModalMedia(r);

        elements.detailModal.classList.add('active');
    }

    function renderModalMedia(r) {
        const files = r.files_parsed || [];
        elements.modalMediaTabs.innerHTML = '';
        elements.modalMediaContainer.innerHTML = '<div class="media-placeholder">Select a media file above to view preview.</div>';

        if (!Array.isArray(files) || files.length === 0) {
            elements.modalMediaContainer.innerHTML = '<div class="media-placeholder">No media files associated with this record.</div>';
            return;
        }

        files.forEach((f, idx) => {
            const fileUrl = typeof f === 'object' ? f.file_url : String(f);
            const fileName = fileUrl.split('/').pop();
            const btn = document.createElement('button');
            btn.className = `btn-media-tab ${idx === 0 ? 'active' : ''}`;
            
            let icon = 'fa-file';
            if (fileName.endsWith('.jpg') || fileName.endsWith('.png')) icon = 'fa-image';
            if (fileName.endsWith('.mp4') || fileName.endsWith('.avi')) icon = 'fa-video';
            if (fileName.endsWith('.wav')) icon = 'fa-volume-high';

            btn.innerHTML = `<i class="fa-solid ${icon}"></i> ${fileName}`;
            btn.addEventListener('click', () => {
                elements.modalMediaTabs.querySelectorAll('.btn-media-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                loadMediaPreview(fileName, state.selectedMission.folder_name);
            });
            elements.modalMediaTabs.appendChild(btn);
        });

        // Load first media by default
        const firstFile = typeof files[0] === 'object' ? files[0].file_url : String(files[0]);
        loadMediaPreview(firstFile.split('/').pop(), state.selectedMission.folder_name);
    }

    function loadMediaPreview(fileName, folderName) {
        const mediaUrl = `/api/media?path=${encodeURIComponent(folderName + '/' + fileName)}`;
        const lower = fileName.toLowerCase();

        if (lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png')) {
            elements.modalMediaContainer.innerHTML = `<img src="${mediaUrl}" alt="${fileName}" loading="lazy">`;
        } else if (lower.endsWith('.mp4') || lower.endsWith('.avi')) {
            elements.modalMediaContainer.innerHTML = `
                <video controls autoplay loop style="width:100%;">
                    <source src="${mediaUrl}" type="video/mp4">
                    Your browser does not support video playback.
                </video>
            `;
        } else if (lower.endsWith('.wav')) {
            elements.modalMediaContainer.innerHTML = `
                <div style="text-align:center; width:100%;">
                    <p style="margin-bottom:12px; color:var(--primary); font-family:var(--font-code);">${fileName}</p>
                    <audio controls autoplay style="width:90%;">
                        <source src="${mediaUrl}" type="audio/wav">
                        Your browser does not support audio playback.
                    </audio>
                </div>
            `;
        } else {
            elements.modalMediaContainer.innerHTML = `<div class="media-placeholder">Unsupported preview format for ${fileName}</div>`;
        }
    }

    elements.btnModalClose.addEventListener('click', () => {
        elements.detailModal.classList.remove('active');
        elements.modalMediaContainer.innerHTML = '';
    });

    elements.detailModal.addEventListener('click', (e) => {
        if (e.target === elements.detailModal) {
            elements.detailModal.classList.remove('active');
            elements.modalMediaContainer.innerHTML = '';
        }
    });


    // --- Process 3: Validate Logic ---
    elements.btnRunValidation.addEventListener('click', async () => {
        if (!state.importedData) {
            alert('Please import mission and template data first.');
            return;
        }

        try {
            elements.btnRunValidation.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validating...';

            const res = await fetch('/api/validate', { method: 'POST' });
            const report = await res.json();

            if (res.ok) {
                state.validationReport = report;
                renderValidationDashboard(report);
            } else {
                alert('Validation Error: ' + (report.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Network error running validation: ' + err.message);
        } finally {
            elements.btnRunValidation.innerHTML = '<i class="fa-solid fa-play"></i> Run Full Validation Audit';
        }
    });

    function renderValidationDashboard(report) {
        const sum = report.summary;
        
        if (elements.validationEmptyState) elements.validationEmptyState.style.display = 'none';
        if (elements.validationResultArea) elements.validationResultArea.style.display = 'block';

        // Audit Issues Counts (if elements exist)
        if (elements.cntIssues) elements.cntIssues.textContent = sum.issues_count;
        if (elements.cntOrphaned) elements.cntOrphaned.textContent = sum.orphaned_files_count;
        if (elements.cntMissingPoints) elements.cntMissingPoints.textContent = sum.missing_points_count;
        if (elements.cntExtraPoints) elements.cntExtraPoints.textContent = sum.extra_points_count;

        renderIssuesList();

        // Coverage lists
        renderCoverageLists(report);

        // Update Confusion Matrix Dashboard
        updateConfusionMatrixFromState();
    }

    function renderIssuesList() {
        if (!state.validationReport || !elements.issuesList) return;
        const issues = state.validationReport.issues || [];
        const filter = state.activeIssueFilter;

        const filtered = issues.filter(i => {
            if (filter === 'all') return true;
            return i.severity === filter;
        });

        if (filtered.length === 0) {
            elements.issuesList.innerHTML = '<div class="empty-state">No issues in this severity category.</div>';
            return;
        }

        let html = '';
        filtered.forEach(i => {
            let icon = 'fa-circle-info text-accent';
            if (i.severity === 'ERROR') icon = 'fa-circle-xmark text-danger';
            if (i.severity === 'WARNING') icon = 'fa-triangle-exclamation text-warning';

            html += `
                <div class="issue-item ${i.severity}">
                    <div class="issue-title">
                        <i class="fa-solid ${icon}"></i> [${i.severity}] ${i.title}
                    </div>
                    <div class="issue-msg">${i.message}</div>
                </div>
            `;
        });

        elements.issuesList.innerHTML = html;
    }

    elements.issueFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.issueFilterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeIssueFilter = btn.dataset.filterIssue;
            renderIssuesList();
        });
    });

    function renderCoverageLists(report) {
        if (!elements.listMissingPoints) return;
        const missing = report.coverage.missing_in_results || [];
        const extra = report.coverage.extra_in_results || [];
        const orphaned = report.orphaned_files || [];

        // Missing list
        if (missing.length === 0) {
            elements.listMissingPoints.innerHTML = '<li class="text-success"><i class="fa-solid fa-check"></i> None. All template points executed!</li>';
        } else {
            elements.listMissingPoints.innerHTML = missing.map(m => `
                <li class="text-danger">
                    <i class="fa-solid fa-xmark"></i> <strong>${m.node_info}</strong> (Template idx: ${m.template.template_index})
                </li>
            `).join('');
        }

        // Extra list
        if (extra.length === 0) {
            elements.listExtraPoints.innerHTML = '<li class="text-muted">None. No extra points recorded.</li>';
        } else {
            elements.listExtraPoints.innerHTML = extra.map(e => `
                <li class="text-warning">
                    <i class="fa-solid fa-triangle-exclamation"></i> <strong>${e.action_name}</strong> (Index: ${e.result.inspection_index})
                </li>
            `).join('');
        }

        // Orphaned files
        if (orphaned.length === 0) {
            elements.listOrphanedFiles.innerHTML = '<li class="empty-state">No orphaned files in mission directory.</li>';
        } else {
            elements.listOrphanedFiles.innerHTML = orphaned.map(f => `
                <li class="file-tag">${f}</li>
            `).join('');
        }
    }

    // Initialize
    loadMissionsAndTemplates();
});
