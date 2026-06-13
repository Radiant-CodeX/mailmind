'use client';

import React, { useEffect, useState } from 'react';

const THEMES = [
  'light',
  'dark',
  'cupcake',
  'bumblebee',
  'emerald',
  'corporate',
  'synthwave',
  'retro',
  'cyberpunk',
  'valentine',
  'halloween',
  'garden',
  'forest',
  'aqua',
  'lofi',
  'pastel',
  'fantasy',
  'wireframe',
  'black',
  'luxury',
  'dracula',
  'cmyk',
  'autumn',
  'business',
  'acid',
  'lemonade',
  'night',
  'coffee',
  'winter',
  'dim',
  'nord',
  'sunset',
];

export function ThemeSelector() {
  const [currentTheme, setCurrentTheme] = useState<string>('dark');

  useEffect(() => {
    const saved = localStorage.getItem('theme') || 'dark';
    setCurrentTheme(saved);
    document.documentElement.setAttribute('data-theme', saved);
  }, []);

  const handleThemeChange = (theme: string) => {
    setCurrentTheme(theme);
    localStorage.setItem('theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  };

  return (
    <div className="dropdown dropdown-end">
      <button
        tabIndex={0}
        className="btn btn-ghost btn-circle btn-sm"
        title="Theme selector"
        aria-label="Change theme"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5"
        >
          <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8zm0-14a1 1 0 0 0-1 1v4a1 1 0 0 0 2 0V7a1 1 0 0 0-1-1z" />
        </svg>
      </button>
      <ul
        tabIndex={0}
        className="dropdown-content z-[1] p-2 shadow bg-base-100 rounded-box w-52 grid grid-cols-2 gap-1"
      >
        {THEMES.map((theme) => (
          <li key={theme}>
            <button
              onClick={() => handleThemeChange(theme)}
              className={`btn btn-sm btn-ghost w-full justify-start ${
                currentTheme === theme ? 'btn-active' : ''
              }`}
              title={`Switch to ${theme} theme`}
            >
              <span className="capitalize text-xs">{theme}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
