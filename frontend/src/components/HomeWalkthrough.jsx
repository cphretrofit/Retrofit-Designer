import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { X, ArrowUpRight, ArrowLeft, Camera, ChevronLeft, ChevronRight } from "lucide-react";
import { getRoomPhotos, mediaUrl } from "@/lib/api";

const FLOOR_NAMES = ["Ground floor", "First floor", "Second floor", "Third floor"];
const num = (v) => (isFinite(+v) ? +v : 0);
const M = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.92, ...o });
const COL = {
  wood: 0xd9b489, woodDk: 0xb98f57, cream: 0xefe9df, wall: 0xf4f1ea, white: 0xf8f7f4,
  fabric: 0xece7dd, dark: 0x2f3b46, green: 0x4f8a5b, pot: 0xe8e2d6, steel: 0xd8dde0, unit: 0xdfe4dd,
};

const roomTypeOf = (name) => {
  const n = (name || "").toLowerCase();
  if (/kitchen/.test(n)) return "kitchen";
  if (/dining/.test(n)) return "dining";
  if (/(lounge|living|sitting|reception)/.test(n)) return "lounge";
  if (/bed/.test(n)) return "bed";
  if (/(bath|shower|ensuite|en-suite|wc|toilet|cloak)/.test(n)) return "bath";
  if (/(hall|landing|stair|corridor|lobby|entrance)/.test(n)) return "hall";
  return "other";
};

