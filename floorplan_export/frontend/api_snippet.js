// --- API helper the editor imports (paste into your frontend src/lib/api.js) ---
// `api` is your configured axios instance with baseURL = `${REACT_APP_BACKEND_URL}/api`.

export const saveFloorplanCad = (id, cadData) =>
  api.put(`/projects/${id}/floorplan`, { cadData }).then((r) => r.data);
