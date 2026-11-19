const byId = id => document.getElementById(id);
const pageSize = 25;
let rows = [], workbook = "", page = 0;

function render() {
  const body = byId("results").tBodies[0];
  body.replaceChildren();
  for (const row of rows.slice(page * pageSize, (page + 1) * pageSize)) {
    const tr = body.insertRow();
    const status = row.isActive == null ? "—" : row.isActive ? "Active" : "Inactive";
    for (const value of [row.fileName, row.uploadedByUserName, row.uploadedByUser,
      row.UploadTime || row.uploadedAt, row.clientID, row.accountID, status]) {
      tr.insertCell().textContent = value === "" || value == null ? "—" : value;
    }
  }
  byId("results").hidden = !rows.length;
  byId("pages").hidden = rows.length <= pageSize;
  byId("prev").disabled = page === 0;
  byId("next").disabled = (page + 1) * pageSize >= rows.length;
  byId("page").textContent = `Page ${page + 1} of ${Math.ceil(rows.length / pageSize)}`;
  byId("download").disabled = !workbook;
}
byId("prev").onclick = () => { page--; render(); };
byId("next").onclick = () => { page++; render(); };
byId("lookup").onsubmit = async event => {
  event.preventDefault();
  rows = []; workbook = ""; page = 0; render();
  const clientID = byId("client").value.trim(), accountID = byId("account").value.trim();
  const status = byId("status");
  if (!clientID && !accountID) {
    status.textContent = "Enter a client ID or account ID.";
    return;
  }
  if (!/^https:\/\//.test(API_ORIGIN)) {
    status.textContent = "Set the HTTPS API service URL in docs/config.js to connect this site.";
    return;
  }
  const form = byId("lookup");
  const controls = [...form.elements];
  controls.forEach(control => control.disabled = true);
  status.textContent = "Looking up uploaded documents…";
  try {
    const response = await fetch(API_ORIGIN.replace(/\/$/, "") + "/lookup", {
      method: "POST", cache: "no-store", redirect: "error",
      headers: {"Content-Type": "application/json", "Authorization": "Bearer " + byId("key").value.trim()},
      body: JSON.stringify({clientID, accountID})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Lookup failed (HTTP ${response.status}).`);
    rows = data.rows; workbook = data.workbook;
    status.textContent = `${rows.length} uploaded file(s) for client ${data.client}.`;
    render();
  } catch (error) {
    status.textContent = error instanceof TypeError
      ? "Could not connect. Check the API URL, service availability, and allowed Pages origin."
      : error.message;
  } finally {
    controls.forEach(control => control.disabled = false);
  }
};
byId("download").onclick = () => {
  const bytes = Uint8Array.from(atob(workbook), char => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], {type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}));
  const link = document.createElement("a");
  link.href = url; link.download = "Instafin_Documents.xlsx"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
};
