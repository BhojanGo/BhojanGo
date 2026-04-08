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

export default function SignupScreen() {
  const { setTokens, setUser } = useAuthStore();

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
    country: "US" as "US" | "IN",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleChange(field: keyof typeof form) {
    return (value: string) => setForm({ ...form, [field]: value });
  }

  async function handleSignup() {
    if (!form.full_name || !form.email || !form.password) {
      setError("Please fill all fields.");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/user/auth/register", {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || undefined,
        password: form.password,
        country: form.country,
        preferred_currency: form.country === "IN" ? "INR" : "USD",
        preferred_locale: form.country === "IN" ? "en-IN" : "en-US",
      });
      await setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      router.replace("/(tabs)");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Registration failed. Please try again.";
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
            <Text className="text-2xl font-semibold text-gray-900 mb-1">Create account</Text>
            <Text className="text-gray-500 mb-8">Join BhojanGo today</Text>

            {[
              { field: "full_name" as const, label: "Full Name", placeholder: "Jane Doe", type: "default" },
              { field: "email" as const, label: "Email", placeholder: "you@example.com", type: "email-address" },
              { field: "phone" as const, label: "Phone (optional)", placeholder: "+14155551234", type: "phone-pad" },
              { field: "password" as const, label: "Password", placeholder: "Min. 8 characters", type: "default", secure: true },
              { field: "confirmPassword" as const, label: "Confirm Password", placeholder: "••••••••", type: "default", secure: true },
            ].map(({ field, label, placeholder, type, secure }) => (
              <View key={field} className="mb-4">
                <Text className="text-sm font-medium text-gray-700 mb-1">{label}</Text>
                <TextInput
                  value={form[field]}
                  onChangeText={handleChange(field)}
                  placeholder={placeholder}
                  placeholderTextColor="#9ca3af"
                  keyboardType={type as "default" | "email-address" | "phone-pad"}
                  autoCapitalize={field === "email" || field === "phone" ? "none" : "words"}
                  secureTextEntry={secure}
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 text-gray-900 text-sm"
                />
              </View>
            ))}

            {/* Country selector */}
            <View className="mb-4">
              <Text className="text-sm font-medium text-gray-700 mb-1">Country</Text>
              <View className="flex-row gap-3">
                {([["US", "United States"], ["IN", "India"]] as const).map(([code, name]) => (
                  <Pressable
                    key={code}
                    onPress={() => setForm({ ...form, country: code })}
                    className={`flex-1 py-3 rounded-xl items-center border ${
                      form.country === code
                        ? "border-emerald-500 bg-emerald-50"
                        : "border-gray-300 bg-white"
                    }`}
                  >
                    <Text className={`text-sm font-medium ${form.country === code ? "text-emerald-700" : "text-gray-600"}`}>
                      {name}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>

            {error ? (
              <View className="bg-red-50 rounded-xl px-4 py-3 mb-4">
                <Text className="text-red-600 text-sm">{error}</Text>
              </View>
            ) : null}

            <Pressable
              onPress={handleSignup}
              disabled={loading}
              className="w-full py-3.5 bg-emerald-500 rounded-xl items-center mb-4 active:opacity-80"
            >
              <Text className="text-white font-semibold text-base">
                {loading ? "Creating account..." : "Sign Up"}
              </Text>
            </Pressable>

            <View className="flex-row justify-center gap-1">
              <Text className="text-gray-500 text-sm">Already have an account?</Text>
              <Pressable onPress={() => router.push("/(auth)/login")}>
                <Text className="text-emerald-500 font-semibold text-sm">Sign In</Text>
              </Pressable>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
