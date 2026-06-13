import React from "react";
import { ThemeSelector } from "../shared/ThemeSelector";

interface HeaderProps {
  themeMode: "light" | "dark";
  onToggleTheme: () => void;
}

export function Header({ themeMode, onToggleTheme }: HeaderProps) {
  return (
    <header
      className="h-16 border-b border-base-300 px-6 flex items-center justify-between bg-base-100 w-full"
      id="header"
    >
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-bold">
          Workspace
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <ThemeSelector />
      </div>
    </header>
  );
}
