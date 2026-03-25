// main.js — full helper functions (from uploads/script.js)
// Attach small helper functions to `window` so they can be called from inline
// handlers in HTML (keeps compatibility with your existing pages).

(function (){
  'use strict';

  // Toggle contact info box visibility (used on index.html)
  window.toggleContactInfo = function() {
    const contactBox = document.getElementById('contact-info-box');
    if (contactBox) contactBox.classList.toggle('visible');
  };

  // Fetch reports from backend; returns an array (empty on error)
  window.fetchReports = async function(){
    try {
      const res = await fetch('/api/reports');
      if (!res.ok) throw new Error(`Failed to load reports: ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error('fetchReports error', e);
      return [];
    }
  };

  // Fetch dashboard stats; returns object or null on error
  window.fetchStats = async function(){
    try {
      const res = await fetch('/api/data');
      if (!res.ok) throw new Error(`Failed to load stats: ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error('fetchStats error', e);
      return null;
    }
  };

  // Create CSV from reports and trigger download
  window.downloadReportsCsv = async function(){
    const reports = await window.fetchReports();
    if (!reports || !reports.length){
      alert('No reports to download');
      return;
    }

    const header = ['id','type','weight','location','lat','lon','timestamp'];
    const rows = reports.map(r => header.map(h => {
      const v = r[h] ?? '';
      return `"${String(v).replace(/"/g,'""')}"`;
    }).join(','));

    const csv = [header.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `waste_reports_${(new Date()).toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // Populate dashboard stats and render chart (if Chart.js is available)
  window.loadStatsAndChart = async function(){
    const stats = await window.fetchStats();
    if (!stats) return;

    const statsGrid = document.getElementById('statsGrid');
    if (statsGrid){
      const totalWaste = stats.total_waste ?? stats.total ?? 0;
      const activeZones = stats.active_zones ?? stats.active_trucks ?? 0;
      const recycled = stats.recycled ?? 0;
      const countReports = stats.count_reports ?? stats.reports_count ?? (stats.reports ? stats.reports.length : 0);

      statsGrid.innerHTML = `
        <div class="stat"><h3>Total Waste (kg)</h3><p style="font-size:1.4rem">${totalWaste}</p></div>
        <div class="stat"><h3>Active Zones</h3><p style="font-size:1.4rem">${activeZones}</p></div>
        <div class="stat"><h3>Recycled (est)</h3><p style="font-size:1.4rem">${recycled}</p></div>
        <div class="stat"><h3>Reports</h3><p style="font-size:1.4rem">${countReports}</p></div>
      `;
    }

    const chartEl = document.getElementById('typeChart');
    if (chartEl && typeof Chart !== 'undefined'){
      const byType = stats.by_type || stats.byType || {};
      const labels = Object.keys(byType);
      const data = Object.values(byType);

      if (window._typeChartInstance && typeof window._typeChartInstance.destroy === 'function'){
        try { window._typeChartInstance.destroy(); } catch(e){ console.warn('error destroying chart', e); }
        window._typeChartInstance = null;
      }

      window._typeChartInstance = new Chart(chartEl, {
        type: 'doughnut',
        data: { labels, datasets: [{ data, backgroundColor: ['#74c69d','#95d5b2','#52b788','#2d6a4f','#40916c','#2f855a'] }] },
        options: { plugins:{legend:{position:'bottom'}}, responsive:true }
      });
    }

    const dl = document.getElementById('downloadCsvBtn'); if (dl) dl.onclick = window.downloadReportsCsv;
    const ref = document.getElementById('refreshBtn'); if (ref) ref.onclick = () => window.loadStatsAndChart();
  };

  // initTrackMap code (same as before)
  window.initTrackMap = function(options){
    options = options || {};
    const mapId = options.mapId || 'map';
    const center = options.center || [-33.8688, 151.2093];
    const zoom = options.zoom || 11;
    const refreshMs = typeof options.refreshMs === 'number' ? options.refreshMs : 15000;
    const imageBase = options.imageBase || '';

    function escapeHtml(s){ if (s === null || s === undefined) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

    if (window._trackMap && typeof window._trackMap.remove === 'function'){ try { window._trackMap.remove(); } catch(e){ console.warn('remove previous map error', e); } window._trackMap = null; }

    try {
      const map = L.map(mapId).setView(center, zoom);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors' }).addTo(map);

      window._trackMap = map; window._trackMapRef = map;
      window._trackMarkersGroup = L.layerGroup().addTo(map);

      async function refreshMarkers(){
        try {
          const reports = await window.fetchReports();
          if (window._trackMarkersGroup && typeof window._trackMarkersGroup.clearLayers === 'function') window._trackMarkersGroup.clearLayers();

          (reports || []).forEach(r => {
            const lat = parseFloat(r.lat); const lon = parseFloat(r.lon); if (!isFinite(lat) || !isFinite(lon)) return;
            const marker = L.marker([lat, lon]); let popup = `<b>${escapeHtml(r.type||'Unknown')} Waste</b><br>`;
            if (r.weight) popup += `${escapeHtml(String(r.weight))} kg<br>`; if (r.location) popup += `📍 ${escapeHtml(r.location)}<br>`;
            const imageName = r.photo || r.image; if (imageName){ const safeImagePath = (imageBase ? imageBase.replace(/\/$/, '') + '/' : '') + encodeURIComponent(imageName); popup += `<img src="${safeImagePath}" width="200" style="margin-top:5px;border-radius:5px;">`; }
            marker.bindPopup(popup); window._trackMarkersGroup.addLayer(marker);
          });

          try { const layers = window._trackMarkersGroup.getLayers(); if (layers && layers.length>0){ const bounds = window._trackMarkersGroup.getBounds(); if (bounds && (typeof bounds.isValid==='function' ? bounds.isValid() : true)){ map.fitBounds(bounds, { padding: [50,50] }); } } } catch(e){}
        } catch(e){ console.error('refreshMarkers error', e); }
      }

      refreshMarkers();
      if (window._trackMapInterval) clearInterval(window._trackMapInterval); window._trackMapInterval = setInterval(refreshMarkers, refreshMs);

      return { stop: function(){ if (window._trackMapInterval) clearInterval(window._trackMapInterval); }, refresh: refreshMarkers };
    } catch(e){ console.error('initTrackMap error', e); return null; }
  };

  // Helper: build image URL for a saved photo filename
  window.getReportImageUrl = function(filename){
    if (!filename) return '';
    return '/static/uploads/' + encodeURIComponent(filename);
  };

  // Render a list of reports into a container (id). Each item shows thumbnail and a Details button.
  window.renderReportsList = async function(containerId){
    const container = document.getElementById(containerId);
    if (!container) return;
    const reports = await window.fetchReports();
    if (!reports || reports.length === 0){
      container.innerHTML = '<em>No reports yet.</em>';
      return;
    }

    const items = reports.map((r, i) => {
      const img = r.photo ? `<img src="${window.getReportImageUrl(r.photo)}" width="120" style="border-radius:6px; margin-right:12px;">` : '';
      const coords = (r.lat && r.lon) ? `${r.lat}, ${r.lon}` : '—';
      return `
        <div class="report-item" style="display:flex;align-items:center;gap:12px;padding:12px;border-bottom:1px solid #eee;">
          ${img}
          <div style="flex:1">
            <div style="font-weight:700">${(r.type||'Unknown')} — ${escapeHtml(r.location||'')}</div>
            <div style="color:#555">${escapeHtml(String(r.weight||''))} kg • ${coords}</div>
          </div>
          <div>
            <button class="btn" onclick='(function(){ window.showReportModal(${JSON.stringify(r)}) })()'>Details</button>
          </div>
        </div>`;
    }).join('\n');

    container.innerHTML = items;
  };

  // Show a modal with report details. Uses the existing .modal styles.
  window.showReportModal = function(report){
    // remove existing if present
    let existing = document.getElementById('reportDetailModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'reportDetailModal';
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
      <div class="modal-content">
        <span class="close" id="_r_close">&times;</span>
        <h3>Report Details</h3>
        <p><strong>Type:</strong> ${escapeHtml(report.type||'')}</p>
        <p><strong>Location:</strong> ${escapeHtml(report.location||'')}</p>
        <p><strong>Weight:</strong> ${escapeHtml(String(report.weight||''))} kg</p>
        <p><strong>Coords:</strong> ${(report.lat && report.lon) ? escapeHtml(report.lat + ', ' + report.lon) : '—'}</p>
        ${report.photo ? `<p><img src="${window.getReportImageUrl(report.photo)}" style="width:100%;max-width:400px;border-radius:8px;margin-top:8px;"></p>` : ''}
      </div>`;

    document.body.appendChild(modal);
    document.getElementById('_r_close').onclick = function(){ modal.remove(); };
    modal.onclick = function(e){ if (e.target === modal) modal.remove(); };
  };

})();
