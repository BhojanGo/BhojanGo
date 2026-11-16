// The map on Drive and on a delivery (R8): a real map, the same as the customer
// app's tracking map (MapLibre over OpenFreeMap's free vector tiles, no key, no
// account), in OpenFreeMap's dark style to match the app. The delivery partner's
// position, the kitchen and the drop-off, the leg to the kitchen solid and the
// leg on to the drop-off dashed (after pickup: the partner to the drop-off). With
// no stops it is centred on the partner's position when known, else on the city
// (Markets' centre). © OpenStreetMap contributors shown just above the sheet.
//
// MapLibre is native code: an APK built before it was added has no MLRN modules,
// and importing the package would throw. Then (or if the style can't load) the
// route is drawn on a plain dark ground, with no made-up streets.
import { useMemo, useState } from "react";
import { Linking, Text, TurboModuleRegistry, View } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { night, ui } from "./theme";

type Pt = [number, number] | null | undefined; // [lat, lng]
type MapLibre = typeof import("@maplibre/maplibre-react-native");

const STYLE = "https://tiles.openfreemap.org/styles/dark";
// The tiles' credits; OSM's own wording first (a legal notice, the same in every language).
const ATTRIBUTION = "© OpenStreetMap contributors · OpenMapTiles · OpenFreeMap";
const COPYRIGHT = "https://www.openstreetmap.org/copyright";
const TOP = 128; // the status pills over the map

let loaded: MapLibre | null | undefined;
/** The MapLibre module, or null when this build has no MapLibre native code. */
function mapLibre(): MapLibre | null {
  if (loaded !== undefined) return loaded;
  try {
    loaded = TurboModuleRegistry.get("MLRNMapViewModule")
      ? // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded only when the native module exists
        (require("@maplibre/maplibre-react-native") as MapLibre)
      : null;
  } catch {
    loaded = null;
  }
  return loaded;
}

const ll = (p: [number, number]): [number, number] => [p[1], p[0]];
const ok = (p: Pt): p is [number, number] => !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]);

function line(points: Pt[]): GeoJSON.FeatureCollection {
  const pts = points.filter(ok);
  return {
    type: "FeatureCollection",
    features: pts.length > 1 ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: pts.map(ll) } }] : [],
  };
}

interface Props {
  rider: Pt; pickup: Pt; dropoff: Pt; height: number;
  /** The accessibility label, in the rider's language (rider.map.label). */
  label: string;
  /** How much of the map shows above the sheet: the route is fitted between the top pills and it. */
  visible?: number;
  /** After pickup: the leg to the restaurant is gone, the rider heads to the drop-off. */
  done?: boolean;
  /** Where to look with no position and no stops: the partner's city (Markets' centre). */
  center?: Pt;
}

export function RouteMap(props: Props) {
  const ML = mapLibre();
  const [failed, setFailed] = useState(false);
  return (
    <View testID="route-map" accessibilityLabel={props.label} style={{ height: props.height, backgroundColor: night.map }}>
      {ML && !failed ? <NativeMap ML={ML} {...props} onFail={() => setFailed(true)} /> : <DrawnMap {...props} />}
    </View>
  );
}

function NativeMap({ ML, rider, pickup, dropoff, height, visible, done = false, center, onFail }: Props & { ML: MapLibre; onFail: () => void }) {
  const { Map, Camera, GeoJSONSource, Layer, Marker } = ML;
  const covered = height - Math.min(height, visible ?? height); // under the sheet
  const toKitchen = useMemo(() => line(!done ? [rider, pickup] : []), [done, rider, pickup]);
  const onward = useMemo(() => line(done ? [rider, dropoff] : [pickup, dropoff]), [done, rider, pickup, dropoff]);
  const stops = [done ? null : pickup, dropoff].filter(ok);
  const pts = [rider, ...stops].filter(ok);
  // Fit the stops (and the partner) when there are stops; else follow the partner, else the city.
  const me = ok(rider) ? rider : null;
  const city = ok(center) ? center : null;
  const camera = cameraFor(stops.length ? bounds(pts) : null, me, city, covered);
  return (
    <View style={{ flex: 1 }}>
      <Map style={{ flex: 1 }} mapStyle={STYLE} attribution={false} logo={false} compass={false} touchRotate={false} touchPitch={false}
        onDidFailLoadingMap={onFail}>
        <Camera {...camera} maxZoom={16} />
        <GeoJSONSource id="to-kitchen" data={toKitchen}>
          <Layer id="to-kitchen" type="line" layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": night.link, "line-width": 5 }} />
        </GeoJSONSource>
        <GeoJSONSource id="onward" data={onward}>
          <Layer id="onward" type="line" layout={{ "line-cap": "round", "line-join": "round" }}
            paint={done ? { "line-color": night.link, "line-width": 5 } : { "line-color": night.kesar, "line-width": 4, "line-dasharray": [1, 2] }} />
        </GeoJSONSource>
        {ok(pickup) && !done ? (
          <Marker id="pickup" lngLat={ll(pickup)} anchor="center">
            <View testID="map-pickup"><Pin kind="pickup" /></View>
          </Marker>
        ) : null}
        {ok(dropoff) ? (
          <Marker id="dropoff" lngLat={ll(dropoff)} anchor="center">
            <View testID="map-dropoff"><Pin kind="dropoff" /></View>
          </Marker>
        ) : null}
        {ok(rider) ? (
          <Marker id="me" lngLat={ll(rider)} anchor="center">
            <View testID="map-me"><Pin kind="me" /></View>
          </Marker>
        ) : null}
      </Map>
      <Text
        testID="map-attribution"
        accessibilityRole="link"
        onPress={() => void Linking.openURL(COPYRIGHT)}
        style={[ui.muted, {
          position: "absolute", right: 16, bottom: covered + 8, maxWidth: "80%", textAlign: "right",
          color: night.muted, backgroundColor: "rgba(15, 27, 29, 0.8)", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: "hidden",
        }]}
      >
        {ATTRIBUTION}
      </Text>
    </View>
  );
}

