"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuth } from "@/contexts/AuthContext";

const PUBLIC_PATHS = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (isLoading) return;
    // In dev mode the backend accepts no-auth requests; we detect this by
    // checking if SECRET_KEY is still the default. On the frontend side we
    // rely on the NEXT_PUBLIC_AUTH_ENABLED env var to control the guard.
    const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";
    if (authEnabled && !user && !isPublic) {
      router.replace("/login");
    }
    if (user && pathname === "/login") {
      router.replace("/");
    }
  }, [isLoading, user, isPublic, pathname, router]);

  // Login page — no sidebar
  if (isPublic) return <>{children}</>;

  // Waiting for auth init
  if (isLoading) return null;

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
