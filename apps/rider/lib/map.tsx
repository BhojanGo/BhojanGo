// The dark route map, drawn (no map provider key): rider → pickup → drop-off,
// as on RiderOffer.html and RiderDropoff.html.
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { night } from "./theme";

type Pt = [number, number] | null | undefined;

export function RouteMap({ rider, pickup, dropoff, height, visible, done = false }: {
  rider: Pt; pickup: Pt; dropoff: Pt; height: number;
  /** How much of the map shows above the sheet: the route is fitted between the top pills and it. */
  visible?: number;
  /** After pickup: the leg to the restaurant is gone, the rider heads to the drop-off. */
  done?: boolean;
}) {
  const W = 390, H = height;
  const top = 128, bottom = Math.min(H, visible ?? H) - 28; // below the status pills
  const pts = [rider, pickup, dropoff].filter(Boolean) as [number, number][];
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  const [minLat, maxLat, minLng, maxLng] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const span = Math.max(maxLat - minLat, maxLng - minLng, 0.004);
  const xy = (p: Pt): [number, number] | null => {
    if (!p || pts.length === 0) return null;
    return [60 + ((p[1] - minLng) / span) * (W - 120), bottom - ((p[0] - minLat) / span) * Math.max(40, bottom - top)];
  };
  const r = xy(rider), a = xy(pickup), b = xy(dropoff);
  const curve = (p: [number, number], q: [number, number]) =>
    `M${p[0]} ${p[1]} C ${p[0] + (q[0] - p[0]) * 0.4} ${p[1] - 20}, ${q[0] - (q[0] - p[0]) * 0.4} ${q[1] + 20}, ${q[0]} ${q[1]}`;
  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" accessibilityLabel="Route map">
      <Rect width={W} height={H} fill={night.map} />
      <Path d={`M-10 ${H * 0.28} C 100 ${H * 0.22}, 220 ${H * 0.35}, 400 ${H * 0.25}`} stroke={night.road} strokeWidth={14} fill="none" />
      <Path d={`M-10 ${H * 0.65} C 140 ${H * 0.6}, 260 ${H * 0.75}, 400 ${H * 0.62}`} stroke={night.road} strokeWidth={14} fill="none" />
      <Path d={`M120 -10 C 140 ${H * 0.35}, 100 ${H * 0.65}, 130 ${H + 10}`} stroke={night.road} strokeWidth={10} fill="none" />
      <Path d={`M300 -10 C 280 ${H * 0.3}, 320 ${H * 0.7}, 300 ${H + 10}`} stroke={night.road} strokeWidth={10} fill="none" />
      {r && a && !done ? <Path d={curve(r, a)} stroke={night.link} strokeWidth={4} strokeLinecap="round" fill="none" /> : null}
      {a && b ? (
        <Path d={curve(done && r ? r : a, b)} stroke={done ? night.link : night.kesar} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={done ? undefined : "1 9"} fill="none" />
      ) : null}
      {r && !done ? <Circle cx={r[0]} cy={r[1]} r={8} fill={night.link} /> : null}
      {a ? <Circle cx={a[0]} cy={a[1]} r={11} fill={night.kesar} stroke={night.ground} strokeWidth={3} /> : null}
      {b ? <Rect x={b[0] - 10} y={b[1] - 10} width={20} height={20} rx={5} fill={night.text} /> : null}
    </Svg>
  );
}
