import { Card } from "@/components/ui/card"

export function SkeletonCard() {
  return (
    <Card className="bg-card/50 border-border p-6">
      <div className="space-y-3">
        <div className="h-4 bg-muted rounded w-3/4 animate-pulse" />
        <div className="h-8 bg-muted rounded w-1/2 animate-pulse" />
        <div className="h-4 bg-muted rounded w-2/3 animate-pulse" />
      </div>
    </Card>
  )
}
