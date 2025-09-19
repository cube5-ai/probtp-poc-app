import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "healthy":
    case "online":
      return "text-green-600 dark:text-green-400";
    case "warning":
      return "text-yellow-600 dark:text-yellow-400";
    case "error":
    case "offline":
      return "text-red-600 dark:text-red-400";
    default:
      return "text-gray-600 dark:text-gray-400";
  }
}

export function getStatusBgColor(status: string): string {
  switch (status) {
    case "healthy":
    case "online":
      return "bg-green-500";
    case "warning":
      return "bg-yellow-500";
    case "error":
    case "offline":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}
