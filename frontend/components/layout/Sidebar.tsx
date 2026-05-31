"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Bell,
  Upload,
  TrendingUp,
  LogOut,
  LogIn,
  Search,
  BarChart2,
  History,
  Database,
  User,
  Newspaper,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/aktualnosci", label: "Aktualności", icon: Newspaper },
  { href: "/search", label: "Szukaj aktywa", icon: Search },
  { href: "/tfi", label: "TFI", icon: Building2 },
  { href: "/funds", label: "Fundusze", icon: Building2 },
  { href: "/subfunds", label: "Subfundusze", icon: Building2 },
  { href: "/dane", label: "Dane", icon: Database, authOnly: true },
  { href: "/rankings", label: "Rankingi i analizy", icon: BarChart2 },
  { href: "/alerts", label: "Alerty", icon: Bell },
  { href: "/upload", label: "Upload", icon: Upload, authOnly: true },
  { href: "/historia", label: "Historia uploadów", icon: History, authOnly: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="w-60 flex flex-col border-r bg-card">
      <div className="flex items-center gap-2 p-5 border-b">
        <TrendingUp className="h-6 w-6 text-primary" />
        <span className="font-bold text-base leading-tight">Fund Tracker</span>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {nav.filter((item) => !item.authOnly || !!user).map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-3 border-t space-y-1">
        {user ? (
          <>
            <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground truncate">
              <User className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{user.email}</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-3 py-2 w-full rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Wyloguj
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-3 px-3 py-2 w-full rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
          >
            <LogIn className="h-4 w-4" />
            Zaloguj się
          </Link>
        )}
      </div>
    </aside>
  );
}
