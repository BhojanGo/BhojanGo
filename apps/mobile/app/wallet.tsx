import { useState } from "react";
import { FlatList, Pressable, Text, TextInput, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

interface WalletBalance { balance: number; currency: string; }
interface WalletTx { id: string; amount: number; type: "credit" | "debit"; description: string; created_at: string; }

export default function WalletScreen() {
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");

  const currencySymbol = user?.preferred_currency === "INR" ? "₹" : "$";
  const quickAmounts = user?.preferred_currency === "INR" ? [100, 200, 500, 1000] : [5, 10, 20, 50];

  const { data: balance } = useQuery<WalletBalance>({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/balance");
      return data;
    },
  });

  const { data: transactions } = useQuery<WalletTx[]>({
    queryKey: ["wallet-transactions"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/transactions?limit=20");
      return data;
    },
  });

  const topUpMutation = useMutation({
    mutationFn: async (amt: number) => {
      const { data } = await api.post("/payment/wallet/topup", {
        amount: amt,
        currency: balance?.currency ?? "USD",
        payment_method: "stripe",
      });
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["wallet-balance"] });
      void qc.invalidateQueries({ queryKey: ["wallet-transactions"] });
      setAmount("");
    },
  });

  return (
    <SafeAreaView className="flex-1 bg-gray-50">
      <FlatList
        data={transactions ?? []}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View className="px-4 pt-4">
            {/* Balance card */}
            <View className="bg-emerald-500 rounded-2xl p-6 mb-4">
              <Text className="text-emerald-100 text-sm">Available Balance</Text>
              <Text className="text-white text-4xl font-bold mt-1">
                {currencySymbol}{balance?.balance?.toFixed(2) ?? "0.00"}
              </Text>
            </View>

            {/* Top-up */}
            <View className="bg-white rounded-xl p-4 mb-4">
              <Text className="font-semibold text-gray-900 mb-3">Add Money</Text>
              <View className="flex-row flex-wrap gap-2 mb-3">
                {quickAmounts.map((amt) => (
                  <Pressable
                    key={amt}
                    onPress={() => setAmount(String(amt))}
                    className={`px-4 py-1.5 rounded-lg border ${
                      amount === String(amt) ? "border-emerald-500 bg-emerald-50" : "border-gray-300 bg-white"
                    }`}
                  >
                    <Text className={`text-sm font-medium ${amount === String(amt) ? "text-emerald-700" : "text-gray-700"}`}>
                      {currencySymbol}{amt}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <View className="flex-row gap-2">
                <View className="flex-1 flex-row items-center border border-gray-300 rounded-xl px-3">
                  <Text className="text-gray-500 mr-1">{currencySymbol}</Text>
                  <TextInput
                    value={amount}
                    onChangeText={setAmount}
                    keyboardType="numeric"
                    placeholder="0.00"
                    placeholderTextColor="#9ca3af"
                    className="flex-1 py-3 text-sm text-gray-900"
                  />
                </View>
                <Pressable
                  onPress={() => {
                    const amt = parseFloat(amount);
                    if (amt > 0) topUpMutation.mutate(amt);
                  }}
                  disabled={topUpMutation.isPending || !amount || parseFloat(amount) <= 0}
                  className="px-5 bg-emerald-500 rounded-xl items-center justify-center active:opacity-80 disabled:opacity-50"
                >
                  <Text className="text-white font-semibold">
                    {topUpMutation.isPending ? "..." : "Add"}
                  </Text>
                </Pressable>
              </View>
            </View>

            <Text className="font-semibold text-gray-900 mb-2">Transaction History</Text>
          </View>
        }
        contentContainerStyle={{ paddingBottom: 24 }}
        ListEmptyComponent={
          <View className="items-center py-8">
            <Text className="text-gray-400 text-sm">No transactions yet</Text>
          </View>
        }
        renderItem={({ item: tx }) => (
          <View className="bg-white mx-4 px-4 py-3 border-b border-gray-100 flex-row items-center justify-between">
            <View className="flex-row items-center gap-3">
              <View className={`w-9 h-9 rounded-full items-center justify-center ${
                tx.type === "credit" ? "bg-green-50" : "bg-red-50"
              }`}>
                <Text className={`text-base ${tx.type === "credit" ? "text-green-600" : "text-red-500"}`}>
                  {tx.type === "credit" ? "↓" : "↑"}
                </Text>
              </View>
              <View>
                <Text className="text-sm font-medium text-gray-900">{tx.description}</Text>
                <Text className="text-xs text-gray-400">
                  {new Date(tx.created_at).toLocaleDateString()}
                </Text>
              </View>
            </View>
            <Text className={`text-sm font-semibold ${tx.type === "credit" ? "text-green-600" : "text-red-500"}`}>
              {tx.type === "credit" ? "+" : "-"}{currencySymbol}{tx.amount.toFixed(2)}
            </Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}
