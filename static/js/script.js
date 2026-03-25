// Main frontend helpers (copied from uploads/script.js)
(function(){'use strict';
  window.toggleContactInfo = function(){ const contactBox = document.getElementById('contact-info-box'); if(contactBox) contactBox.classList.toggle('visible'); };
  window.fetchReports = async function(){ try { const res = await fetch('/api/reports'); if(!res.ok) throw new Error('Failed to load reports'); return await res.json(); } catch(e){ console.error('fetchReports error', e); return []; } };
  // small helper to post report via JSON (used by standalone pages)
  window.postJsonReport = async function(obj){ const res = await fetch('/api/report', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(obj) }); return res; };
})();
