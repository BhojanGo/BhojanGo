// The live map on tracking, as the website's LiveMap: MapLibre (native) over
// OpenFreeMap's free vector tiles (no key, no account), © OpenStreetMap
// contributors shown on the map. Markers for the kitchen, home and the rider;
// the rider's trail drawn solid, a dashed line to the next stop. The rider
// marker moves on every location_update from the tracking socket.
//
// MapLibre is native code: an APK built before it was added (Metro + an older
// dev build) has no MLRN modules, and importing the package would throw. So it
// is loaded only when its native module is there; otherwise (or if the style
// can't load) the route is drawn on a plain ground as before.
import { color, textFont } from "@bhojango/mobile-core";
import { useMemo, useState } from "react";
import { Linking, Text, TurboModuleRegistry, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Circle, Path, Polyline, Rect } from "react-native-svg";

import { boundsOf, type Pt } from "../lib/contract";

type MapLibre = typeof import("@maplibre/maplibre-react-native");

const STYLE = "https://tiles.openfreemap.org/styles/liberty";
// The tiles' credits; OSM's own wording first (a legal notice, the same in every language).
const ATTRIBUTION = "© OpenStreetMap contributors · OpenMapTiles · OpenFreeMap";
const COPYRIGHT = "https://www.openstreetmap.org/copyright";

let loaded: MapLibre | null | undefined;
/** The MapLibre module, or null when this build has no MapLibre native code. */
export function mapLibre(): MapLibre | null {
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

export interface LiveMapProps {
  pickup: Pt | null;
  dropoff: Pt | null;
  rider: Pt | null;
  trail: Pt[];
  /** Where the rider goes next (the kitchen, then home); null when finished. */
  next: Pt | null;
  labels: { map: string; kitchen: string; home: string; rider: string };
  height: number;
  /** Room at the bottom covered by the sheet, so the markers stay in view. */
  coverBottom?: number;
  style?: StyleProp<ViewStyle>;
}

const ll = (p: Pt): [number, number] => [p[1], p[0]];

function line(points: Pt[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: points.length > 1 ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points.map(ll) } }] : [],
  };
}

export function LiveMap(props: LiveMapProps) {
  const ML = mapLibre();
  const [failed, setFailed] = useState(false);
  return (
    <View testID="track-map" accessibilityLabel={props.labels.map} style={[{ height: props.height, backgroundColor: color.mapGround }, props.style]}>
      {ML && !failed ? <NativeMap ML={ML} {...props} onFail={() => setFailed(true)} /> : <DrawnMap {...props} />}
    </View>
  );
}

function NativeMap({ ML, pickup, dropoff, rider, trail, next, labels, coverBottom = 0, onFail }: LiveMapProps & { ML: MapLibre; onFail: () => void }) {
  const { Map, Camera, GeoJSONSource, Layer, Marker } = ML;
  // Fit everything in view when the places change (not on every rider step, so panning isn't undone).
  const fitKey = JSON.stringify([pickup, dropoff, !!rider]);
  const [fit, setFit] = useState<{ key: string; bounds: [number, number, number, number] | null }>({ key: "", bounds: null });
  if (fit.key !== fitKey) setFit({ key: fitKey, bounds: boundsOf([pickup, dropoff, rider, ...trail]) });
  const bounds = fit.key === fitKey ? fit.bounds : boundsOf([pickup, dropoff, rider, ...trail]);
  const done = useMemo(() => line(pickup ? [pickup, ...trail] : trail), [pickup, trail]);
  const ahead = useMemo(() => line(next ? [rider ?? pickup, next].filter((p): p is Pt => !!p) : []), [next, rider, pickup]);
  const padding = { top: 72, right: 48, bottom: 48 + coverBottom, left: 48 };

  return (
    <View testID="live-map" style={{ flex: 1 }}>
      <Map
        style={{ flex: 1 }}
        mapStyle={STYLE}
        attribution={false}
        logo={false}
        compass={false}
        touchRotate={false}
        touchPitch={false}
        onDidFailLoadingMap={onFail}
      >
        <Camera
          {...(bounds ? { bounds, padding, duration: 600 } : { zoom: 1 })}
          maxZoom={16}
        />
        <GeoJSONSource id="done" data={done}>
          <Layer id="done" type="line" layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": color.peacock, "line-width": 5 }} />
        </GeoJSONSource>
        <GeoJSONSource id="ahead" data={ahead}>
          <Layer id="ahead" type="line" layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{ "line-color": color.peacockDeep, "line-width": 4, "line-dasharray": [1, 2] }} />
        </GeoJSONSource>
        {pickup ? (
          <Marker id="kitchen" lngLat={ll(pickup)} anchor="center">
            <View testID="map-kitchen" accessibilityLabel={labels.kitchen}><KitchenPin /></View>
          </Marker>
        ) : null}
        {dropoff ? (
          <Marker id="home" lngLat={ll(dropoff)} anchor="center">
            <View testID="map-home" accessibilityLabel={labels.home}><HomePin /></View>
          </Marker>
        ) : null}
        {rider ? (
          <Marker id="rider" lngLat={ll(rider)} anchor="center">
            <View testID="map-rider" accessibilityLabel={labels.rider}><RiderPin /></View>
          </Marker>
        ) : null}
      </Map>
      <Text
        testID="map-attribution"
        accessibilityRole="link"
        onPress={() => void Linking.openURL(COPYRIGHT)}
        style={[textFont("600"), {
          // top right: always on screen (the sheet below can cover more of the map than coverBottom)
          position: "absolute", right: 8, top: 8, maxWidth: "92%", fontSize: 9, color: color.kohl,
          backgroundColor: "rgba(255,255,255,0.85)", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: "hidden",
        }]}
      >
        {ATTRIBUTION}
      </Text>
    </View>
  );
}