function fSofa(w) {
  const g = new THREE.Group();
  const sw = Math.min(2.2, Math.max(1.2, w * 0.55)), sd = 0.85;
  const base = new THREE.Mesh(new THREE.BoxGeometry(sw, 0.38, sd), M(COL.fabric)); base.position.y = 0.2; g.add(base);
  const back = new THREE.Mesh(new THREE.BoxGeometry(sw, 0.5, 0.2), M(COL.fabric)); back.position.set(0, 0.55, -sd / 2 + 0.1); g.add(back);
  for (let i = 0; i < 3; i++) {
    const c = new THREE.Mesh(new THREE.SphereGeometry(0.25, 18, 14), M(COL.white));
    c.position.set(-sw / 2 + 0.35 + i * (sw - 0.7) / 2, 0.6, 0); c.scale.set(1, 0.85, 0.9); g.add(c);
  }
  return g;
}
function fTable(tw, td, h, col) {
  const g = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(tw, 0.06, td), M(col)); top.position.y = h; g.add(top);
  [[tw / 2 - 0.06, td / 2 - 0.06], [-tw / 2 + 0.06, td / 2 - 0.06], [tw / 2 - 0.06, -td / 2 + 0.06], [-tw / 2 + 0.06, -td / 2 + 0.06]]
    .forEach(([x, z]) => { const l = new THREE.Mesh(new THREE.BoxGeometry(0.06, h, 0.06), M(col)); l.position.set(x, h / 2, z); g.add(l); });
  return g;
}
function fPlant() {
  const g = new THREE.Group();
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.12, 0.3, 16), M(COL.pot)); pot.position.y = 0.15; g.add(pot);
  for (let i = 0; i < 3; i++) { const lf = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.55, 10), M(COL.green)); lf.position.set((i - 1) * 0.08, 0.58, 0); lf.rotation.z = (i - 1) * 0.24; g.add(lf); }
  return g;
}
function fChair(x, z, rot) {
  const c = new THREE.Group();
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.06, 0.42), M(COL.unit)); seat.position.y = 0.45; c.add(seat);
  const bk = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.45, 0.06), M(COL.unit)); bk.position.set(0, 0.68, -0.18); c.add(bk);
  [[0.17, 0.17], [-0.17, 0.17], [0.17, -0.17], [-0.17, -0.17]].forEach(([lx, lz]) => { const l = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.45, 0.05), M(COL.unit)); l.position.set(lx, 0.22, lz); c.add(l); });
  c.position.set(x, 0, z); c.rotation.y = rot; return c;
}
function furnitureFor(type, w, d) {
  const g = new THREE.Group();
  const back = -d / 2;
  if (type === "lounge") {
    const s = fSofa(w); s.position.set(0, 0, back + 0.55); g.add(s);
    const t = fTable(Math.min(1.1, w * 0.4), 0.6, 0.42, COL.wood); t.position.set(0, 0, 0.1); g.add(t);
    const p = fPlant(); p.position.set(w / 2 - 0.4, 0, d / 2 - 0.4); g.add(p);
  } else if (type === "dining") {
    const tw = Math.min(1.4, w * 0.5), td = Math.min(0.85, d * 0.45);
    g.add(fTable(tw, td, 0.75, COL.wood));
    g.add(fChair(0, td / 2 + 0.35, 0)); g.add(fChair(0, -td / 2 - 0.35, Math.PI));
    g.add(fChair(tw / 2 + 0.35, 0, -Math.PI / 2)); g.add(fChair(-tw / 2 - 0.35, 0, Math.PI / 2));
    const p = fPlant(); p.position.set(w / 2 - 0.4, 0, d / 2 - 0.4); g.add(p);
  } else if (type === "kitchen") {
    const runW = w * 0.86;
    const unit = new THREE.Mesh(new THREE.BoxGeometry(runW, 0.9, 0.6), M(COL.unit)); unit.position.set(0, 0.45, back + 0.35); g.add(unit);
    const wtop = new THREE.Mesh(new THREE.BoxGeometry(runW, 0.06, 0.62), M(COL.white)); wtop.position.set(0, 0.92, back + 0.35); g.add(wtop);
    const hob = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.04, 0.5), M(COL.dark)); hob.position.set(runW * 0.25, 0.96, back + 0.35); g.add(hob);
    const sink = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.06, 0.4), M(COL.steel)); sink.position.set(-runW * 0.25, 0.95, back + 0.35); g.add(sink);
    const fridge = new THREE.Mesh(new THREE.BoxGeometry(0.6, 1.7, 0.6), M(COL.white)); fridge.position.set(-runW / 2 + 0.3, 0.85, back + 0.9); g.add(fridge);
  } else if (type === "bed") {
    const bw = Math.min(1.5, w * 0.6), bl = Math.min(2.0, d * 0.7);
    const bed = new THREE.Mesh(new THREE.BoxGeometry(bw, 0.4, bl), M(COL.fabric)); bed.position.set(0, 0.2, back + bl / 2 + 0.15); g.add(bed);
    const hb = new THREE.Mesh(new THREE.BoxGeometry(bw, 0.6, 0.1), M(COL.woodDk)); hb.position.set(0, 0.4, back + 0.12); g.add(hb);
    const pil = new THREE.Mesh(new THREE.BoxGeometry(bw * 0.82, 0.15, 0.4), M(COL.white)); pil.position.set(0, 0.46, back + 0.5); g.add(pil);
    const st = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 0.4), M(COL.woodDk)); st.position.set(bw / 2 + 0.35, 0.2, back + 0.35); g.add(st);
  } else if (type === "bath") {
    const tub = new THREE.Mesh(new THREE.BoxGeometry(Math.min(1.6, w * 0.7), 0.55, 0.75), M(COL.white)); tub.position.set(0, 0.28, back + 0.5); g.add(tub);
    const ped = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.8, 0.2), M(COL.white)); ped.position.set(w / 2 - 0.4, 0.4, back + 0.35); g.add(ped);
    const basin = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.2, 0.4), M(COL.white)); basin.position.set(w / 2 - 0.4, 0.82, back + 0.35); g.add(basin);
  }
  return g;
}

