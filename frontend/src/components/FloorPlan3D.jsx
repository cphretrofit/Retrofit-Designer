import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const WALL_H = 2.6;
const FLOOR_GAP = 0.9;
const FLOOR_NAMES = ["Ground Floor", "First Floor", "Second Floor", "Third Floor"];

const ROOM_TONE = (name) => {
  const n = (name || "").toLowerCase();
  if (/(bath|shower|wc|toilet|ensuite|en-suite|cloak)/.test(n)) return 0x8fb6c9;
  if (/(kitchen|utility)/.test(n)) return 0xc9b892;
  if (/(bed)/.test(n)) return 0xb7c4a8;
  if (/(hall|landing|stair)/.test(n)) return 0xcfcfcf;
  return 0xcdd6e0;
};

const ROOF_HEX = (covering) => {
  const c = (covering || "").toLowerCase();
  if (c.includes("slate")) return 0x4e5c6b;
  if (c.includes("metal") || c.includes("steel") || c.includes("zinc")) return 0x8a949e;
  if (c.includes("felt") || c.includes("bitumen")) return 0x40403f;
  return 0xb4573b; // clay / concrete tile (default terracotta)
};


function labelSprite(text) {
  const c = document.createElement("canvas");
  const dpr = 2;
  c.width = 256 * dpr; c.height = 64 * dpr;
  const ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.fillStyle = "rgba(255,255,255,0.86)";
  const w = ctx.measureText(text).width;
  ctx.font = "600 26px Georgia, serif";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillStyle = "#1f2937";
  ctx.fillText(text, 128, 34);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sp = new THREE.Sprite(mat);
  sp.scale.set(2.2, 0.55, 1);
  return sp;
}

