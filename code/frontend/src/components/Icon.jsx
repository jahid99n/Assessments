const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  list: "M8 5h13 M8 12h13 M8 19h13 M3 5h.01 M3 12h.01 M3 19h.01",
  receipt: "M6 3h12v18l-3-2-3 2-3-2-3 2V3 M9 7h6 M9 11h6 M9 15h3",
  wallet: "M3 7h18v13H3z M3 7V4h15v3 M16 11h5v5h-5z",
  up: "M12 16V4 M7 9l5-5 5 5 M4 16v4h16v-4",
  plus: "M12 5v14 M5 12h14",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  logout: "M9 4H4v16h5 M10 12h11 M17 8l4 4-4 4",
  check: "M5 12l4 4L19 6",
  close: "M6 6l12 12 M6 18L18 6",
  shield: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3 M8 12l3 3 5-6",
  trend: "M3 18l6-6 4 3 8-11 M15 4h6v6",
  info: "M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  search: "M21 21l-6-6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  bell: "M6 8a6 6 0 0 1 12 0v7l2 3H4l2-3V8 M10 21h4",
};
export default function Icon({ name, size = 20 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.receipt} />
    </svg>
  );
}
