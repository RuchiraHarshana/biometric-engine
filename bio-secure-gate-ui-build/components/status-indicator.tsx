"use client"

export function StatusIndicator() {
  return (
    <div className="flex items-center gap-2">
      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
      <span className="text-xs text-muted-foreground">System Active</span>
    </div>
  )
}
