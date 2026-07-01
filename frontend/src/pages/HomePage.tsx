import {
  ArrowRight,
  BarChart3,
  CarFront,
  CheckCircle2,
  Fuel,
  Network,
  Package,
  Route,
  Sparkles,
  Truck,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import mainImagePng from "../../mainimage-hero.png";
import mainImageWebp from "../../mainimage-hero.webp";


/* ─── colour palette ─── */
const C = {
  ink: "#111111",
  accent: "#000000",
  accentLight: "#000000",
  bg: "#F8F9FA",
  surface: "#FFFFFF",
  muted: "#6b7280",
  border: "#E7EAEE",
  success: "#22C55E",
};

/* ─── Stats ─── */
const stats = [
  { value: "38%", label: "Cost Reduction", icon: BarChart3 },
  { value: "2.4×", label: "Driver Utilization", icon: Truck },
  { value: "61%", label: "Less Fuel Burned", icon: Fuel },
  { value: "<90s", label: "Match Latency", icon: Zap },
];

/* ─── Benefits ─── */
const benefits = [
  {
    icon: Sparkles,
    title: "Reduced Transportation Cost",
    description:
      "One optimized trip lowers the cost of moving both people and parcels by sharing fixed overhead.",
    color: "#5B5BEF",
  },
  {
    icon: Fuel,
    title: "Reduced Fuel Consumption",
    description:
      "Fewer duplicate trips means significantly less fuel burned across the entire network.",
    color: "#22C55E",
  },
  {
    icon: Truck,
    title: "Better Driver Utilization",
    description:
      "Captains spend more time on productive routes instead of empty repositioning.",
    color: "#F59E0B",
  },
  {
    icon: Package,
    title: "Faster Parcel Delivery",
    description:
      "Parcel demand piggybacks on active passenger movement when routes overlap.",
    color: "#EC4899",
  },
  {
    icon: Route,
    title: "Reduced Traffic Congestion",
    description:
      "Smarter bundling reduces unnecessary vehicles competing on the same corridor.",
    color: "#06B6D4",
  },
  {
    icon: Network,
    title: "Intelligent Route Matching",
    description:
      "AI-powered engine evaluates thousands of combinations in milliseconds for optimal pairing.",
    color: "#8B5CF6",
  },
];

/* ─── Animated counter hook ─── */
function useCountUp(target: string, duration = 1800, start = false) {
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    if (!start) return;
    const num = parseFloat(target.replace(/[^0-9.]/g, ""));
    const suffix = target.replace(/[0-9.]/g, "");
    let raf: number;
    const startTime = performance.now();
    function tick(now: number) {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = (num * eased).toFixed(target.includes(".") ? 1 : 0);
      setDisplay(current + suffix);
      if (progress < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [start, target, duration]);
  return display;
}

/* ─── Stat card ─── */
function StatCard({
  value,
  label,
  icon: Icon,
  visible,
}: {
  value: string;
  label: string;
  icon: React.ElementType;
  visible: boolean;
}) {
  const display = useCountUp(value, 1600, visible);
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 24,
        padding: "28px 24px",
        boxShadow: "0 8px 32px rgba(15,23,42,0.06)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        transition: "transform 0.2s, box-shadow 0.2s",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.transform = "translateY(-4px)";
        el.style.boxShadow = "0 20px 48px rgba(91,91,239,0.14)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.transform = "translateY(0)";
        el.style.boxShadow = "0 8px 32px rgba(15,23,42,0.06)";
      }}
    >
      <div
        style={{
          background: "rgba(91,91,239,0.08)",
          borderRadius: 14,
          padding: 10,
        }}
      >
        <Icon size={20} color={C.accent} />
      </div>
      <span
        style={{
          fontSize: 36,
          fontWeight: 800,
          color: C.ink,
          letterSpacing: "-0.04em",
          lineHeight: 1,
        }}
      >
        {display}
      </span>
      <span
        style={{
          fontSize: 12,
          color: C.muted,
          fontWeight: 600,
          textAlign: "center",
        }}
      >
        {label}
      </span>
    </div>
  );
}

