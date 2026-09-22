// Group survey photos into logical areas from their caption. Order matters — the first
// matching bucket wins. Anything that doesn't clearly match lands in "Other / unsorted"
// rather than being mis-filed, since photopack captions vary.
export const PHOTO_GROUPS = [
  { key: "external", label: "External & elevations", kw: [/elevation/, /external/, /\bfront\b/, /\brear\b/, /\bside\b/, /garden/, /\bdpc\b/, /cavity/, /wall thickness/, /render/, /brick/] },
  { key: "loft", label: "Loft & roof", kw: [/loft/, /\broof\b/, /attic/, /rafter/, /eaves/, /ridge/] },
  { key: "kitchen", label: "Kitchen", kw: [/kitchen/] },
  { key: "bath", label: "Bathroom & WC", kw: [/bath/, /\bwc\b/, /shower/, /toilet/, /en.?suite/] },
  { key: "bed", label: "Bedrooms", kw: [/bed\s?room/, /\bbed\s?\d/, /\bbed\b/] },
  { key: "living", label: "Living & reception", kw: [/living/, /lounge/, /reception/, /dining/, /sitting/] },
  { key: "hall", label: "Hall, stairs & landing", kw: [/hall/, /stair/, /landing/] },
  { key: "floor", label: "Floors", kw: [/\bfloor/] },
  { key: "windows", label: "Windows & doors", kw: [/window/, /\bdoor/, /glazing/, /undercut/] },
  { key: "services", label: "Meters, heating & services", kw: [/meter/, /boiler/, /heating/, /cylinder/, /thermostat/, /control/, /\bgas\b/, /electric/, /fan/, /extractor/] },
  { key: "damp", label: "Damp, mould & condensation", kw: [/mould/, /mold/, /damp/, /condensation/, /penetrat/] },
];

export function buildPhotoGroups(photos) {
  const map = new Map();
  photos.forEach((ph, pi) => {
    const cap = (ph.caption || "").toLowerCase();
    const grp = PHOTO_GROUPS.find((g) => g.kw.some((re) => re.test(cap)));
    const key = grp ? grp.key : "other";
    const label = grp ? grp.label : "Other / unsorted";
    if (!map.has(key)) map.set(key, { key, label, items: [] });
    map.get(key).items.push({ ph, pi });
  });
  const order = [...PHOTO_GROUPS.map((g) => g.key), "other"];
  return order.filter((k) => map.has(k)).map((k) => map.get(k));
}