function buildRoomShell(w, d) {
  const g = new THREE.Group(); const H = 2.5, t = 0.09;
  const floor = new THREE.Mesh(new THREE.BoxGeometry(w, 0.06, d), M(COL.wood)); floor.position.y = 0.03; floor.receiveShadow = true; g.add(floor);
  const ceil = new THREE.Mesh(new THREE.BoxGeometry(w, 0.06, d), M(COL.wall)); ceil.position.y = H; g.add(ceil);
  const wmat = M(COL.wall);
  const mk = (gw, gd, x, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(gw, H, gd), wmat); m.position.set(x, H / 2, z); g.add(m); };
  mk(w, t, 0, -d / 2); mk(w, t, 0, d / 2); mk(t, d, -w / 2, 0); mk(t, d, w / 2, 0);
  const win = new THREE.Mesh(new THREE.PlaneGeometry(Math.min(1.9, w * 0.55), 1.25),
    new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.85, transparent: true, opacity: 0.94, side: THREE.DoubleSide }));
  win.position.set(0, 1.35, d / 2 - 0.06); g.add(win);
  const rad = new THREE.Mesh(new THREE.BoxGeometry(Math.min(1.2, w * 0.4), 0.5, 0.08), M(COL.white)); rad.position.set(0, 0.45, d / 2 - 0.14); g.add(rad);
  const lamp = new THREE.PointLight(0xfff3e2, 0.9, Math.max(w, d) * 3.2, 2); lamp.position.set(0, H - 0.3, 0); g.add(lamp);
  return g;
}

