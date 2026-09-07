import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { HomeWalkthrough } from "@/components/HomeWalkthrough";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function PublicWalkthrough() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/public/walkthrough/${token}`)
      .then((r) => { if (!r.ok) throw new Error("gone"); return r.json(); })
      .then(setData)
      .catch(() => setErr(true));
  }, [token]);

  if (err) return <div className="min-h-screen flex items-center justify-center text-muted-foreground" data-testid="public-walkthrough-error">This walkthrough link is no longer available.</div>;
  if (!data) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Loading walkthrough…</div>;

  return (
    <HomeWalkthrough
      cadData={data.cadData}
      roomPhotosData={data.roomPhotos}
      pinSpecsData={data.pinSpecs}
      readOnly
      title={data.name}
      onClose={() => navigate("/")}
    />
  );
}
