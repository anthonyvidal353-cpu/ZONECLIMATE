import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API, withCredentials: true });

export function setToken(token) {
  if (token) {
    localStorage.setItem("cz_token", token);
    http.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    localStorage.removeItem("cz_token");
    delete http.defaults.headers.common["Authorization"];
  }
}

const saved = localStorage.getItem("cz_token");
if (saved) http.defaults.headers.common["Authorization"] = `Bearer ${saved}`;

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Une erreur est survenue. Réessayez.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const api = {
  // auth
  register: (data) => http.post("/auth/register", data).then((r) => r.data),
  login: (data) => http.post("/auth/login", data).then((r) => r.data),
  logout: () => http.post("/auth/logout").then((r) => r.data),
  me: () => http.get("/auth/me").then((r) => r.data),
  // users
  listUsers: () => http.get("/users").then((r) => r.data),
  updateUserRole: (id, role) => http.put(`/users/${id}`, { role }).then((r) => r.data),
  deleteUser: (id) => http.delete(`/users/${id}`).then((r) => r.data),
  // sauvegarde (admin)
  downloadBackup: () => http.get("/admin/backup").then((r) => r.data),
  saveBackupNow: () => http.post("/admin/backup/save").then((r) => r.data),
  restoreBackup: (data) => http.post("/admin/restore", data).then((r) => r.data),
  // Projets Tuya (admin)
  tuyaRegions: () => http.get("/admin/tuya/regions").then((r) => r.data),
  listTuyaProjects: () => http.get("/admin/tuya/projects").then((r) => r.data),
  createTuyaProject: (data) => http.post("/admin/tuya/projects", data).then((r) => r.data),
  updateTuyaProject: (id, data) => http.put(`/admin/tuya/projects/${id}`, data).then((r) => r.data),
  deleteTuyaProject: (id) => http.delete(`/admin/tuya/projects/${id}`).then((r) => r.data),
  activateTuyaProject: (id) => http.post(`/admin/tuya/projects/${id}/activate`).then((r) => r.data),
  testTuyaProject: (id) => http.post(`/admin/tuya/projects/${id}/test`).then((r) => r.data),
  // Catalogue QR (admin) + association par QR
  catalogDiscover: () => http.post("/admin/catalog/discover").then((r) => r.data),
  listCatalog: () => http.get("/admin/catalog").then((r) => r.data),
  associateQR: (iid, data) => http.post(`/installations/${iid}/associate-qr`, data).then((r) => r.data),
  // installations
  listInstallations: () => http.get("/installations").then((r) => r.data),
  createInstallation: (payload) => http.post("/installations", payload).then((r) => r.data),
  getInstallation: (id) => http.get(`/installations/${id}`).then((r) => r.data),
  updateInstallation: (id, data) => http.put(`/installations/${id}`, data).then((r) => r.data),
  deleteInstallation: (id) => http.delete(`/installations/${id}`).then((r) => r.data),
  // invitations / members
  invite: (id, role, email) => http.post(`/installations/${id}/invite`, { role, email }).then((r) => r.data),
  listInvites: (id) => http.get(`/installations/${id}/invitations`).then((r) => r.data),
  acceptInvite: (code) => http.post("/invitations/accept", { code }).then((r) => r.data),
  members: (id) => http.get(`/installations/${id}/members`).then((r) => r.data),
  // climate (installation scoped)
  getSystem: (iid) => http.get(`/installations/${iid}/system`).then((r) => r.data),
  updateSystem: (iid, data) => http.put(`/installations/${iid}/system`, data).then((r) => r.data),
  masterPower: (iid, on) => http.post(`/installations/${iid}/system/master-power`, null, { params: { on } }).then((r) => r.data),
  runDiagnostic: (iid) => http.post(`/installations/${iid}/system/diagnostic`).then((r) => r.data),
  getZones: (iid) => http.get(`/installations/${iid}/zones`).then((r) => r.data),
  updateZone: (iid, id, data) => http.put(`/installations/${iid}/zones/${id}`, data).then((r) => r.data),
  setMaster: (iid, id) => http.post(`/installations/${iid}/zones/${id}/set-master`).then((r) => r.data),
  getDevices: (iid) => http.get(`/installations/${iid}/devices`).then((r) => r.data),
  syncDevices: (iid) => http.post(`/installations/${iid}/devices/sync`).then((r) => r.data),
  discover: (iid, { count = 1, category = "thermostat", source = "sim" } = {}) =>
    http.post(`/installations/${iid}/discover`, null, { params: { count, category, source } }).then((r) => r.data),
  listPairing: (iid) => http.get(`/installations/${iid}/pairing`).then((r) => r.data),
  associatePairing: (iid, pid, data) => http.post(`/installations/${iid}/pairing/${pid}/associate`, data).then((r) => r.data),
  ignorePairing: (iid, pid) => http.delete(`/installations/${iid}/pairing/${pid}`).then((r) => r.data),
  tick: (iid) => http.post(`/installations/${iid}/simulate/tick`).then((r) => r.data),
  getHistory: (iid, hours = 24) => http.get(`/installations/${iid}/history`, { params: { hours } }).then((r) => r.data),
  getSchedule: (iid, zoneId) => http.get(`/installations/${iid}/schedule`, { params: zoneId ? { zone_id: zoneId } : {} }).then((r) => r.data),
  createSlot: (iid, data) => http.post(`/installations/${iid}/schedule`, data).then((r) => r.data),
  deleteSlot: (iid, id) => http.delete(`/installations/${iid}/schedule/${id}`).then((r) => r.data),
};

export default api;