export function HomeWalkthrough({ cadData, projectId, onClose }) {
  const mountRef = useRef(null);
  const S = useRef({});
  const pillRefs = useRef([]);
  const [rooms, setRooms] = useState([]);
  const [activeFloor, setActiveFloor] = useState(0);
  const [mode, setMode] = useState("overview"); // overview | room
  const [activeRoom, setActiveRoom] = useState(null);
  const [roomPhotos, setRoomPhotos] = useState(null);
  const [photoIdx, setPhotoIdx] = useState(0);

  useEffect(() => { if (projectId) getRoomPhotos(projectId).then(setRoomPhotos).catch(() => {}); }, [projectId]);

  const cad = cadData || {};
  let floors = Array.isArray(cad.floors) && cad.floors.length ? cad.floors : (cad.rooms ? [{ rooms: cad.rooms }] : []);
  floors = floors.filter((f) => (f?.rooms || []).length);
  const photosCountFor = (i) => (roomPhotos?.floors?.[activeFloor]?.[i]?.photos || []).length;
  const photosForActive = (roomPhotos?.floors?.[activeFloor]?.[activeRoom]?.photos) || [];

  const enterRoom = (i) => {
    const st = S.current; const rm = st.roomsMeta?.[i]; if (!rm) return;
    setActiveRoom(i); setMode("room"); setPhotoIdx(0);
    st.mode = "room";
    if (st.dollGroup) st.dollGroup.visible = false;
    (st.furnGroups || []).forEach((g, j) => { if (g) g.visible = j === i; });
    if (st.shell) { st.scene.remove(st.shell); st.shell = null; }
    const shell = buildRoomShell(rm.w, rm.d); shell.position.set(rm.wx, 0, rm.wz); st.scene.add(shell); st.shell = shell;
    st.goal = { pos: new THREE.Vector3(rm.wx + rm.w * 0.3, 1.55, rm.wz + rm.d * 0.42), look: new THREE.Vector3(rm.wx - rm.w * 0.12, 1.05, rm.wz - rm.d * 0.18) };
    st.controls.enabled = false; st.controls.minDistance = 0.4; st.controls.maxDistance = Math.max(rm.w, rm.d) * 1.6;
  };
  const backToOverview = () => {
    const st = S.current; setMode("overview"); setActiveRoom(null); st.mode = "overview";
    if (st.shell) { st.scene.remove(st.shell); st.shell = null; }
    if (st.dollGroup) st.dollGroup.visible = true;
    (st.furnGroups || []).forEach((g) => { if (g) g.visible = true; });
    if (st.overviewPose) st.goal = { pos: st.overviewPose.pos.clone(), look: st.overviewPose.look.clone() };
    st.controls.enabled = false; st.controls.minDistance = st.span * 0.4; st.controls.maxDistance = st.span * 4;
  };

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const f = floors[activeFloor] || floors[0];
    const rlist = (f?.rooms || []).filter((r) => num(r.w) > 0 && num(r.h) > 0);
    if (!rlist.length) return;

    const width = mount.clientWidth || 900, height = mount.clientHeight || 560;
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0xeeeeec);
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.05, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.setSize(width, height);
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);

    let maxx = 0, maxy = 0;
    rlist.forEach((r) => { maxx = Math.max(maxx, num(r.x) + num(r.w)); maxy = Math.max(maxy, num(r.y) + num(r.h)); });
    const CX = maxx / 2, CY = maxy / 2;

    const dollGroup = new THREE.Group(); scene.add(dollGroup);
    const furnGroups = []; const roomsMeta = [];
    const WALL_H = 1.45, t = 0.1;
    rlist.forEach((r, i) => {
      const w = num(r.w), d = num(r.h);
      const wx = num(r.x) + w / 2 - CX, wz = num(r.y) + d / 2 - CY;
      const type = roomTypeOf(r.name);
      const floor = new THREE.Mesh(new THREE.BoxGeometry(w, 0.08, d), M(type === "hall" ? COL.cream : COL.wood));
      floor.position.set(wx, 0.04, wz); floor.receiveShadow = true; dollGroup.add(floor);
      const wmat = M(COL.wall);
      const mk = (gw, gd, x, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(gw, WALL_H, gd), wmat); m.position.set(wx + x, WALL_H / 2, wz + z); m.castShadow = true; dollGroup.add(m); };
      mk(w, t, 0, -d / 2); mk(w, t, 0, d / 2); mk(t, d, -w / 2, 0); mk(t, d, w / 2, 0);
      const fg = furnitureFor(type, w, d); fg.position.set(wx, 0, wz); scene.add(fg); furnGroups[i] = fg;
      roomsMeta[i] = { name: (r.name || "").trim() || `Room ${i + 1}`, w, d, wx, wz, type };
    });

    // staircase in the hall (overview only)
    const hall = rlist.find((r) => /hall|hallway|entrance|lobby|corridor|foyer|landing|stair/i.test(r.name || ""));
    if (hall) {
      const hx = num(hall.x), hy = num(hall.y), hw = num(hall.w), hh = num(hall.h);
      const alongX = hw >= hh, n = 12, riser = WALL_H / n;
      const stairW = Math.min(0.95, (alongX ? hh : hw) * 0.7) || 0.7;
      const going = Math.min(0.26, ((alongX ? hw : hh) * 0.85) / n) || 0.2;
      const cxm = hx + hw / 2, cym = hy + hh / 2, start = (alongX ? cxm : cym) - (n * going) / 2;
      const stMat = M(0xc9cdd4);
      for (let i = 0; i < n; i++) {
        const bh = (i + 1) * riser;
        const step = new THREE.Mesh(new THREE.BoxGeometry(alongX ? going : stairW, bh, alongX ? stairW : going), stMat);
        const ap = start + i * going + going / 2;
        step.position.set((alongX ? ap : cxm) - CX, bh / 2, (alongX ? cym : ap) - CY); step.castShadow = true;
        dollGroup.add(step);
      }
    }

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(maxx * 4, maxy * 4), M(0xf4f4f2)); ground.rotation.x = -Math.PI / 2; ground.position.y = -0.01; ground.receiveShadow = true; scene.add(ground);
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    scene.add(new THREE.HemisphereLight(0xffffff, 0xe6e6df, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.05); key.position.set(maxx, maxx * 1.5, maxy); key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.camera.far = maxx * 8; key.shadow.camera.left = -maxx; key.shadow.camera.right = maxx; key.shadow.camera.top = maxy; key.shadow.camera.bottom = -maxy; scene.add(key);
    scene.add(new THREE.DirectionalLight(0xeaf0ff, 0.35).translateX(-maxx).translateZ(-maxy));

    const span = Math.max(maxx, maxy, 6);
    const overviewPose = { pos: new THREE.Vector3(span * 1.0, span * 1.25, span * 1.4), look: new THREE.Vector3(0, 0.5, 0) };
    camera.position.copy(overviewPose.pos);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08; controls.target.copy(overviewPose.look);
    controls.minDistance = span * 0.4; controls.maxDistance = span * 4; controls.maxPolarAngle = Math.PI / 2.02; controls.update();

    S.current = { scene, camera, renderer, controls, dollGroup, furnGroups, roomsMeta, overviewPose, span, goal: null, mode: "overview", shell: null };
    setRooms(roomsMeta);

    const v = new THREE.Vector3();
    let raf;
    const loop = () => {
      const st = S.current;
      if (st.goal) {
        camera.position.lerp(st.goal.pos, 0.09); controls.target.lerp(st.goal.look, 0.09);
        if (camera.position.distanceTo(st.goal.pos) < 0.1) { st.goal = null; controls.enabled = true; }
      }
      controls.update();
      // position room pills
      roomsMeta.forEach((rm, i) => {
        const el = pillRefs.current[i]; if (!el) return;
        if (st.mode === "room") { el.style.display = "none"; return; }
        v.set(rm.wx, WALL_H + 0.15, rm.wz).project(camera);
        if (v.z > 1) { el.style.display = "none"; return; }
        el.style.display = "block";
        el.style.left = ((v.x * 0.5 + 0.5) * width) + "px";
        el.style.top = ((-v.y * 0.5 + 0.5) * height) + "px";
      });
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };
    loop();

    const onResize = () => { const w = mount.clientWidth, h = mount.clientHeight; camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h); };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf); window.removeEventListener("resize", onResize);
      controls.dispose(); renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
      S.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cadData, activeFloor]);

  return (
    <div className="fixed inset-0 z-[60] bg-white flex flex-col anim-in" data-testid="home-walkthrough">
      <div className="flex items-center justify-between px-6 h-16 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-md bg-[var(--c-action)] text-white flex items-center justify-center font-display font-300 text-lg">H</div>
          <div>
            <div className="text-[15px] font-medium leading-tight">Home walkthrough</div>
            <div className="text-[12px] text-muted-foreground leading-tight">Your floor plan, in three dimensions</div>
          </div>
        </div>
        <button onClick={onClose} data-testid="walkthrough-close" className="flex items-center gap-1.5 h-9 px-3 border border-border rounded-full text-[12.5px] font-medium hover:bg-secondary transition-colors">
          <X className="h-4 w-4" strokeWidth={1.75} /> Close
        </button>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* sidebar */}
        <aside className="w-[300px] shrink-0 border-r border-border overflow-y-auto p-5 hidden md:block" data-testid="walkthrough-sidebar">
          <div className="text-[17px] font-medium">Explore the house</div>
          <div className="text-[12.5px] text-muted-foreground mt-0.5">Choose a room to step inside.</div>
          {floors.length > 1 && (
            <div className="mt-4 inline-flex rounded-md border border-border overflow-hidden w-full" data-testid="walkthrough-floor-toggle">
              {floors.map((_, i) => (
                <button key={i} onClick={() => { setActiveFloor(i); setMode("overview"); setActiveRoom(null); }} data-testid={`walkthrough-floor-${i}`}
                  className={`flex-1 h-9 text-[12.5px] font-medium transition-colors ${i === activeFloor ? "bg-[var(--c-action)] text-white" : "hover:bg-secondary"}`}>
                  {FLOOR_NAMES[i] || `Floor ${i + 1}`}
                </button>
              ))}
            </div>
          )}
          <div className="mt-4 divide-y divide-border/70 border-t border-border">
            {rooms.map((r, i) => (
              <button key={i} onClick={() => enterRoom(i)} data-testid={`walkthrough-room-${i}`}
                className={`w-full flex items-center gap-3 py-3 text-left group ${activeRoom === i ? "text-[var(--c-action)]" : ""}`}>
                <span className="text-[11px] font-mono text-muted-foreground w-6">{String(i + 1).padStart(2, "0")}</span>
                <span className="flex-1 min-w-0">
                  <span className="block text-[14px] font-medium truncate">{r.name}</span>
                  <span className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                    {r.type === "hall" ? "Stair shape indicative" : `${r.w.toFixed(2)} × ${r.d.toFixed(2)} m`}
                    {photosCountFor(i) > 0 && <span className="inline-flex items-center gap-0.5 text-[var(--c-action)]"><Camera className="h-3 w-3" strokeWidth={1.75} />{photosCountFor(i)}</span>}
                  </span>
                </span>
                <ArrowUpRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" strokeWidth={1.75} />
              </button>
            ))}
          </div>
          <MiniPlan rooms={rooms} active={activeRoom} floorName={FLOOR_NAMES[activeFloor] || "Floor"} onPick={enterRoom} />
          <div className="mt-4 text-[11px] text-muted-foreground leading-relaxed">
            Concept model based on your survey. Openings, stairs and furniture are approximate — not a measured survey.
          </div>
        </aside>

        {/* viewport */}
        <div className="relative flex-1 min-w-0 bg-[#eeeeec]">
          <div ref={mountRef} data-testid="walkthrough-canvas" className="absolute inset-0" style={{ cursor: mode === "room" ? "default" : "grab" }} />
          {/* immersive real-photo backdrop when stepping inside a room that has survey photos */}
          {mode === "room" && photosForActive.length > 0 && (
            <div className="absolute inset-0 bg-black" data-testid="walkthrough-photo">
              <img key={photoIdx} src={mediaUrl(photosForActive[Math.min(photoIdx, photosForActive.length - 1)].url)} alt="Survey photo"
                className="w-full h-full object-cover anim-in" />
              <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.28), rgba(0,0,0,0) 22%, rgba(0,0,0,0) 68%, rgba(0,0,0,0.42))" }} />
              {photosForActive.length > 1 && (
                <>
                  <button onClick={() => setPhotoIdx((k) => (k - 1 + photosForActive.length) % photosForActive.length)} data-testid="walkthrough-photo-prev"
                    className="absolute left-4 top-1/2 -translate-y-1/2 h-11 w-11 rounded-full bg-white/85 hover:bg-white flex items-center justify-center shadow transition-colors"><ChevronLeft className="h-5 w-5" /></button>
                  <button onClick={() => setPhotoIdx((k) => (k + 1) % photosForActive.length)} data-testid="walkthrough-photo-next"
                    className="absolute right-4 top-1/2 -translate-y-1/2 h-11 w-11 rounded-full bg-white/85 hover:bg-white flex items-center justify-center shadow transition-colors"><ChevronRight className="h-5 w-5" /></button>
                </>
              )}
              <div className="absolute bottom-5 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-black/60 text-white text-[12px] px-3.5 py-1.5 rounded-full">
                <Camera className="h-3.5 w-3.5" strokeWidth={1.75} /> Actual survey photo · {Math.min(photoIdx, photosForActive.length - 1) + 1} / {photosForActive.length}
              </div>
            </div>
          )}
          {/* view card */}
          <div className="absolute top-5 left-5 bg-white/95 backdrop-blur border border-border rounded-lg px-5 py-4 shadow-sm pointer-events-none" data-testid="walkthrough-viewcard">
            <div className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground">{mode === "room" ? "Room view · eye level" : "Dollhouse view"}</div>
            <div className="text-[22px] font-display font-300 leading-tight mt-0.5">{mode === "room" && rooms[activeRoom] ? rooms[activeRoom].name : (FLOOR_NAMES[activeFloor] || "Floor")}</div>
            <div className="text-[12px] text-muted-foreground mt-0.5">
              {mode === "room" && rooms[activeRoom] ? `${rooms[activeRoom].w.toFixed(2)} × ${rooms[activeRoom].d.toFixed(2)} m · approximate` : "Click any room to step inside"}
            </div>
          </div>
          {mode === "room" && (
            <button onClick={backToOverview} data-testid="walkthrough-back"
              className="absolute top-5 right-5 flex items-center gap-2 h-10 px-4 bg-[var(--c-primary,#1f2937)] bg-neutral-900 text-white rounded-lg text-[13px] font-medium hover:opacity-90 transition-opacity">
              <ArrowLeft className="h-4 w-4" strokeWidth={1.75} /> Back to overview
            </button>
          )}
          {/* room pills */}
          {rooms.map((r, i) => (
            r.type === "hall" || r.type === "other" ? (
              <div key={i} ref={(el) => (pillRefs.current[i] = el)} style={{ position: "absolute", transform: "translate(-50%,-50%)" }}>
                <button onClick={() => enterRoom(i)} data-testid={`walkthrough-pill-${i}`}
                  className="flex items-center gap-1 bg-white/95 border border-border rounded-full px-2.5 py-1 text-[11.5px] font-medium shadow-sm hover:bg-white transition-colors">
                  {r.name} <ArrowUpRight className="h-3 w-3" strokeWidth={2} />
                </button>
              </div>
            ) : (
              <div key={i} ref={(el) => (pillRefs.current[i] = el)} style={{ position: "absolute", transform: "translate(-50%,-50%)" }}>
                <button onClick={() => enterRoom(i)} data-testid={`walkthrough-pill-${i}`}
                  className="flex items-center gap-1 bg-white/95 border border-border rounded-full px-3 py-1.5 text-[12px] font-medium shadow-sm hover:bg-white hover:scale-105 transition-all">
                  {r.name} <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </div>
            )
          ))}
        </div>
      </div>
    </div>
  );
}

