"use client";

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center">
      <h1 className="text-4xl font-bold">404 - Page Not Found</h1>
      <p className="mt-4 text-lg">
        The page you are looking for does not exist.
      </p>
      <Link href="/" className="mt-8 px-4 py-2 text-lg font-semibold text-white bg-blue-500 rounded-md">
        Go back home
      </Link>
    </div>
  );
}
