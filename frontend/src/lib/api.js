import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const getDashboard = () => api.get("/dashboard").then((r) => r.data);
export const getProjects = () => api.get("/projects").then((r) => r.data);
export const getProject = (id) => api.get(`/projects/${id}`).then((r) => r.data);
export const updateField = (id, payload) =>
  api.patch(`/projects/${id}/field`, payload).then((r) => r.data);

export const confirmItem = (id, index, payload) =>
  api.patch(`/projects/${id}/items/${index}/confirm`, payload).then((r) => r.data);

export const mediaUrl = (u) => (!u ? u : u.startsWith("http") ? u : `${BACKEND_URL}${u}`);
