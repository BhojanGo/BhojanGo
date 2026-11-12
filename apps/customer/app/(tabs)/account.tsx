// Account: who you are, sign out, delete your account (with a confirmation).
import { Button, Card, color, errorMessage, Sheet, space, textFont, Txt, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTabBarSpace } from "../../lib/tabbar";

export default function Account() {
  const bottom = useTabBarSpace();
  const { user, signOut, deleteAccount } = useSession();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      router.replace("/sign-in");
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4], paddingBottom: bottom }}>
        <Txt variant="h1" accessibilityRole="header">Account</Txt>
        <Card style={{ gap: 4 }}>
          <Txt variant="title">{user?.full_name}</Txt>
          <Text style={[textFont("400"), { color: color.muted }]}>{user?.phone ?? user?.email}</Text>
        </Card>
        <Button title="Sign out" variant="secondary" block onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
        <View style={{ marginTop: space[8], gap: space[2] }}>
          <Txt variant="label">Delete account</Txt>
          <Txt variant="small" style={{ color: color.muted }}>
            Removes your name, phone, email and addresses. Past orders are kept without your details.
          </Txt>
          <Button title="Delete my account" variant="danger" onPress={() => setConfirm(true)} />
        </View>
      </ScrollView>
      <Sheet visible={confirm} onClose={() => setConfirm(false)} title="Delete your account?"
        footer={
          <View style={{ gap: space[2] }}>
            <Button title="Yes, delete it" variant="danger" size="lg" block loading={busy} onPress={remove} />
            <Button title="Keep my account" variant="secondary" block onPress={() => setConfirm(false)} />
          </View>
        }>
        <Txt style={{ color: color.muted }}>You&apos;ll be signed out on every device. This can&apos;t be undone.</Txt>
        {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      </Sheet>
    </SafeAreaView>
  );
}