function KitchenPin() {
  return (
    <Svg width={36} height={36} viewBox="-18 -18 36 36">
      <Circle r={16} fill={color.white} stroke={color.kohl} strokeWidth={3} />
      <Path d="M-5 -8v16M-8 -8v5a3 3 0 0 0 6 0v-5M5 -8c-3 2-3 7 0 9v7" stroke={color.kohl} strokeWidth={2.4} fill="none" strokeLinecap="round" />
    </Svg>
  );
}

function HomePin() {
  return (
    <Svg width={38} height={38} viewBox="-19 -19 38 38">
      <Circle r={17} fill={color.peacock} stroke={color.white} strokeWidth={3} />
      <Path d="M-8 1 0-7 8 1v8h-16z" fill={color.white} />
    </Svg>
  );
}

function RiderPin() {
  return (
    <Svg width={52} height={52} viewBox="-26 -26 52 52">
      <Circle r={24} fill={color.plate} fillOpacity={0.9} />
      <Circle r={14} fill={color.kesarBright} stroke={color.white} strokeWidth={3} />
    </Svg>
  );
}

/** No MapLibre in this build (or no tiles): the route drawn over a plain ground. */
function DrawnMap({ pickup, dropoff, rider, trail, next, labels, height }: LiveMapProps) {
  const pts = [pickup, dropoff, rider, ...trail].filter(Boolean) as Pt[];
  const W = 390, H = height, pad = 60;
  if (pts.length === 0) return <View testID="drawn-map" style={{ flex: 1 }} />;
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  const [minLat, maxLat, minLng, maxLng] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const span = Math.max(maxLat - minLat, maxLng - minLng, 0.004);
  const xy = (p: Pt): [number, number] => [pad + ((p[1] - minLng) / span) * (W - 2 * pad), H - pad - ((p[0] - minLat) / span) * (H - 2 * pad)];
  const from = rider ?? pickup;
  const done = pickup ? [pickup, ...trail] : trail;
  return (
    <Svg testID="drawn-map" width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
      <Rect width={W} height={H} fill={color.mapGround} />
      {[80, 160, 240, 320].map((y) => <Path key={y} d={`M0 ${y} H${W}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {[70, 190, 310].map((x) => <Path key={x} d={`M${x} 0 V${H}`} stroke="#DDE4E4" strokeWidth={10} />)}
      {from && next ? <Path d={`M${xy(from).join(" ")} L${xy(next).join(" ")}`} stroke={color.peacockDeep} strokeWidth={4} strokeDasharray="8 8" /> : null}
      {done.length > 1 ? <Polyline points={done.map((p) => xy(p).join(",")).join(" ")} fill="none" stroke={color.peacock} strokeWidth={5} strokeLinecap="round" /> : null}
      {pickup ? <Circle accessibilityLabel={labels.kitchen} cx={xy(pickup)[0]} cy={xy(pickup)[1]} r={10} fill={color.kohl} /> : null}
      {dropoff ? <Circle accessibilityLabel={labels.home} cx={xy(dropoff)[0]} cy={xy(dropoff)[1]} r={10} fill={color.peacock} stroke={color.white} strokeWidth={3} /> : null}
      {rider ? <Circle accessibilityLabel={labels.rider} cx={xy(rider)[0]} cy={xy(rider)[1]} r={12} fill={color.kesar} stroke={color.white} strokeWidth={4} /> : null}
    </Svg>
  );
}
