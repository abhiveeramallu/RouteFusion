import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useRouteFusion } from "../context/RouteFusionContext";
import type { UserRole } from "../types";
import { PanelCard } from "./PanelCard";
import { PanelHeader } from "./PanelHeader";

function inputClassName() {
  return "w-full rounded-2xl border border-[#dbe1e7] bg-[#f9fafb] px-4 py-3 text-sm text-[#111827] outline-none transition placeholder:text-[#9ca3af] focus:border-[#111111] focus:bg-white";
}

function nextRouteForRole(role: UserRole) {
  if (role === "captain") {
    return "/captain";
  }
  if (role === "operator" || role === "admin") {
    return "/dashboard";
  }
  return "/ride";
}

export function AuthPanel() {
  const navigate = useNavigate();
  const { login, refreshing } = useRouteFusion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const user = await login({ email, password });
    navigate(nextRouteForRole(user.role));
  }

  return (
    <div className="space-y-6 p-6">
      <PanelHeader
        eyebrow="Account Access"
        title="Sign in to RouteFusion"
        description="Use your RouteFusion account to continue into the ride, parcel, and captain workflow."
      />

      <PanelCard className="space-y-6">
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            void handleSubmit(event).catch(() => undefined);
          }}
        >
          <label className="grid gap-2">
            <span className="text-sm font-medium text-[#4b5563]">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClassName()}
              placeholder="name@example.com"
            />
          </label>

          <label className="grid gap-2">
            <span className="text-sm font-medium text-[#4b5563]">Password</span>
            <input
              required
              minLength={8}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClassName()}
              placeholder="At least 8 characters"
            />
          </label>

          <button
            type="submit"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-[#111111] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#000000]"
          >
            <ArrowRight className="h-4 w-4" />
            {refreshing ? "Working..." : "Sign In"}
          </button>
        </form>
      </PanelCard>
    </div>
  );
}
