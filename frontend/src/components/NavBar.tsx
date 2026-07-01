import {
  BarChart3,
  Box,
  Car,
  Home,
  Map,
  ShieldCheck,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Home", icon: Home },
  { to: "/parcel", label: "Parcel Request", icon: Box },
  { to: "/ride", label: "Ride Request", icon: Car },
  { to: "/captain", label: "Captain Corner", icon: ShieldCheck },
  { to: "/map", label: "Live Map", icon: Map },
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
];

export function NavBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/75 backdrop-blur-2xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-4">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-primary via-accent to-secondary text-sm font-bold text-white shadow-glow">
            RF
          </div>
          <div>
            <p className="font-display text-xl font-semibold text-white">RouteFusion</p>
            <p className="text-sm text-slate-400">Smartly combining people and parcels</p>
          </div>
        </div>
        <nav className="flex flex-wrap gap-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${
                  isActive
                    ? "border-primary/50 bg-primary/20 text-white"
                    : "border-white/10 bg-white/5 text-slate-300 hover:border-accent/40 hover:text-white"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