function HeroIllustration() {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        minHeight: 360,
        borderRadius: 28,
        overflow: "hidden",
      }}
    >
      <picture>
        <source srcSet={mainImageWebp} type="image/webp" />
        <img
          src={mainImagePng}
          alt="RouteFusion hero illustration"
          loading="lazy"
          decoding="async"
          width={1440}
          height={960}
          sizes="(min-width: 1280px) 720px, (min-width: 768px) 50vw, 100vw"
          style={{
            width: "100%",
            height: "100%",
            minHeight: 360,
            display: "block",
            objectFit: "cover",
            objectPosition: "center",
          }}
        />
      </picture>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0) 55%, rgba(91,91,239,0.04) 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

/* ─── Main HomePage ─── */
export function HomePage() {
  const statsRef = useRef<HTMLDivElement>(null);
  const [statsVisible, setStatsVisible] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);
  const [heroVisible, setHeroVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.target === statsRef.current && e.isIntersecting) {
            setStatsVisible(true);
          }
          if (e.target === heroRef.current && e.isIntersecting) {
            setHeroVisible(true);
          }
        });
      },
      { threshold: 0.15 }
    );
    if (statsRef.current) obs.observe(statsRef.current);
    if (heroRef.current) obs.observe(heroRef.current);
    return () => obs.disconnect();
  }, []);

  return (
    <div
      style={{
        minHeight: "100%",
        background: C.bg,
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* ──────── HERO — light, clean ──────── */}
      <div
        ref={heroRef}
        style={{
          position: "relative",
          overflow: "hidden",
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 28,
          margin: "24px 24px 0",
          padding: "52px 40px 48px",
          boxShadow: "0 8px 40px rgba(15,23,42,0.06)",
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? "translateY(0)" : "translateY(20px)",
          transition: "opacity 0.7s ease, transform 0.7s ease",
        }}
      >
        {/* subtle accent blob top-right */}
        <div
          style={{
            position: "absolute",
            top: -100,
            right: -100,
            width: 340,
            height: 340,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(91,91,239,0.08) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        <div
          style={{
            position: "relative",
            zIndex: 1,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 28,
            alignItems: "center",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "rgba(91,91,239,0.08)",
                border: "1px solid rgba(91,91,239,0.2)",
                borderRadius: 100,
                padding: "4px 14px",
                marginBottom: 18,
              }}
            >
              <Sparkles size={11} color={C.accent} />
              <span
                style={{
                  fontSize: 11,
                  color: C.accent,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                }}
              >
                AI-Powered Route Intelligence
              </span>
            </div>

            <div style={{ maxWidth: 580 }}>
              <h1
                style={{
                  fontSize: "clamp(26px, 4.5vw, 44px)",
                  fontWeight: 800,
                  color: C.ink,
                  letterSpacing: "-0.04em",
                  lineHeight: 1.12,
                  marginBottom: 16,
                }}
              >
                One Trip.{" "}
                <span style={{ color: C.accent }}>Two Missions.</span>
                <br />
                Zero Wasted Miles.
              </h1>

              <p
                style={{
                  fontSize: 15,
                  color: C.muted,
                  lineHeight: 1.75,
                  marginBottom: 32,
                  maxWidth: 500,
                }}
              >
                RouteFusion combines passenger rides and parcel deliveries into a
                single optimized trip — slashing costs, cutting emissions, and
                maximizing every journey.
              </p>

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <NavLink
                  to="/ride"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    background: C.accent,
                    color: "#ffffff",
                    borderRadius: 100,
                    padding: "11px 22px",
                    fontSize: 14,
                    fontWeight: 700,
                    textDecoration: "none",
                    transition: "opacity 0.2s, transform 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.opacity = "0.88";
                    (e.currentTarget as HTMLAnchorElement).style.transform = "scale(1.02)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.opacity = "1";
                    (e.currentTarget as HTMLAnchorElement).style.transform = "scale(1)";
                  }}
                >
                  <CarFront size={15} />
                  Book a Ride
                  <ArrowRight size={13} />
                </NavLink>
                <NavLink
                  to="/parcel"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    background: "transparent",
                    color: C.ink,
                    border: `1.5px solid ${C.border}`,
                    borderRadius: 100,
                    padding: "11px 22px",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                    transition: "border-color 0.2s, transform 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.borderColor = C.accent;
                    (e.currentTarget as HTMLAnchorElement).style.transform = "scale(1.02)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLAnchorElement).style.borderColor = C.border;
                    (e.currentTarget as HTMLAnchorElement).style.transform = "scale(1)";
                  }}
                >
                  <Package size={15} />
                  Send a Parcel
                </NavLink>
              </div>
            </div>
          </div>

          <HeroIllustration />
        </div>
      </div>

      {/* ──────── STATS STRIP ──────── */}
      <div
        ref={statsRef}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 16,
          margin: "20px 24px",
        }}
      >
        {stats.map((s, i) => (
          <div
            key={s.label}
            style={{
              opacity: statsVisible ? 1 : 0,
              transform: statsVisible ? "translateY(0)" : "translateY(20px)",
              transition: `opacity 0.6s ease ${i * 0.1}s, transform 0.6s ease ${i * 0.1}s`,
            }}
          >
            <StatCard {...s} visible={statsVisible} />
          </div>
        ))}
      </div>

      {/* ──────── BENEFITS GRID ──────── */}
      <div style={{ margin: "0 24px 20px" }}>
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 28,
            padding: "32px 28px",
            boxShadow: "0 4px 24px rgba(15,23,42,0.05)",
          }}
        >
          <div style={{ marginBottom: 24 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                color: C.accent,
              }}
            >
              Platform Benefits
            </span>
            <h2
              style={{
                fontSize: 20,
                fontWeight: 800,
                color: C.ink,
                letterSpacing: "-0.03em",
                marginTop: 6,
              }}
            >
              Why RouteFusion?
            </h2>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 14,
            }}
          >
            {benefits.map(({ icon: Icon, title, description, color }) => (
              <div
                key={title}
                style={{
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 20,
                  padding: "20px 18px",
                  transition:
                    "transform 0.2s, box-shadow 0.2s, border-color 0.2s",
                }}
                onMouseEnter={(e) => {
                  const el = e.currentTarget as HTMLDivElement;
                  el.style.transform = "translateY(-3px)";
                  el.style.boxShadow = `0 12px 32px ${color}22`;
                  el.style.borderColor = color + "55";
                }}
                onMouseLeave={(e) => {
                  const el = e.currentTarget as HTMLDivElement;
                  el.style.transform = "translateY(0)";
                  el.style.boxShadow = "none";
                  el.style.borderColor = C.border;
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 12,
                    background: color + "14",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 14,
                  }}
                >
                  <Icon size={18} color={color} />
                </div>
                <p
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: C.ink,
                    marginBottom: 6,
                    lineHeight: 1.3,
                  }}
                >
                  {title}
                </p>
                <p
                  style={{
                    fontSize: 12,
                    color: C.muted,
                    lineHeight: 1.7,
                  }}
                >
                  {description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ──────── FOOTER CTA — light ──────── */}
      <div
        style={{
          margin: "0 24px 24px",
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 28,
          padding: "40px 32px",
          boxShadow: "0 4px 24px rgba(15,23,42,0.05)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 15,
            background: "rgba(91,91,239,0.08)",
            border: `1px solid rgba(91,91,239,0.18)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 18px",
          }}
        >
          <CheckCircle2 size={22} color={C.accent} />
        </div>
        <h2
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: C.ink,
            letterSpacing: "-0.03em",
            marginBottom: 10,
          }}
        >
          Ready to optimize your routes?
        </h2>
        <p
          style={{
            fontSize: 14,
            color: C.muted,
            marginBottom: 28,
            lineHeight: 1.7,
            maxWidth: 380,
          }}
        >
          Join the platform that makes every mile count — for passengers,
          parcels, and the planet.
        </p>
        <div
          style={{
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          <NavLink
            to="/ride"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: C.accent,
              color: "#fff",
              borderRadius: 100,
              padding: "11px 26px",
              fontSize: 14,
              fontWeight: 700,
              textDecoration: "none",
              transition: "opacity 0.2s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.opacity = "0.88";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.opacity = "1";
            }}
          >
            <CarFront size={15} />
            Get Started
          </NavLink>
          <NavLink
            to="/dashboard"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: "transparent",
              color: C.ink,
              border: `1.5px solid ${C.border}`,
              borderRadius: 100,
              padding: "11px 26px",
              fontSize: 14,
              fontWeight: 600,
              textDecoration: "none",
              transition: "border-color 0.2s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderColor = C.accent;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderColor = C.border;
            }}
          >
            <BarChart3 size={15} />
            View Dashboard
          </NavLink>
        </div>
      </div>
    </div>
  );
}
