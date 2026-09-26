import type { ReactNode } from "react";
import { ToastProvider } from "@/providers/ToastProvider";
import { Toaster } from "@/components/ui";

/**
 * The signed-out half: a centred card on the brand colour, as in the mockup.
 *
 * No navigation and no live feed here, because there is no session to authenticate
 * either of them.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <div className="flex min-h-screen flex-col items-center justify-center bg-linear-to-br from-brand-700 via-brand-600 to-brand-800 px-4 py-10">
        <div className="mb-6 flex items-center gap-2.5 text-white">
          <span
            aria-hidden
            className="grid h-10 w-10 place-items-center rounded-lg bg-white/20 text-lg font-bold"
          >
            S
          </span>
          <div>
            <p className="text-xl font-semibold tracking-tight">StockSense</p>
            <p className="text-xs text-white/70">Inventory management</p>
          </div>
        </div>

        <div className="w-full max-w-md rounded-lg bg-sheet p-6 shadow-xl sm:p-8">{children}</div>

        <p className="mt-6 text-xs text-white/60">
          Every stock change is recorded as a move between two locations.
        </p>
      </div>
      <Toaster />
    </ToastProvider>
  );
}
