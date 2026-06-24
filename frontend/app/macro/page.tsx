import { Suspense } from "react";
import { MacroTabShell } from "@/components/macro/MacroTabShell";

export default function MacroPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold">Macro Intelligence</h1>
      <Suspense>
        <MacroTabShell />
      </Suspense>
    </div>
  );
}
