import { Badge } from "@/components/ui/badge";

export function ThemePills({
  themes,
  variant = "default",
}: {
  themes: string[];
  variant?: "default" | "gap";
}) {
  if (themes.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing yet — generate a digest first.</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {themes.map((theme) => (
        <Badge
          key={theme}
          variant={variant === "gap" ? "outline" : "secondary"}
          className={variant === "gap" ? "border-chart-2/60 text-chart-2" : undefined}
        >
          {theme}
        </Badge>
      ))}
    </div>
  );
}
