// "Rate this order" after delivery (the website's RateOrder): 1-5 stars and an
// optional comment -> POST /orders/{id}/rating. Once rated, "Your rating" is
// shown, with a change button until the API's editable_until (7 days).
import { Button, color, inZone, Input, textFont, useI18n } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";

import { getRating, rateOrder, type Order, type Rating } from "./account";
import { LinkButton, Section, Stars, ui } from "./account-ui";
import { Icon } from "./icons";

export function RateOrder({ order }: { order: Order }) {
  const { t, date } = useI18n();
  // The order says whether it's rated (newer API); otherwise ask.
  const known = order.rating && order.rating.stars ? order.rating : null;
  const [rating, setRating] = useState<Rating | null | undefined>(known ?? (order.rated === false ? null : undefined));
  const [editing, setEditing] = useState(false);
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (rating !== undefined) return;
    let live = true;
    getRating(order.id).then((r) => live && setRating(r)).catch(() => live && setRating(null));
    return () => {
      live = false;
    };
  }, [order.id, rating]);

  if (rating === undefined) return null;

  // The API says whether it can still be changed (7 days after rating).
  const editable = !!rating && rating.editable;

  if (rating && !editing) {
    return (
      <Section title={t("rating.your_rating")} testID="your-rating">
        <View accessible accessibilityLabel={t("rating.stars", { count: rating.stars })}>
          <Stars value={rating.stars} />
        </View>
        {rating.comment ? <Text testID="your-rating-comment" style={[ui.muted, { fontSize: 15 }]}>“{rating.comment}”</Text> : null}
        <Text style={ui.small}>{t("rating.thanks")}</Text>
        {editable ? (
          <>
            <Text style={ui.small}>{t("app.rating.until", { date: date(rating.editable_until, { weekday: "short", ...inZone(order.time_zone) }) })}</Text>
            <LinkButton testID="change-rating" title={t("app.rating.change")}
              onPress={() => { setStars(rating.stars); setComment(rating.comment ?? ""); setError(null); setEditing(true); }} />
          </>
        ) : null}
      </Section>
    );
  }

  async function submit() {
    if (!stars) return;
    setBusy(true);
    setError(null);
    try {
      setRating(await rateOrder(order.id, stars, comment));
      setEditing(false);
    } catch {
      setError(t("rating.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={t("rating.title")} note={t("rating.sub")} testID="rate-order">
      <View accessibilityRole="radiogroup" accessibilityLabel={t("rating.stars_label")} style={{ flexDirection: "row", gap: 4 }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <Pressable key={n} testID={`star-${n}`} accessibilityRole="radio" accessibilityState={{ checked: stars === n }}
            accessibilityLabel={t("rating.stars", { count: n })} onPress={() => setStars(n)} hitSlop={4}
            style={{ width: 48, height: 48, alignItems: "center", justifyContent: "center" }}>
            <Icon name="star" size={32} stroke={n <= stars ? color.kesar : color.lineStrong} fill={n <= stars ? color.kesar : "none"} />
          </Pressable>
        ))}
      </View>
      {stars > 0 ? (
        <>
          <Input testID="rating-comment" label={t("rating.comment")} placeholder={t("rating.comment_placeholder")} value={comment}
            onChangeText={setComment} maxLength={500} multiline />
          <Button testID="send-rating" title={busy ? t("rating.saving") : t("rating.submit")} loading={busy} onPress={submit} />
        </>
      ) : null}
      {editing ? <LinkButton title={t("common.cancel")} onPress={() => setEditing(false)} /> : null}
      {error ? <Text accessibilityRole="alert" style={[textFont("600"), { fontSize: 14, color: color.chili }]}>{error}</Text> : null}
    </Section>
  );
}
