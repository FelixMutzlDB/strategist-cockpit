import { Routes, Route, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import Canvas from "./pages/Canvas";
import Engagements from "./pages/Engagements";
import Gallery from "./pages/Gallery";
import Impact from "./pages/Impact";
import Ask from "./pages/Ask";
import { StrategoChat } from "./components/StrategoChat";
import {
  LayoutGrid,
  Compass,
  BarChart3,
  FolderOpen,
  PieChart,
  Sparkles,
} from "lucide-react";

function NavLink({
  to,
  children,
  icon: Icon,
}: {
  to: string;
  children: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
        isActive
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
      {children}
    </Link>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      {/* Top navigation */}
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <Link to="/" className="flex items-center gap-2 mr-8">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <Compass className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-bold text-lg">Strategist Cockpit</span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/" icon={LayoutGrid}>
              Home
            </NavLink>
            <NavLink to="/canvas" icon={Compass}>
              Canvas
            </NavLink>
            <NavLink to="/engagements" icon={BarChart3}>
              Engagements
            </NavLink>
            <NavLink to="/impact" icon={PieChart}>
              Impact
            </NavLink>
            <NavLink to="/ask" icon={Sparkles}>
              Ask
            </NavLink>
            <NavLink to="/gallery" icon={FolderOpen}>
              Gallery
            </NavLink>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="container py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/canvas" element={<Canvas />} />
          <Route path="/engagements" element={<Engagements />} />
          <Route path="/impact" element={<Impact />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </main>

      {/* Floating Stratego chat */}
      <StrategoChat />
    </div>
  );
}
