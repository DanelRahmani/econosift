"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "@/components/ThemeProvider";

interface SparklineProps {
  data: number[];
  positive: boolean;
  width?: number;
  height?: number;
  className?: string;
}

export function Sparkline({ data, positive, width = 120, height = 40, className = "" }: SparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || data.length < 2) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const pad = 4;
    const w = width - pad * 2;
    const h = height - pad * 2;

    const toX = (i: number) => pad + (i / (data.length - 1)) * w;
    const toY = (v: number) => pad + h - ((v - min) / range) * h;

    // Fill
    const fillColor = positive
      ? theme === "dark" ? "rgba(22,163,74,0.15)" : "rgba(22,163,74,0.12)"
      : theme === "dark" ? "rgba(196,57,74,0.15)" : "rgba(196,57,74,0.12)";
    const strokeColor = positive ? "#16a34a" : "#c4394a";

    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) {
      ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.lineTo(toX(data.length - 1), height - pad);
    ctx.lineTo(toX(0), height - pad);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) {
      ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.stroke();
  }, [data, positive, width, height, theme]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={className}
      aria-hidden="true"
    />
  );
}
