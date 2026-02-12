import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Compass, BarChart3, FolderOpen, Bot } from "lucide-react";

const tiles = [
  {
    title: "Strategist Canvas",
    description:
      "Your strategic framework at a glance. Explore the pillars of Thought Leadership, Coaching, Customer Mobilization, and more.",
    icon: Compass,
    to: "/canvas",
    color: "from-blue-500/10 to-indigo-500/10",
    iconColor: "text-blue-600",
  },
  {
    title: "Impact Dashboard",
    description:
      "Track engagements and measure impact across fiscal years, territories, and engagement types.",
    icon: BarChart3,
    to: "/impact",
    color: "from-emerald-500/10 to-teal-500/10",
    iconColor: "text-emerald-600",
  },
  {
    title: "Projects Gallery",
    description:
      "Reusable assets and key artefacts -- presentations, apps, frameworks, and templates at your fingertips.",
    icon: FolderOpen,
    to: "/gallery",
    color: "from-amber-500/10 to-orange-500/10",
    iconColor: "text-amber-600",
  },
];

export default function Home() {
  return (
    <div className="space-y-8">
      {/* Hero / Welcome */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/5 via-primary/10 to-primary/5 border p-8 md:p-12">
        <div className="flex items-start gap-6">
          <div className="hidden md:flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary shadow-lg">
            <Bot className="h-8 w-8 text-primary-foreground" />
          </div>
          <div className="space-y-3">
            <h1 className="text-3xl font-bold tracking-tight">
              Welcome to the Strategist Cockpit
            </h1>
            <div className="bg-background/80 backdrop-blur rounded-lg p-4 border max-w-2xl">
              <p className="text-muted-foreground leading-relaxed">
                <span className="font-semibold text-foreground">Hey! I'm Stratego</span>{" "}
                -- your strategic advisory companion. This cockpit brings together your
                engagements, the strategist canvas framework, impact metrics, and reusable
                assets in one place. Explore the tiles below or chat with me anytime using
                the button in the bottom right corner.
              </p>
            </div>
            <p className="text-sm text-muted-foreground">
              Translating business vision into data & AI programs and organizational change.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Tiles */}
      <div className="grid gap-6 md:grid-cols-3">
        {tiles.map((tile) => (
          <Link key={tile.to} to={tile.to} className="group">
            <Card className="h-full transition-all hover:shadow-md hover:border-primary/20 group-hover:-translate-y-0.5">
              <CardHeader>
                <div
                  className={`h-12 w-12 rounded-xl bg-gradient-to-br ${tile.color} flex items-center justify-center mb-2`}
                >
                  <tile.icon className={`h-6 w-6 ${tile.iconColor}`} />
                </div>
                <CardTitle className="text-xl">{tile.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                  {tile.description}
                </CardDescription>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
