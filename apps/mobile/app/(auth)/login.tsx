import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function LoginScreen() {
  const { setTokens, setUser } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) { setError("Please fill all fields."); return; }
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/user/auth/login", { email, password });
      await setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      // Route based on user role
      if (data.user.role === "driver") {
        router.replace("/(driver-tabs)/home");
      } else {
        router.replace("/(tabs)");
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Invalid email or password";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-white">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1"
      >
        <ScrollView contentContainerStyle={{ flexGrow: 1, padding: 24 }}>
          <View className="flex-1 justify-center">
            <Text className="text-3xl font-bold text-emerald-500 mb-1">BhojanGo</Text>
            <Text className="text-2xl font-semibold text-gray-900 mb-1">Welcome back</Text>
            <Text className="text-gray-500 mb-8">Sign in to your account</Text>

            <View className="mb-4">
              <Text className="text-sm font-medium text-gray-700 mb-1">Email</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="you@example.com"
                placeholderTextColor="#9ca3af"
                keyboardType="email-address"
                autoCapitalize="none"
                autoComplete="email"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 text-gray-900 text-sm"
              />
            </View>

            <View className="mb-6">
              <Text className="text-sm font-medium text-gray-700 mb-1">Password</Text>
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                placeholderTextColor="#9ca3af"
                secureTextEntry
                autoComplete="password"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 text-gray-900 text-sm"
              />
            </View>

            {error ? (
              <View className="bg-red-50 rounded-xl px-4 py-3 mb-4">
                <Text className="text-red-600 text-sm">{error}</Text>
              </View>
            ) : null}

            <Pressable
              onPress={handleLogin}
              disabled={loading}
              className="w-full py-3.5 bg-emerald-500 rounded-xl items-center mb-4 active:opacity-80"
            >
              <Text className="text-white font-semibold text-base">
                {loading ? "Signing in..." : "Sign In"}
              </Text>
            </Pressable>

            <View className="flex-row justify-center gap-1">
              <Text className="text-gray-500 text-sm">Don't have an account?</Text>
              <Pressable onPress={() => router.push("/(auth)/signup")}>
                <Text className="text-emerald-500 font-semibold text-sm">Sign Up</Text>
              </Pressable>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