function MiniPlan({ rooms, active, floorName, onPick }) {
  if (!rooms.length) return null;
  const maxx = Math.max(...rooms.map((r) => r.wx + r.w / 2)) + Math.max(...rooms.map((r) => r.w)) / 2;
  const W = Math.max(...rooms.map((r) => r.wx + r.w / 2)) - Math.min(...rooms.map((r) => r.wx - r.w / 2));
  const H = Math.max(...rooms.map((r) => r.wz + r.d / 2)) - Math.min(...rooms.map((r) => r.wz - r.d / 2));
  const minx = Math.min(...rooms.map((r) => r.wx - r.w / 2)), minz = Math.min(...rooms.map((r) => r.wz - r.d / 2));
  const s = 150 / Math.max(W, 0.1);
  const vw = W * s + 8, vh = H * s + 8;
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[12px] font-medium">{floorName}</span>
        <span className="text-[11px] text-muted-foreground">Click to enter</span>
      </div>
      <svg viewBox={`0 0 ${vw} ${vh}`} className="w-full border border-border rounded-md bg-white" data-testid="walkthrough-miniplan" style={{ fontFamily: "Georgia, serif" }}>
        {rooms.map((r, i) => {
          const x = (r.wx - r.w / 2 - minx) * s + 4, y = (r.wz - r.d / 2 - minz) * s + 4;
          const w = r.w * s, h = r.d * s;
          return (
            <g key={i} onClick={() => onPick(i)} style={{ cursor: "pointer" }}>
              <rect x={x} y={y} width={w} height={h} fill={active === i ? "#cfe3d6" : "#ffffff"} stroke="#9aa2ad" strokeWidth="1" />
              {r.type === "hall" && Array.from({ length: 6 }).map((_, k) => (
                <line key={k} x1={x + 3 + k * (w - 6) / 6} y1={y + 3} x2={x + 3 + k * (w - 6) / 6} y2={y + h - 3} stroke="#9aa2ad" strokeWidth="0.6" />
              ))}
              <text x={x + w / 2} y={y + h / 2 + 3} fontSize="8" textAnchor="middle" fill="#3b3b3b">{r.name}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
