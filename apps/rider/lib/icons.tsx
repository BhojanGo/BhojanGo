// Stroke icons as drawn on the design board (24 px grid).
import Svg, { Circle, Path } from "react-native-svg";

import { night } from "./theme";

const PATHS = {
  back: "M15 5l-7 7 7 7",
  check: "m5 12 5 5 9-10",
  chevronRight: "m9 6 6 6-6 6",
  chevronDown: "m6 9 6 6 6-6",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2",
  navigate: "m3 11 18-8-8 18-2-8z",
  message: "M4 5h16v11H8l-4 4z",
  camera: "M4 8h3l2-3h6l2 3h3v11H4z",
  shield: "M12 3 4 6v6c0 4.5 3.5 8 8 9 4.5-1 8-4.5 8-9V6zM9 12l2 2 4-4",
  drive: "M5 17h14M6 17l1.5-6h9L18 17M8 11l1-4h6l1 4M7 20a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM17 20a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  wallet: "M4 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4zM4 7l11-3v3M16 13.5h.01",
  account: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  bag: "M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2",
  document: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  alert: "M12 8v5M12 17h.01M10.3 3.9L2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  close: "M6 6l12 12M18 6 6 18",
  bank: "M3 10h18L12 4zM5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22, stroke = night.text, width = 2 }: { name: IconName; size?: number; stroke?: string; width?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round">
      <Path d={PATHS[name]} />
      {name === "camera" ? <Circle cx={12} cy={13} r={3.5} /> : null}
    </Svg>
  );
}

/** The BhojanGo mark in the rider colours (header of the onboarding screen). */
export function RiderMark({ size = 28 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 40 40" accessibilityLabel="BhojanGo">
      <Path d="M11 5.5v24" stroke={night.link} strokeWidth={5} strokeLinecap="round" fill="none" />
      <Circle cx={20.5} cy={25} r={8.5} fill="none" stroke={night.link} strokeWidth={5} />
      <Path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke={night.kesar} strokeWidth={2.2} strokeLinecap="round" fill="none" />
    </Svg>
  );
}
