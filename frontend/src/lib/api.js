import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API });

export const api = {
  getSystem: () => http.get("/system").then((r) => r.data),
  updateSystem: (data) => http.put("/system", data).then((r) => r.data),
  masterPower: (on) => http.post("/system/master-power", null, { params: { on } }).then((r) => r.data),
  runDiagnostic: () => http.post("/system/diagnostic").then((r) => r.data),
  getZones: () => http.get("/zones").then((r) => r.data),
  updateZone: (id, data) => http.put(`/zones/${id}`, data).then((r) => r.data),
  getDevices: () => http.get("/devices").then((r) => r.data),
  syncDevices: () => http.post("/devices/sync").then((r) => r.data),
  tick: () => http.post("/simulate/tick").then((r) => r.data),
  getSchedule: (zoneId) =>
    http.get("/schedule", { params: zoneId ? { zone_id: zoneId } : {} }).then((r) => r.data),
  createSlot: (data) => http.post("/schedule", data).then((r) => r.data),
  updateSlot: (id, data) => http.put(`/schedule/${id}`, data).then((r) => r.data),
  deleteSlot: (id) => http.delete(`/schedule/${id}`).then((r) => r.data),
};

export default api;
