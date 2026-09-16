import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  color?: "purple" | "green" | "red" | "yellow" | "blue" | "gray";
  className?: string;
}

const colors = {
  purple: "bg-purple-100 text-purple-800",
  green:  "bg-green-100 text-green-800",
  red:    "bg-red-100 text-red-800",
  yellow: "bg-yellow-100 text-yellow-800",
  blue:   "bg-blue-100 text-blue-800",
  gray:   "bg-gray-100 text-gray-700",
};

export default function Badge({ children, color = "gray", className }: BadgeProps) {
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium", colors[color], className)}>
      {children}
    </span>
  );
}
