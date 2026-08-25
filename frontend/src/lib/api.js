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

export const listUsers = () => api.get("/admin/users").then((r) => r.data);
export const createUser = (payload) => api.post("/admin/users", payload).then((r) => r.data);
export const updateUser = (uid, payload) => api.put(`/admin/users/${uid}`, payload).then((r) => r.data);
export const resetUserPassword = (uid, new_password) =>
  api.post(`/admin/users/${uid}/reset-password`, { new_password }).then((r) => r.data);
export const deleteUser = (uid) => api.delete(`/admin/users/${uid}`).then((r) => r.data);

export const mediaUrl = (u) => (!u ? u : u.startsWith("http") ? u : `${BACKEND_URL}${u}`);
