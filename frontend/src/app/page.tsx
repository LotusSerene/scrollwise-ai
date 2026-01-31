"use client";
import React from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  ClipboardList,
  Feather,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/MockAuthProvider";
import Image from "next/image";

export default function HomePage() {
  const auth = useAuth();

  const handleGoToDashboard = () => {
    window.location.href = "/dashboard";
  };

  return (
    <div className="min-h-screen bg-background text-foreground antialiased relative overflow-hidden">

      <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center px-4 sm:px-6 lg:px-8">
          <div className="mr-4 hidden md:flex">
            <Link
              href="/"
              className="mr-6 flex items-center space-x-2 relative group"
            >
              <div className="absolute inset-0 rounded-full bg-primary/10 transform scale-0 group-hover:scale-125 transition-transform duration-300"></div>
              <Feather className="h-6 w-6 text-primary transition-transform duration-300 group-hover:rotate-12" />
              <span className="font-bold sm:inline-block font-display tracking-wide relative">
                ScrollWise
                <span className="absolute -bottom-1 left-0 w-0 h-[2px] bg-primary/70 group-hover:w-full transition-all duration-300"></span>
              </span>
            </Link>
            <nav className="hidden md:flex items-center gap-6 text-sm">
            </nav>
          </div>
          <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
            <nav className="flex items-center gap-2">
              <Link href="/dashboard">
                <Button
                  variant="outline"
                  className="relative group overflow-hidden"
                >
                  <span className="relative z-10 transition-colors">
                    Dashboard
                  </span>
                  <span className="absolute inset-0 bg-primary/10 transform scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-300"></span>
                </Button>
              </Link>
            </nav>
          </div>
        </div>
      </header>
      <section className="container mx-auto px-6 py-32 md:py-40 flex flex-col items-center text-center relative">
        <h1 className="text-5xl md:text-7xl font-bold tracking-wider mb-8 font-display relative z-10 text-foreground/95">
          <span className="relative inline-block">
            <span className="relative z-10 typewriter-text">
              Welcome to ScrollWise
            </span>
            <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-24 h-1 bg-primary/60"></span>
          </span>
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-3xl mb-12 relative z-10 leading-relaxed">
          Your intelligent co-pilot for crafting compelling narratives,
          organizing complex worlds, and managing creative projects seamlessly.
          Turn your ideas into masterpieces.
        </p>
        <div className="flex items-center justify-center w-full max-w-md mb-12">
          <div className="flex-grow h-px bg-border/70"></div>
          <Feather className="mx-4 text-primary/70 h-6 w-6" />
          <div className="flex-grow h-px bg-border/70"></div>
        </div>
        <Link href="#features">
          <Button
            size="lg"
            variant="outline"
            className="group border-primary text-primary hover:bg-primary/10 hover:text-primary text-lg px-8 py-6 rounded-md relative overflow-hidden transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 active:translate-y-0"
          >
            <span className="relative z-10">Explore Features</span>
            <ArrowRight className="relative z-10 ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            <span className="absolute inset-0 bg-primary/5 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-500"></span>
          </Button>
        </Link>
      </section>
      <section id="features" className="py-20 md:py-28 relative">
        <div className="container mx-auto px-6 relative">
          <div className="flex flex-col items-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-center mb-4 font-display tracking-wide">
              Why Choose ScrollWise?
            </h2>
            <div className="w-32 h-1 bg-primary/40 rounded-full mb-3"></div>
            <Feather className="text-primary/60 h-6 w-6" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
            <Card className="bg-card border-border text-card-foreground transition-all duration-300 hover:border-primary/50 relative overflow-hidden group shadow-md hover:shadow-lg transform hover:-translate-y-1">
              <CardHeader className="items-center text-center">
                <div className="p-4 rounded-full bg-primary/10 mb-5 transition-all duration-300 group-hover:bg-primary/20 border border-primary/5 relative overflow-hidden">
                  <BookOpen className="h-8 w-8 text-primary transition-all duration-500 ease-out transform group-hover:translate-x-1 group-hover:-translate-x-1"
                    style={{
                      animation: 'none'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.animation = 'slideLeftRight 1.2s ease-in-out infinite';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.animation = 'none';
                    }}
                  />
                </div>
                <CardTitle className="text-xl font-semibold font-display tracking-wide">
                  Intelligent Narrative Crafting
                </CardTitle>
                <CardDescription className="text-muted-foreground mt-1">
                  AI-powered suggestions, plot structuring tools, character
                  development assistance, and help ensuring stylistic
                  consistency (learn about{" "}
                  <a
                    href="https://en.wikipedia.org/wiki/Style_guide"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    style guides
                  </a>
                  ).
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center text-muted-foreground/80 pb-6">
                Overcome writer&apos;s block and weave intricate stories with
                smart guidance every step of the way.
              </CardContent>
            </Card>
            <Card className="bg-card border-border text-card-foreground transition-all duration-300 hover:border-primary/50 relative overflow-hidden group shadow-md hover:shadow-lg transform hover:-translate-y-1">
              <CardHeader className="items-center text-center">
                <div className="p-4 rounded-full bg-primary/10 mb-5 transition-all duration-300 group-hover:bg-primary/20 border border-primary/5 relative overflow-hidden">
                  <BrainCircuit className="h-8 w-8 text-primary transition-all duration-500 ease-out transform group-hover:translate-x-1 group-hover:-translate-x-1"
                    style={{
                      animation: 'none'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.animation = 'slideLeftRight 1.2s ease-in-out infinite';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.animation = 'none';
                    }}
                  />
                </div>
                <CardTitle className="text-xl font-semibold font-display tracking-wide">
                  Worldbuilding & Lore Management
                </CardTitle>
                <CardDescription className="text-muted-foreground mt-1">
                  Organize timelines, locations, characters, and magical systems
                  in one interconnected space.
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center text-muted-foreground/80 pb-6">
                Build rich, consistent worlds with dedicated tools designed for
                complex universe creation.
              </CardContent>
            </Card>
            <Card className="bg-card border-border text-card-foreground transition-all duration-300 hover:border-primary/50 relative overflow-hidden group shadow-md hover:shadow-lg transform hover:-translate-y-1">
              <CardHeader className="items-center text-center">
                <div className="p-4 rounded-full bg-primary/10 mb-5 transition-all duration-300 group-hover:bg-primary/20 border border-primary/5 relative overflow-hidden">
                  <ClipboardList className="h-8 w-8 text-primary transition-all duration-500 ease-out transform group-hover:translate-x-1 group-hover:-translate-x-1"
                    style={{
                      animation: 'none'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.animation = 'slideLeftRight 1.2s ease-in-out infinite';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.animation = 'none';
                    }}
                  />
                </div>
                <CardTitle className="text-xl font-semibold font-display tracking-wide">
                  Seamless Project Organization
                </CardTitle>
                <CardDescription className="text-muted-foreground mt-1">
                  Manage multiple projects, track progress, set deadlines, and
                  collaborate effectively.
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center text-muted-foreground/80 pb-6">
                Stay on top of your creative endeavors with intuitive project
                dashboards and task management.
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
      <section className="container mx-auto px-6 py-20 md:py-28 text-center relative">
        <h2 className="text-3xl md:text-4xl font-bold mb-16 font-display tracking-wide relative z-10">
          <span className="relative inline-block">
            Get Started in Minutes
            <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-16 h-1 bg-primary/60"></span>
          </span>
        </h2>
        <div className="flex flex-col md:flex-row justify-center items-center gap-8 md:gap-12 relative z-10">
          <div className="flex flex-col items-center group transition-all duration-300 transform hover:-translate-y-1">
            <div className="text-5xl font-bold text-primary mb-3 relative">
              <span>1</span>
            </div>
            <p className="text-lg text-muted-foreground font-medium">
              Launch App
            </p>
          </div>
          <div className="text-muted-foreground hidden md:block relative">
            <div className="w-20 h-1 bg-muted-foreground/30"></div>
          </div>
          <div className="flex flex-col items-center group transition-all duration-300 transform hover:-translate-y-1">
            <div className="text-5xl font-bold text-primary mb-3 relative">
              <span>2</span>
            </div>
            <p className="text-lg text-muted-foreground font-medium">
              Create Your Project
            </p>
          </div>
          <div className="text-muted-foreground hidden md:block relative">
            <div className="w-20 h-1 bg-muted-foreground/30"></div>
          </div>
          <div className="flex flex-col items-center group transition-all duration-300 transform hover:-translate-y-1">
            <div className="text-5xl font-bold text-primary mb-3 relative">
              <span>3</span>
            </div>
            <p className="text-lg text-muted-foreground font-medium">
              Start Writing & Building
            </p>
          </div>
        </div>
      </section>
      <section className="py-20 md:py-28 relative overflow-hidden">
        <div className="container mx-auto px-6 text-center relative z-10">
          <div className="mb-8 flex justify-center">
            <div className="h-16 w-16 rounded-full border-2 border-primary/40 flex items-center justify-center opacity-60">
              <Sparkles className="h-8 w-8 text-primary/70" />
            </div>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold mb-6 font-display tracking-wide">
            Ready to Unleash Your Creativity?
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            Join ScrollWise today and experience the future of intelligent
            writing and project management.
          </p>
          <Button
            onClick={
              auth.isAuthenticated
                ? handleGoToDashboard
                : handleGoToDashboard
            }
            size="lg"
            className="group bg-primary text-primary-foreground hover:bg-primary/90 text-lg px-8 py-6 rounded-md relative overflow-hidden transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 active:translate-y-0 border border-primary/30"
          >
            <span className="relative z-10">
              Go to Dashboard
            </span>
            <ArrowRight className="relative z-10 ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            <span className="absolute inset-0 bg-primary/90 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-500"></span>
          </Button>
        </div>
      </section>
      <footer className="py-10 relative z-10">
        <div className="container mx-auto px-6 mb-8">
          <div className="w-full h-px bg-border/50 relative">
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background px-6">
              <Feather className="h-5 w-5 text-primary/40" />
            </div>
          </div>
        </div>
        <div className="container mx-auto px-6 text-center text-muted-foreground">
          &copy; {new Date().getFullYear()} ScrollWise. All rights reserved.
          <div className="mt-3 flex items-center justify-center text-sm">
            Join our community for more support:
            <a
              href="https://discord.gg/c6zfPcekzV"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 flex items-center text-primary hover:underline"
            >
              <Image
                src="/discord.svg"
                alt="Discord Icon"
                width={20}
                height={20}
                className="mr-1"
              />
              Discord
            </a>
          </div>
        </div>
      </footer>
      <style jsx global>{`
        @keyframes typewriter {
          from {
            width: 0;
          }
          to {
            width: 100%;
          }
        }

        @keyframes slideLeftRight {
          0% {
            transform: translateX(0);
          }
          25% {
            transform: translateX(8px);
          }
          75% {
            transform: translateX(-8px);
          }
          100% {
            transform: translateX(0);
          }
        }

        .typewriter-text {
          display: inline-block;
          overflow: hidden;
          white-space: nowrap;
          animation: typewriter 2.5s steps(40, end) 0.5s 1 normal both;
        }
      `}</style>
    </div>
  );
}