export const FloorPlan3D = forwardRef(function FloorPlan3D({ cadData, markers, roof, pinSpecs, className }, ref) {
  const mountRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneStateRef = useRef(null);

  useImperativeHandle(ref, () => ({
    capture: () => {
      const st = sceneStateRef.current;
      if (!st) return null;
      st.renderer.render(st.scene, st.camera);
      try { return st.renderer.domElement.toDataURL("image/png"); } catch { return null; }
    },
  }));

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const cad = cadData || {};
    let floors = Array.isArray(cad.floors) && cad.floors.length ? cad.floors : (cad.rooms ? [{ rooms: cad.rooms }] : []);
    floors = floors.filter((f) => (f?.rooms || []).length);
    if (!floors.length) return;

    const width = mount.clientWidth || 800;
    const height = mount.clientHeight || 460;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f5f8);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // extent
    const num = (v) => (isFinite(+v) ? +v : 0);
    let maxx = 0, maxy = 0;
    floors.forEach((f) => (f.rooms || []).forEach((r) => { maxx = Math.max(maxx, num(r.x) + num(r.w)); maxy = Math.max(maxy, num(r.y) + num(r.h)); }));
    const cx = maxx / 2, cy = maxy / 2;

    const root = new THREE.Group();
    scene.add(root);
    const pickables = [];

    floors.forEach((f, fi) => {
      const zBase = fi * (WALL_H + FLOOR_GAP);
      (f.rooms || []).forEach((r) => {
        const w = num(r.w), d = num(r.h);
        if (w <= 0 || d <= 0) return;
        const x = num(r.x) - cx + w / 2, y = num(r.y) - cy + d / 2;
        // walls: a slightly hollow box (box shell) via BoxGeometry with wireframe edges + solid floor slab
        const slab = new THREE.Mesh(new THREE.BoxGeometry(w, 0.08, d), new THREE.MeshStandardMaterial({ color: ROOM_TONE(r.name), roughness: 0.95 }));
        slab.position.set(x, zBase + 0.04, y); slab.receiveShadow = true; root.add(slab);
        const wall = new THREE.Mesh(new THREE.BoxGeometry(w, WALL_H, d), new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.16, roughness: 1 }));
        wall.position.set(x, zBase + WALL_H / 2, y); wall.castShadow = true; root.add(wall);
        slab.userData = { kind: "room", name: (r.name || "").trim(), wall }; pickables.push(slab);
        const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, WALL_H, d)), new THREE.LineBasicMaterial({ color: 0x6b7685 }));
        edges.position.set(x, zBase + WALL_H / 2, y); root.add(edges);
        if ((r.name || "").trim()) {
          const sp = labelSprite(r.name.trim());
          sp.position.set(x, zBase + WALL_H + 0.5, y);
          root.add(sp);
        }
      });
    });

    // ── survey-driven openings (windows + doors) and staircase ──
    const glassMat = new THREE.MeshStandardMaterial({ color: 0x9fc6e0, transparent: true, opacity: 0.5, roughness: 0.1, metalness: 0.1, side: THREE.DoubleSide });
    const doorMat = new THREE.MeshStandardMaterial({ color: 0x9c6b3f, roughness: 0.85 });
    const frontDoorMat = new THREE.MeshStandardMaterial({ color: 0x2f5d50, roughness: 0.7 });
    const SILL = 0.85, WIN_H = 1.15, WIN_W = 1.05, EPS = 0.04;
    const addWindow = (wx, wz, faceX, yc) => {
      const g = new THREE.PlaneGeometry(WIN_W, WIN_H);
      const glass = new THREE.Mesh(g, glassMat);
      const frame = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({ color: 0x3f5060 }));
      glass.position.set(wx, yc, wz); frame.position.set(wx, yc, wz);
      if (faceX) { glass.rotation.y = Math.PI / 2; frame.rotation.y = Math.PI / 2; }
      root.add(glass); root.add(frame);
    };
    floors.forEach((f, fi) => {
      const zBase = fi * (WALL_H + FLOOR_GAP);
      const yc = zBase + SILL + WIN_H / 2;
      (f.windows || []).forEach((w) => {
        const wall = (w.wall || "").toLowerCase();
        if ((w.label || "").toUpperCase() === "NEI") return; // neighbour / party wall — not a window
        const along = (w.y != null ? num(w.y) : num(w.x)); // survey stores along-wall pos under x or y
        if (wall === "top") addWindow(num(w.x) - cx, -cy + EPS, false, yc);
        else if (wall === "bottom") addWindow(num(w.x) - cx, maxy - cy - EPS, false, yc);
        else if (wall === "left") addWindow(-cx + EPS, along - cy, true, yc);
        else if (wall === "right") addWindow(maxx - cx - EPS, along - cy, true, yc);
      });
      (f.doors || []).forEach((dr) => {
        const g = new THREE.BoxGeometry(0.85, 2.0, 0.05); g.translate(0.425, 0, 0);
        const leaf = new THREE.Mesh(g, doorMat);
        leaf.position.set(num(dr.x) - cx, zBase + 1.02, num(dr.y) - cy); leaf.rotation.y = -Math.PI / 5;
        root.add(leaf);
      });
    });
    // front door on the ground-floor external wall
    const fd = floors[0] && floors[0].frontDoor;
    if (fd && (fd.x != null || fd.y != null)) {
      const W = maxx, H = maxy;
      let wall = (fd.wall || "").toLowerCase();
      const px = num(fd.x), py = num(fd.y);
      if (!["top", "bottom", "left", "right"].includes(wall)) {
        const dist = { top: Math.abs(py), bottom: Math.abs(py - H), left: Math.abs(px), right: Math.abs(px - W) };
        wall = Object.keys(dist).reduce((a, b) => (dist[a] < dist[b] ? a : b));
      }
      let fx, fz, faceX = false;
      if (wall === "top") { fx = (fd.x != null ? px : W / 2) - cx; fz = -cy; }
      else if (wall === "bottom") { fx = (fd.x != null ? px : W / 2) - cx; fz = maxy - cy; }
      else if (wall === "left") { faceX = true; fx = -cx; fz = (fd.y != null ? py : H / 2) - cy; }
      else { faceX = true; fx = maxx - cx; fz = (fd.y != null ? py : H / 2) - cy; }
      const g = new THREE.BoxGeometry(1.0, 2.1, 0.08); g.translate(0.5, 0, 0);
      const door = new THREE.Mesh(g, frontDoorMat);
      door.position.set(fx, 1.05, fz);
      door.rotation.y = faceX ? (Math.PI / 2 - Math.PI / 6) : -Math.PI / 6;
      root.add(door);
      door.userData = { kind: "pin", title: "Front Door", spec: "Main entrance" }; pickables.push(door);
    }
    // staircase rising from the ground-floor Hall to the First-floor Landing
    if (floors.length >= 2) {
      const g0 = floors[0].rooms || [];
      const hall = g0.find((r) => /hall|hallway|entrance|lobby|corridor|foyer/i.test(r.name || ""))
        || g0.find((r) => /stair/i.test(r.name || ""));
      if (hall) {
        const hx = num(hall.x), hy = num(hall.y), hw = num(hall.w), hh = num(hall.h);
        const riser = 0.21, totalRise = WALL_H + FLOOR_GAP;
        const n = Math.max(6, Math.round(totalRise / riser));
        const alongX = hw >= hh;
        const stairW = Math.min(0.95, (alongX ? hh : hw) * 0.7) || 0.8;
        const going = Math.min(0.26, ((alongX ? hw : hh) * 0.85) / n) || 0.2;
        const runLen = n * going;
        const cxm = hx + hw / 2, cym = hy + hh / 2;
        const startAlong = (alongX ? cxm : cym) - runLen / 2;
        const stMat = new THREE.MeshStandardMaterial({ color: 0xc2c7cf, roughness: 0.9 });
        const stair = new THREE.Group();
        for (let i = 0; i < n; i++) {
          const bh = (i + 1) * (totalRise / n);
          const step = new THREE.Mesh(new THREE.BoxGeometry(alongX ? going : stairW, bh, alongX ? stairW : going), stMat);
          const alongPos = startAlong + i * going + going / 2;
          step.position.set((alongX ? alongPos : cxm) - cx, bh / 2, (alongX ? cym : alongPos) - cy);
          stair.add(step);
        }
        root.add(stair);
      }
    }

    // pitched roof over the top storey (form taken from the property photos where available)
    const rtype = (roof?.type || "hipped").toLowerCase();
    const rtop = (floors[floors.length - 1].rooms || []);
    if (rtop.length) {
      let a = Infinity, b = Infinity, cc = -Infinity, dd = -Infinity;
      rtop.forEach((r) => { a = Math.min(a, num(r.x)); b = Math.min(b, num(r.y)); cc = Math.max(cc, num(r.x) + num(r.w)); dd = Math.max(dd, num(r.y) + num(r.h)); });
      const OV = 0.3; a -= OV; b -= OV; cc += OV; dd += OV;
      const rw = cc - a, rd = dd - b, zt = (floors.length - 1) * (WALL_H + FLOOR_GAP) + WALL_H;
      const rh = (rtype === "flat" ? 0.14 : 0.5) * Math.min(rw, rd);
      const rmat = new THREE.MeshStandardMaterial({ color: ROOF_HEX(roof?.covering), roughness: 0.9, flatShading: true });
      let roofMesh;
      if (rtype === "gabled") {
        const ridge = (roof?.ridge || "").toLowerCase();
        let along = rw >= rd;
        if (ridge === "side-to-side") along = true; else if (ridge === "front-to-back") along = false;
        const L = along ? rw : rd; const W = along ? rd : rw;
        const shp = new THREE.Shape(); shp.moveTo(-W / 2, 0); shp.lineTo(W / 2, 0); shp.lineTo(0, rh); shp.closePath();
        const g = new THREE.ExtrudeGeometry(shp, { depth: L, bevelEnabled: false }); g.translate(0, 0, -L / 2);
        roofMesh = new THREE.Mesh(g, rmat);
        if (along) roofMesh.rotation.y = Math.PI / 2;
        roofMesh.position.set((a + cc) / 2 - cx, zt, (b + dd) / 2 - cy);
      } else {
        roofMesh = new THREE.Mesh(new THREE.ConeGeometry(Math.SQRT2 / 2, rh, 4), rmat);
        roofMesh.scale.set(rw, 1, rd); roofMesh.rotation.y = Math.PI / 4;
        roofMesh.position.set((a + cc) / 2 - cx, zt + rh / 2, (b + dd) / 2 - cy);
      }
      roofMesh.castShadow = true; root.add(roofMesh);
    }

    // measure pins (dMEV / loft / trickle / ASHP) mapped from the 2D location-plan markers
    const PIN_COL = { DMEV: 0x0891b2, LOFT: 0xb45309, TRICKLE: 0x16a34a, ASHP: 0x0055ff };
    const N = floors.length;
    (markers || []).forEach((m) => {
      const t = (m.type || "").toUpperCase();
      const col = PIN_COL[t] || 0x525252;
      const fyv = (num(m.y) / 100) * N;
      const fi = Math.min(Math.max(Math.floor(fyv), 0), N - 1);
      const local = fyv - fi;
      let wx = (num(m.x) / 100) * maxx - cx, wz = local * maxy - cy;
      let py = fi * (WALL_H + FLOOR_GAP) + WALL_H + 0.55;
      if (t === "ASHP") { wx = maxx / 2 + 1.5; wz = maxy * 0.2 - cy; py = 1.0; }
      else if (t === "LOFT") { wx = 0; wz = 0; py = (N - 1) * (WALL_H + FLOOR_GAP) + WALL_H + 1.4; }
      const pin = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.6, 14), new THREE.MeshStandardMaterial({ color: col }));
      pin.rotation.x = Math.PI; pin.position.set(wx, py, wz); root.add(pin);
      pin.userData = { kind: "pin", title: m.label || t, spec: (pinSpecs && pinSpecs[t]) || m.spec || "" }; pickables.push(pin);
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.85), new THREE.MeshBasicMaterial({ color: col }));
      stem.position.set(wx, py - 0.5, wz); root.add(stem);
      const lab = labelSprite(m.label || t); lab.position.set(wx, py + 0.55, wz); lab.scale.set(1.7, 0.42, 1); root.add(lab);
    });

    // ground plane
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(maxx * 3, maxy * 3), new THREE.MeshStandardMaterial({ color: 0xe7ebf0, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.02; ground.receiveShadow = true; scene.add(ground);

    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(maxx, maxx * 1.4, maxy); key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024); key.shadow.camera.far = maxx * 6;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe8f5, 0.4); fill.position.set(-maxx, maxx, -maxy); scene.add(fill);

    const span = Math.max(maxx, maxy, 6);
    camera.position.set(span * 1.1, span * 1.15, span * 1.4);
    camera.lookAt(0, floors.length * (WALL_H + FLOOR_GAP) * 0.4, 0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.target.set(0, floors.length * (WALL_H + FLOOR_GAP) * 0.4, 0);
    controls.minDistance = span * 0.5; controls.maxDistance = span * 4;
    controls.maxPolarAngle = Math.PI / 2.05;
    controls.update();

    // ─ interactivity: hover pins for a tooltip, click rooms to highlight ─
    const esc = (t) => String(t).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const tip = document.createElement("div");
    Object.assign(tip.style, { position: "absolute", pointerEvents: "none", zIndex: 6, maxWidth: "240px", padding: "7px 9px", borderRadius: "6px", background: "rgba(17,24,39,0.94)", color: "#fff", font: "500 11px/1.4 Georgia, serif", boxShadow: "0 6px 18px rgba(0,0,0,0.28)", opacity: "0", transition: "opacity .12s", transform: "translate(-50%, calc(-100% - 14px))" });
    tip.setAttribute("data-testid", "floorplan-3d-tooltip");
    mount.appendChild(tip);
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let selected = null;
    const setSel = (slab) => {
      if (selected) { selected.material.emissive.setHex(0x000000); if (selected.userData.wall) selected.userData.wall.material.opacity = 0.16; }
      selected = slab || null;
      if (selected) { selected.material.emissive.setHex(0x1d4ed8); selected.material.emissiveIntensity = 0.3; if (selected.userData.wall) selected.userData.wall.material.opacity = 0.34; }
    };
    const pick = (e) => {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      return { hits: ray.intersectObjects(pickables, false), rect };
    };
    const onHover = (e) => {
      const { hits, rect } = pick(e);
      const o = hits[0] && hits[0].object;
      if (o && o.userData.kind === "pin") {
        tip.innerHTML = `<div style="font-weight:700;margin-bottom:2px;">${esc(o.userData.title)}</div>${o.userData.spec ? `<div style="opacity:.85;">${esc(o.userData.spec)}</div>` : ""}`;
        tip.style.left = (e.clientX - rect.left) + "px"; tip.style.top = (e.clientY - rect.top) + "px"; tip.style.opacity = "1";
        renderer.domElement.style.cursor = "pointer";
      } else if (o && o.userData.kind === "room" && o.userData.name) {
        tip.innerHTML = `<div style="font-weight:700;">${esc(o.userData.name)}</div><div style="opacity:.75;">Click to highlight</div>`;
        tip.style.left = (e.clientX - rect.left) + "px"; tip.style.top = (e.clientY - rect.top) + "px"; tip.style.opacity = "1";
        renderer.domElement.style.cursor = "pointer";
      } else { tip.style.opacity = "0"; renderer.domElement.style.cursor = "grab"; }
    };
    let down = null;
    const onDown = (e) => { down = [e.clientX, e.clientY]; };
    const onUp = (e) => {
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5) {
        const { hits } = pick(e);
        const room = hits.find((h) => h.object.userData.kind === "room");
        if (room) setSel(selected === room.object ? null : room.object);
      }
      down = null;
    };
    const onLeave = () => { tip.style.opacity = "0"; };
    const cv = renderer.domElement;
    cv.addEventListener("pointermove", onHover);
    cv.addEventListener("pointerdown", onDown);
    cv.addEventListener("pointerup", onUp);
    cv.addEventListener("pointerleave", onLeave);

    sceneStateRef.current = { renderer, scene, camera };

    let raf;
    const loop = () => { controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(loop); };
    loop();

    const onResize = () => {
      const w = mount.clientWidth || width, h = mount.clientHeight || height;
      camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      cv.removeEventListener("pointermove", onHover);
      cv.removeEventListener("pointerdown", onDown);
      cv.removeEventListener("pointerup", onUp);
      cv.removeEventListener("pointerleave", onLeave);
      if (tip.parentNode === mount) mount.removeChild(tip);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
      sceneStateRef.current = null;
    };
  }, [cadData, markers, roof, pinSpecs]);

  return <div ref={mountRef} className={className} data-testid="floorplan-3d-canvas" style={{ position: "relative", width: "100%", height: 460, cursor: "grab" }} />;
});
