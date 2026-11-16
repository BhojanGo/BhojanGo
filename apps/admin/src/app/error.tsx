"use client";
// Something broke while showing a console page (R8): plain words and a way on,
// never the error itself (it goes to the browser console).
import { useEffect } from "react";

import { ConsoleMessage } from "@/components/console/ConsoleMessage";

export default function ConsoleError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <ConsoleMessage title="Something went wrong on our side" body="The page couldn't load. Try again; if it keeps happening, the API may be down or deploying.">
      <button type="button" onClick={reset} className="inline-flex min-h-11 items-center rounded-full border border-line bg-white px-5 text-label text-kohl hover:border-peacock">
        Try again
      </button>
    </ConsoleMessage>
  );
}
