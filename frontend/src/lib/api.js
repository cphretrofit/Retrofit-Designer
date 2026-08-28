import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

axios.defaults.withCredentials = true;
export const api = axios.create({ baseURL: API, withCredentials: true });

export const getDashboard = () => api.get("/dashboard").then((r) => r.data);
export const getProjects = () => api.get("/projects").then((r) => r.data);
export const getProject = (id) => api.get(`/projects/${id}`).then((r) => r.data);
export const updateField = (id, payload) =>
  api.patch(`/projects/${id}/field`, payload).then((r) => r.data);

export const confirmItem = (id, index, payload) =>
  api.patch(`/projects/${id}/items/${index}/confirm`, payload).then((r) => r.data);

export const changePassword = (payload) =>
  api.post("/auth/change-password", payload).then((r) => r.data);

export const confirmAllItems = (id) =>
  api.post(`/projects/${id}/items/confirm-all`, { confirmed: true }).then((r) => r.data);

export const updatePhotos = (id, photos) =>
  api.put(`/projects/${id}/photos`, { photos }).then((r) => r.data);

export const addDefect = (id, payload) => api.post(`/projects/${id}/defects`, payload).then((r) => r.data);
export const updateDefect = (id, did, payload) => api.put(`/projects/${id}/defects/${did}`, payload).then((r) => r.data);
export const deleteDefect = (id, did) => api.delete(`/projects/${id}/defects/${did}`).then((r) => r.data);
export const uploadDefectPhoto = (id, did, file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post(`/projects/${id}/defects/${did}/photo`, fd).then((r) => r.data);
};

export const heritageLookup = (id) => api.post(`/projects/${id}/heritage/lookup`).then((r) => r.data);

export const detectSiteConditions = (id) => api.post(`/projects/${id}/site-conditions/detect`).then((r) => r.data);
export const saveSiteConditions = (id, siteConditions) =>
  api.put(`/projects/${id}/site-conditions`, { siteConditions }).then((r) => r.data);
export const parseDatasheets = (id) => api.post(`/projects/${id}/datasheets/parse`).then((r) => r.data);

export const getClients = (includeArchived = false) => api.get(`/clients?include_archived=${includeArchived}`).then((r) => r.data);
export const createClient = (name) => api.post(`/clients`, { name }).then((r) => r.data);
export const updateClient = (id, patch) => api.patch(`/clients/${id}`, patch).then((r) => r.data);
export const getClient = (id) => api.get(`/clients/${id}`).then((r) => r.data);
export const uploadClientDatasheets = (id, files) => {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return api.post(`/clients/${id}/datasheets`, fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};
export const deleteClientDatasheet = (id, docId) => api.delete(`/clients/${id}/datasheets/${docId}`).then((r) => r.data);
export const applyClientLibrary = (id) => api.post(`/projects/${id}/apply-client-library`).then((r) => r.data);

export const addSection = (id, s) => api.post(`/projects/${id}/sections`, s).then((r) => r.data);
export const updateSection = (id, sid, s) => api.put(`/projects/${id}/sections/${sid}`, s).then((r) => r.data);
export const deleteSection = (id, sid) => api.delete(`/projects/${id}/sections/${sid}`).then((r) => r.data);

export const updateVentilation = (id, ventilation) => api.put(`/projects/${id}/ventilation`, { ventilation }).then((r) => r.data);
export const uploadFloorPlan = (id, file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post(`/projects/${id}/floorplan`, fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};
export const updateFloorPlan = (id, payload) => api.put(`/projects/${id}/floorplan`, payload).then((r) => r.data);

export const listUsers = () => api.get("/admin/users").then((r) => r.data);
export const createUser = (payload) => api.post("/admin/users", payload).then((r) => r.data);
export const updateUser = (uid, payload) => api.put(`/admin/users/${uid}`, payload).then((r) => r.data);
export const resetUserPassword = (uid, new_password) =>
  api.post(`/admin/users/${uid}/reset-password`, { new_password }).then((r) => r.data);
export const deleteUser = (uid) => api.delete(`/admin/users/${uid}`).then((r) => r.data);

export const mediaUrl = (u) => (!u ? u : u.startsWith("http") ? u : `${BACKEND_URL}${u}`);