function cameraFor(fit: [number, number, number, number] | null, me: [number, number] | null, city: [number, number] | null, covered: number) {
  const padding = { top: TOP, right: 0, bottom: covered, left: 0 };
  if (fit) return { bounds: fit, padding: { top: TOP, right: 48, bottom: covered + 48, left: 48 }, duration: 600 };
  if (me) return { center: ll(me), zoom: 14.5, padding, duration: 600 };
  if (city) return { center: ll(city), zoom: 11.5, padding, duration: 0 };
  return { zoom: 1 };
}

function bounds(pts: [number, number][]): [number, number, number, number] {
  const pad = 0.002;
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  return [Math.min(...lngs) - pad, Math.min(...lats) - pad, Math.max(...lngs) + pad, Math.max(...lats) + pad];
}

function Pin({ kind }: { kind: "me" | "pickup" | "dropoff" }) {
  if (kind === "me") {
    return (
      <Svg width={40} height={40} viewBox="-20 -20 40 40">
        <Circle r={18} fill={night.link} fillOpacity={0.25} />
        <Circle r={9} fill={night.link} stroke={night.ground} strokeWidth={3} />
      </Svg>
    );
  }
  return kind === "pickup" ? (
    <Svg width={28} height={28} viewBox="-14 -14 28 28"><Circle r={11} fill={night.kesar} stroke={night.ground} strokeWidth={3} /></Svg>
  ) : (
    <Svg width={28} height={28} viewBox="-14 -14 28 28"><Rect x={-10} y={-10} width={20} height={20} rx={5} fill={night.text} stroke={night.ground} strokeWidth={2} /></Svg>
  );
}

/** No MapLibre in this build (or no tiles): the route drawn on a plain dark ground. */
function DrawnMap({ rider, pickup, dropoff, height, visible, done = false, label }: Props) {
  const W = 390, H = height;
  const bottom = Math.min(H, visible ?? H) - 28;
  const pts = [rider, pickup, dropoff].filter(ok);
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  const [minLat, maxLat, minLng, maxLng] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const span = Math.max(maxLat - minLat, maxLng - minLng, 0.004);
  const xy = (p: Pt): [number, number] | null => {
    if (!ok(p)) return null;
    return [60 + ((p[1] - minLng) / span) * (W - 120), bottom - ((p[0] - minLat) / span) * Math.max(40, bottom - TOP)];
  };
  const r = xy(rider), a = xy(pickup), b = xy(dropoff);
  const seg = (p: [number, number], q: [number, number]) => `M${p[0]} ${p[1]} L${q[0]} ${q[1]}`;
  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" accessibilityLabel={label}>
      <Rect width={W} height={H} fill={night.map} />
      {r && a && !done ? <Path d={seg(r, a)} stroke={night.link} strokeWidth={4} strokeLinecap="round" fill="none" /> : null}
      {a && b ? (
        <Path d={seg(done && r ? r : a, b)} stroke={done ? night.link : night.kesar} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={done ? undefined : "1 9"} fill="none" />
      ) : null}
      {r ? <Circle cx={r[0]} cy={r[1]} r={8} fill={night.link} /> : null}
      {a ? <Circle cx={a[0]} cy={a[1]} r={11} fill={night.kesar} stroke={night.ground} strokeWidth={3} /> : null}
      {b ? <Rect x={b[0] - 10} y={b[1] - 10} width={20} height={20} rx={5} fill={night.text} /> : null}
    </Svg>
  );
}
