import React from "react";
import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

import { cn } from "@/lib/utils";

type AuthLayoutProps = React.PropsWithChildren;

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <main className="flex h-screen flex-col justify-center md:flex-row-reverse">
      <Link
        href="/"
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "absolute left-4 top-4 h-9 text-muted-foreground sm:left-8 sm:top-8",
        )}
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Home
      </Link>

      <section className="mx-auto hidden h-full w-full items-start px-4 md:flex md:w-1/3 md:items-center md:px-0">
        <div className="relative mx-auto my-auto w-full min-w-min max-w-sm md:-left-2 md:mx-0">
          <div className="bg-background py-4">
            <div className="relative -ml-2.5 flex items-center text-2xl font-medium gap-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-9 w-9"
              >
                <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" />
              </svg>
              ProBTP
            </div>
          </div>
        </div>
      </section>
      <section className="justify-center px-4 md:flex md:w-2/3 md:border-r md:px-0">
        <div className="mx-auto flex w-full min-w-min flex-col justify-center gap-8 sm:max-w-[450px]">{children}</div>
      </section>
    </main>
  );
}
