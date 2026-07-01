import {
  BarChart3,
  Box,
  CarFront,
  Home,
  ShieldCheck,
  UserCircle2,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import routeFusionLogoPng from "../../routefusion-logo.png";
import routeFusionLogoWebp from "../../routefusion-logo.webp";

const navItems = [
  { to: "/", label: "Home", icon: Home },
  { to: "/ride", label: "Ride Request", icon: CarFront },
  { to: "/parcel", label: "Parcel Request", icon: Box },
  { to: "/captain", label: "Captain Corner", icon: ShieldCheck },
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/profile", label: "Profile", icon: UserCircle2 },
];

export function TopNav() {
  return (
    <header className="border-b border-[#e7eaee] bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:px-8">
        <div className="flex items-center">
          <picture>
            <source srcSet={routeFusionLogoWebp} type="image/webp" />
            <img
              src={routeFusionLogoPng}
              alt="RouteFusion"
              width={200}
              height={133}
              loading="eager"
              decoding="async"
              className="h-16 w-auto object-contain"
            />
          </picture>
        </div>

        <nav className="flex flex-wrap items-center justify-center gap-2 lg:flex-1 lg:px-4">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex items-center gap-2 rounded-full px-3 py-2.5 text-sm font-medium transition xl:px-4 ${
                  isActive
                    ? "bg-[#111111] text-white"
                    : "bg-[#f3f4f6] text-[#4b5563] hover:bg-[#e5e7eb] hover:text-[#111827]"
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
