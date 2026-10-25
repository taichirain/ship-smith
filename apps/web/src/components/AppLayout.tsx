'use client';

import { ReactNode, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { LayoutDashboard, Package, BookOpen, LogOut, Loader, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { getToken, clearToken } from '@/lib/api';

const COLLAPSE_KEY = 'shipsmith.sidebar.collapsed';

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push('/');
    } else {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === '1');
    } catch {
      // storage can be unavailable; keep the sidebar expanded
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((previous) => {
      const next = !previous;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0');
      } catch {
        // ignore storage failures
      }
      return next;
    });
  }

  function handleLogout() {
    clearToken();
    window.location.replace('/');
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader className="w-8 h-8 text-primary-600 animate-spin" />
      </div>
    );
  }

  const navItems = [
    {
      href: '/',
      label: 'Dashboard',
      icon: LayoutDashboard,
      active: pathname === '/',
    },
    {
      href: '/projects',
      label: 'Projects',
      icon: Package,
      active: pathname === '/projects' || pathname.startsWith('/projects/'),
    },
  ];

  const linkClass = (active: boolean) =>
    `flex items-center gap-3 rounded-md py-2 text-sm font-medium transition-colors ${
      collapsed ? 'justify-center px-0' : 'px-3'
    } ${active ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-50'}`;

  return (
    <div className="min-h-screen flex">
      <aside
        className={`${collapsed ? 'w-20' : 'w-64'} shrink-0 bg-white border-r border-gray-200 flex flex-col transition-[width] duration-200`}
      >
        <div
          className={`flex h-16 shrink-0 items-center border-b border-gray-200 ${
            collapsed ? 'flex-col justify-center gap-1 px-2' : 'justify-between px-4'
          }`}
        >
          <Link href="/" className="flex min-w-0 items-center gap-2">
            <img src="/logo.svg" alt="ShipSmith" className="w-6 h-6 shrink-0" />
            {!collapsed && <span className="truncate text-lg font-semibold text-gray-900">ShipSmith</span>}
          </Link>
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="shrink-0 rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-2">
          {navItems.map(({ href, label, icon: Icon, active }) => (
            <Link key={href} href={href} title={collapsed ? label : undefined} className={linkClass(active)}>
              <Icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </Link>
          ))}
          <a
            href="/docs/index.html"
            target="_blank"
            rel="noopener noreferrer"
            title={collapsed ? 'Guide' : undefined}
            className={linkClass(false)}
          >
            <BookOpen className="w-5 h-5 shrink-0" />
            {!collapsed && <span className="truncate">Guide</span>}
          </a>
        </nav>

        <div className="border-t border-gray-200 p-2">
          <button
            onClick={handleLogout}
            title={collapsed ? 'Log out' : undefined}
            className={`flex w-full items-center gap-3 rounded-md py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 ${
              collapsed ? 'justify-center px-0' : 'px-3'
            }`}
          >
            <LogOut className="w-5 h-5 shrink-0" />
            {!collapsed && <span className="truncate">Log out</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-auto">
        {children}
      </main>
    </div>
  );
}
