import { Redirect } from "expo-router";

// "/" used to be the customer home tab; in the rider app it is the rider home
// tab, whose layout sends signed-out users to the login screen.
export default function Index() {
  return <Redirect href="/(driver-tabs)/home" />;
}
